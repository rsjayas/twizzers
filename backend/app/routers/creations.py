from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..firebase_auth import get_current_user

router = APIRouter(prefix="/creations", tags=["creations"])


@router.post("/", response_model=schemas.CreationOut)
def create_creation(
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

    # TODO: enqueue actual render job here (see infra/render-service).
    # For now we mark it ready immediately with a placeholder URL so the
    # rest of the app (share flow, recipient view) is fully testable.
    creation.status = "ready"
    creation.rendered_video_url = f"https://cdn.example.com/renders/{creation.id}.mp4"
    creation.thumbnail_url = f"https://cdn.example.com/renders/{creation.id}.jpg"
    db.commit()
    db.refresh(creation)
    return creation


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
