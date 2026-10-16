from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, poems, templates, music, creations, credits

app = FastAPI(title="Tweezers API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before production
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/health")
def health():
    return {"status": "ok"}
