import datetime as dt
import hashlib
import hmac
import html
import os

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..firebase_auth import get_current_user

router = APIRouter(prefix="/creations", tags=["creations"])

# Public recipient page (no /creations prefix): GET /v/{slug}
viewer_router = APIRouter(tags=["viewer"])

# Render service (see render-service/). When RENDER_SERVICE_URL is unset the
# creation is marked ready immediately with a placeholder URL, so the rest of
# the app stays testable without Node/Chromium.
RENDER_SERVICE_URL = os.getenv("RENDER_SERVICE_URL", "").rstrip("/")
RENDER_SECRET = os.getenv("RENDER_SECRET", "")
# Where the render service can reach this API to report results.
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000").rstrip("/")


def _absolute(url: str | None) -> str | None:
    """Relative asset paths (e.g. /static/music/x.mp3) are served by this API; the
    render service needs a full URL that it can reach."""
    if url and url.startswith("/"):
        return f"{BACKEND_PUBLIC_URL}{url}"
    return url


async def _dispatch_render(creation: models.Creation, poem: models.Poem, template, music) -> None:
    job = {
        "job_id": creation.id,
        "poem": poem.content,
        "mood_tags": (template.mood_tags if template else None) or [],
        "template_category": template.category if template else None,
        "music_url": _absolute(music.audio_file_url) if music else None,
        "callback_url": f"{BACKEND_PUBLIC_URL}/creations/internal/{creation.id}/render-result",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(f"{RENDER_SERVICE_URL}/render", json=job, headers={"x-render-secret": RENDER_SECRET})
        resp.raise_for_status()


@router.post("/", response_model=schemas.CreationOut)
async def create_creation(
    payload: schemas.CreationCreateRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    poem = db.query(models.Poem).filter(models.Poem.id == payload.poem_id, models.Poem.user_id == user.id).first()
    if not poem or poem.status != "finalized":
        raise HTTPException(400, "Poem must be finalized before creating a video")

    creation = models.Creation(
        user_id=user.id,
        poem_id=payload.poem_id,
        template_id=payload.template_id,
        music_track_id=payload.music_track_id,
        status="rendering",
    )
    db.add(creation)
    db.commit()
    db.refresh(creation)

    if not RENDER_SERVICE_URL:
        creation.status = "ready"
        creation.rendered_video_url = f"https://cdn.example.com/renders/{creation.id}.mp4"
        creation.thumbnail_url = f"https://cdn.example.com/renders/{creation.id}.jpg"
    else:
        template = db.query(models.Template).filter(models.Template.id == payload.template_id).first()
        music = db.query(models.MusicTrack).filter(models.MusicTrack.id == payload.music_track_id).first()
        try:
            await _dispatch_render(creation, poem, template, music)
        except httpx.HTTPError:
            creation.status = "failed"
    db.commit()
    db.refresh(creation)
    return creation


@router.post("/internal/{creation_id}/render-result")
def render_result(
    creation_id: str,
    payload: schemas.RenderResultRequest,
    db: Session = Depends(get_db),
    x_render_secret: str = Header(default=""),
):
    """Called by the render service when a job finishes. Not for apps/users."""
    if not RENDER_SECRET or not hmac.compare_digest(x_render_secret, RENDER_SECRET):
        raise HTTPException(401, "Unauthorized")
    creation = db.query(models.Creation).filter(models.Creation.id == creation_id).first()
    if not creation:
        raise HTTPException(404, "Creation not found")
    if payload.status == "ready" and payload.video_url:
        creation.status = "ready"
        creation.rendered_video_url = payload.video_url
        creation.thumbnail_url = payload.thumbnail_url
    else:
        creation.status = "failed"
    db.commit()
    return {"ok": True}


@router.get("/mine")
def my_creations(limit: int = 30, offset: int = 0, db: Session = Depends(get_db),
                 user: models.User = Depends(get_current_user)):
    """The signed-in user's videos, newest first (removed ones are left out)."""
    limit, offset = max(1, min(limit, 100)), max(0, offset)
    rows = (db.query(models.Creation)
            .filter(models.Creation.user_id == user.id, models.Creation.status != "removed")
            .order_by(models.Creation.created_at.desc()).limit(limit).offset(offset).all())
    return [{
        "id": c.id, "status": c.status, "rendered_video_url": c.rendered_video_url,
        "thumbnail_url": c.thumbnail_url, "share_link_slug": c.share_link_slug,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "poem": c.poem.content if c.poem else None,
    } for c in rows]


@router.get("/{creation_id}", response_model=schemas.CreationOut)
def get_creation(creation_id: str, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    creation = db.query(models.Creation).filter(
        models.Creation.id == creation_id, models.Creation.user_id == user.id
    ).first()
    if not creation:
        raise HTTPException(404, "Creation not found")
    return creation


@router.get("/share/{slug}", response_model=schemas.CreationOut)
def get_creation_by_share_link(slug: str, db: Session = Depends(get_db)):
    """Public recipient-facing lookup - no auth required."""
    creation = db.query(models.Creation).filter(models.Creation.share_link_slug == slug).first()
    if not creation or creation.status == "removed":
        raise HTTPException(404, "Not found")
    creation.recipient_view_count = (creation.recipient_view_count or 0) + 1
    db.commit()
    db.refresh(creation)
    return creation


@router.post("/share-event")
def log_share_event(
    payload: schemas.ShareEventRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    owned = db.query(models.Creation).filter(
        models.Creation.id == payload.creation_id, models.Creation.user_id == user.id
    ).first()
    if not owned:
        raise HTTPException(404, "Creation not found")
    share = models.Share(creation_id=payload.creation_id, channel=payload.channel)
    db.add(share)
    db.commit()
    return {"ok": True}


@viewer_router.get("/v/{slug}", response_class=HTMLResponse)
def view_creation(slug: str, db: Session = Depends(get_db)):
    """Public page the recipient opens from a shared link: the video and poem."""
    creation = db.query(models.Creation).filter(models.Creation.share_link_slug == slug).first()
    if not creation or creation.status == "removed":
        raise HTTPException(404, "Not found")
    creation.recipient_view_count = (creation.recipient_view_count or 0) + 1
    db.commit()

    poem = html.escape(creation.poem.content or "") if creation.poem else ""
    if creation.status == "ready" and creation.rendered_video_url:
        poster = f' poster="{html.escape(creation.thumbnail_url, quote=True)}"' if creation.thumbnail_url else ""
        media = (
            f'<video controls playsinline autoplay loop{poster} '
            f'src="{html.escape(creation.rendered_video_url, quote=True)}"></video>'
        )
    elif creation.status == "failed":
        media = "<p>This video could not be made, but the poem is below.</p>"
    else:
        media = "<p>Your video is still being made. Refresh in a minute.</p>"

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>A poem for you - Tweezers</title>
<style>
body{{margin:0;min-height:100vh;display:flex;flex-direction:column;align-items:center;background:#fff0f4;
font-family:Georgia,'Noto Serif',serif;color:#3a1f2b;padding:24px 16px;box-sizing:border-box}}
video{{width:100%;max-width:380px;border-radius:18px;box-shadow:0 8px 24px rgba(209,65,107,.2)}}
pre{{white-space:pre-wrap;font-family:inherit;font-size:1.1rem;line-height:1.5;text-align:center;max-width:380px}}
small{{color:#8a6070;margin-top:16px}}\ndetails.report{{margin-top:12px;color:#8a6070;font-size:.85rem;max-width:380px;width:100%}}\ndetails.report form{{display:flex;flex-direction:column;gap:8px;margin-top:8px}}\ndetails.report textarea,details.report select{{font:inherit;padding:6px}}
</style></head><body>
{media}
<pre>{poem}</pre>
<small>Made with Tweezers - two bodies, one soul</small>
<details class="report"><summary>Report this video</summary>
<form id="report-form">
<select name="reason"><option value="inappropriate">Inappropriate</option><option value="harassment">Harassment or abuse</option><option value="spam">Spam</option><option value="other">Something else</option></select>
<textarea name="details" maxlength="500" placeholder="Tell us more (optional)"></textarea>
<button type="submit">Send report</button>
<p id="report-result" role="status"></p>
</form></details>
<script>
document.getElementById("report-form").addEventListener("submit", async function (e) {{
  e.preventDefault();
  var f = e.target, out = document.getElementById("report-result");
  var res = await fetch("/v/{html.escape(slug, quote=True)}/report", {{
    method: "POST", headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify({{reason: f.reason.value, details: f.details.value}})
  }});
  out.textContent = res.ok ? "Thank you. We will review it." : "Could not send the report. Please try again later.";
  if (res.ok) f.querySelector("button").disabled = true;
}});
</script>
</body></html>"""


REPORT_REASONS = ("inappropriate", "harassment", "spam", "other")
MAX_REPORTS_PER_HOUR = 5


class ReportIn(BaseModel):
    reason: str
    details: str | None = Field(None, max_length=500)


def _reporter_hash(request: Request) -> str:
    # Behind a CDN the real address arrives in X-Forwarded-For (the first entry is the client).
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "unknown")
    salt = os.getenv("REPORT_SALT", "tweezers-report")
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()


@viewer_router.post("/v/{slug}/report")
def report_creation(slug: str, payload: ReportIn, request: Request, db: Session = Depends(get_db)):
    """Public: a viewer reports a shared video. Limited per reporter, never reveals more than ok."""
    if payload.reason not in REPORT_REASONS:
        raise HTTPException(422, f"reason must be one of: {', '.join(REPORT_REASONS)}")
    creation = db.query(models.Creation).filter(models.Creation.share_link_slug == slug).first()
    if not creation or creation.status == "removed":
        raise HTTPException(404, "Not found")
    who = _reporter_hash(request)
    now = dt.datetime.utcnow()
    recent = db.query(models.Report).filter(models.Report.reporter_hash == who,
                                            models.Report.created_at >= now - dt.timedelta(hours=1)).count()
    if recent >= MAX_REPORTS_PER_HOUR:
        raise HTTPException(429, "Too many reports. Try again later.")
    duplicate = db.query(models.Report).filter(models.Report.reporter_hash == who,
                                               models.Report.creation_id == creation.id,
                                               models.Report.created_at >= now - dt.timedelta(hours=24)).first()
    if not duplicate:
        db.add(models.Report(creation_id=creation.id, reason=payload.reason,
                             details=(payload.details or "").strip() or None, reporter_hash=who))
        db.commit()
    return {"ok": True}
