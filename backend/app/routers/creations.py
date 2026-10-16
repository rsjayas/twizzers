import hmac
import os

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..firebase_auth import get_current_user

router = APIRouter(prefix="/creations", tags=["creations"])

# Render service (see render-service/). When RENDER_SERVICE_URL is unset the
# creation is marked ready immediately with a placeholder URL, so the rest of
# the app stays testable without Node/Chromium.
RENDER_SERVICE_URL = os.getenv("RENDER_SERVICE_URL", "").rstrip("/")
RENDER_SECRET = os.getenv("RENDER_SECRET", "")
# Where the render service can reach this API to report results.
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000").rstrip("/")


async def _dispatch_render(creation: models.Creation, poem: models.Poem, template, music) -> None:
    job = {
        "job_id": creation.id,
        "poem": poem.content,
        "mood_tags": (template.mood_tags if template else None) or [],
        "music_url": music.audio_file_url if music else None,
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
    if not creation:
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
