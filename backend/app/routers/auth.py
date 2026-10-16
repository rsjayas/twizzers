from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import firebase_auth, models, schemas
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/firebase", response_model=schemas.UserOut)
def firebase_login(payload: schemas.FirebaseLoginRequest, db: Session = Depends(get_db)):
    """
    Exchange a Firebase ID token (from the app's phone-OTP login) for the
    backend user. Creates the user on first login.
    """
    claims = firebase_auth.verify_id_token(payload.id_token)
    return firebase_auth.get_or_create_user(db, claims, name=payload.name)


@router.get("/me", response_model=schemas.UserOut)
def me(user: models.User = Depends(firebase_auth.get_current_user)):
    return user


@router.post("/signup", response_model=schemas.UserOut)
def signup(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    LEGACY stub (no verification) used by frontend-demo. Real login is
    POST /auth/firebase; remove this once the app and demo use it.
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
