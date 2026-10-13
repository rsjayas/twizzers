from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/music", tags=["music"])


@router.get("/", response_model=List[schemas.MusicTrackOut])
def list_music(mood: Optional[str] = Query(None), db: Session = Depends(get_db)):
    tracks = db.query(models.MusicTrack).all()
    if mood:
        tracks = [t for t in tracks if mood in (t.mood_tags or [])]
    return tracks
