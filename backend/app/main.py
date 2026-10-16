import hmac
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, poems, templates, music, creations, credits
from .admin import router as admin_router

app = FastAPI(title="Tweezers API", version="0.1.0")

def _cors_origins() -> list[str]:
    """Browsers only: the mobile app does not use CORS. Set CORS_ORIGINS to a comma separated
    list (for example the credits checkout page's origin). Unset means no cross-origin access,
    except in local dev (AUTH_DEV_BYPASS=true) where everything is allowed for the demo pages."""
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if raw:
        return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return ["*"] if os.getenv("AUTH_DEV_BYPASS", "false").lower() == "true" else []


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST", "PATCH", "PUT", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def origin_verify(request, call_next):
    """When ORIGIN_VERIFY_SECRET is set (CDN in front, e.g. CloudFront or Cloudflare), only
    requests carrying the matching X-Origin-Verify header are served, so the server cannot be
    used by hitting its own address directly. /health stays open for uptime checks."""
    secret = os.getenv("ORIGIN_VERIFY_SECRET", "")
    if secret and request.url.path != "/health":
        sent = request.headers.get("x-origin-verify", "")
        if not hmac.compare_digest(sent.encode(), secret.encode()):
            return JSONResponse({"detail": "Forbidden"}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # Browsers ignore HSTS over plain HTTP, so this only takes effect behind HTTPS.
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    if request.url.path.startswith(("/admin/api", "/auth", "/credits")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


# Schema is managed by Alembic: run `alembic upgrade head` (the Docker image does this on start).


# Placeholder music (see static/music/generate.sh). Real media should live on R2/CDN.
app.mount("/static", StaticFiles(directory=Path(__file__).resolve().parent.parent / "static"), name="static")

app.include_router(auth.router)
app.include_router(poems.router)
app.include_router(templates.router)
app.include_router(music.router)
app.include_router(creations.router)
app.include_router(creations.viewer_router)
app.include_router(credits.router)
app.include_router(admin_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}


# Admin dashboard UI (built from admin/, see admin/README.md). Mounted last so the
# /admin/api routes above take priority. Skipped when the build isn't present.
_admin_ui = Path(os.getenv("ADMIN_UI_DIR", Path(__file__).resolve().parent.parent.parent / "admin" / "dist"))
if _admin_ui.is_dir():
    app.mount("/admin", StaticFiles(directory=_admin_ui, html=True), name="admin-ui")
