from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/templates", tags=["templates"])


@router.get("/", response_model=List[schemas.TemplateOut])
def list_templates(mood: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(models.Template).filter(models.Template.is_active == True)  # noqa: E712
    templates = q.all()
    if mood:
        templates = [t for t in templates if mood in (t.mood_tags or [])]
    return templates
