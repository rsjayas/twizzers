from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import Base, engine
from . import models  # noqa: F401 - ensures models are registered before create_all
from .routers import auth, poems, templates, music, creations, credits

app = FastAPI(title="Tweezers API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # MVP: create tables directly. Move to Alembic migrations before production.
    Base.metadata.create_all(bind=engine)


app.include_router(auth.router)
app.include_router(poems.router)
app.include_router(templates.router)
app.include_router(music.router)
app.include_router(creations.router)
app.include_router(credits.router)


@app.get("/health")
def health():
    return {"status": "ok"}
