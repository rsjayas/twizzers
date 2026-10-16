"""
Firebase Auth (phone OTP) token verification.

The mobile app signs the user in with Firebase and sends the resulting ID
token to the backend. We verify it against Google's public keys and map the
Firebase user (uid) to a row in `users`.

Requires FIREBASE_PROJECT_ID (the Firebase project's ID, which is the
expected audience of the token).
"""
import logging
import os

from fastapi import Depends, Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from . import models
from .database import get_db

FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

# LOCAL DEVELOPMENT ONLY. When "true", `Authorization: Bearer dev:<user_id>`
# is accepted as that user (no Firebase needed) and POST /auth/signup is
# enabled. This lets frontend-demo work locally. NEVER enable in production.
AUTH_DEV_BYPASS = os.getenv("AUTH_DEV_BYPASS", "false").lower() == "true"
if AUTH_DEV_BYPASS:
    logging.getLogger("uvicorn.error").warning("AUTH_DEV_BYPASS is ON - anyone can act as any user. Local dev only!")


def verify_id_token(token: str) -> dict:
    """Returns the verified token claims (contains 'uid'/'sub', 'phone_number', ...)."""
    if not FIREBASE_PROJECT_ID:
        raise HTTPException(503, "FIREBASE_PROJECT_ID is not configured")
    try:
        claims = google_id_token.verify_firebase_token(
            token, google_requests.Request(), audience=FIREBASE_PROJECT_ID
        )
    except ValueError:
        claims = None
    if not claims:
        raise HTTPException(401, "Invalid or expired Firebase token")
    return claims


def get_or_create_user(db: Session, claims: dict, name: str | None = None) -> models.User:
    uid = claims.get("user_id") or claims.get("sub")
    if not uid:
        raise HTTPException(401, "Token has no user id")
    phone = claims.get("phone_number")
    email = claims.get("email")

    user = db.query(models.User).filter(models.User.firebase_uid == uid).first()
    if user:
        return user

    # Link users created earlier through the old signup stub, by phone/email.
    if phone:
        user = db.query(models.User).filter(models.User.phone == phone).first()
    if not user and email:
        user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        user.firebase_uid = uid
        user.auth_provider = "firebase"
    else:
        user = models.User(firebase_uid=uid, phone=phone, email=email, name=name, auth_provider="firebase")
        db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    authorization: str = Header(default=""),
    db: Session = Depends(get_db),
) -> models.User:
    """Dependency for protected routes: 'Authorization: Bearer <Firebase ID token>'."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Missing bearer token")
    if AUTH_DEV_BYPASS and token.startswith("dev:"):
        user = db.query(models.User).filter(models.User.id == token[4:]).first()
        if not user:
            raise HTTPException(401, "Unknown dev user")
        return user
    return get_or_create_user(db, verify_id_token(token))
