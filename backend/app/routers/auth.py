from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=schemas.UserOut)
def signup(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    MVP-simplified signup: no real OTP/password flow yet.
    Swap this for Firebase Auth / Clerk verification before shipping.
    """
    existing = None
    if payload.phone:
        existing = db.query(models.User).filter(models.User.phone == payload.phone).first()
    elif payload.email:
        existing = db.query(models.User).filter(models.User.email == payload.email).first()

    if existing:
        return existing

    user = models.User(phone=payload.phone, email=payload.email, name=payload.name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
