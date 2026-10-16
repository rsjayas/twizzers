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
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models
from .accounts import create_user, ensure_active
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


def sign_in_provider(claims: dict) -> str:
    return (claims.get("firebase") or {}).get("sign_in_provider") or "other"


def get_or_create_user(db: Session, claims: dict, name: str | None = None) -> models.User:
    """
    Maps a verified Firebase token to our user.

    - A known Firebase account (uid) always maps to its user.
    - A new Firebase account is linked to an existing user only when the match is proven:
      the same phone number (phone sign-in proves the phone) or the same email address
      when Firebase says that email is verified. An unverified email is never used to link,
      so nobody can take over an account by registering someone else's address.
    - Email + password accounts must have a verified email before they can use the app.
    """
    uid = claims.get("user_id") or claims.get("sub")
    if not uid:
        raise HTTPException(401, "Token has no user id")
    provider = sign_in_provider(claims)
    phone = claims.get("phone_number")
    email = (claims.get("email") or "").strip().lower() or None
    email_verified = bool(claims.get("email_verified"))
    name = name or (claims.get("name") or "").strip() or None  # Firebase display name (set at sign-up / by Google)

    if provider == "password" and not email_verified:
        raise HTTPException(403, "email_not_verified")

    identity = db.query(models.UserIdentity).filter(models.UserIdentity.firebase_uid == uid).first()
    if identity:
        return ensure_active(identity.user)

    user = None
    if phone:
        user = db.query(models.User).filter(models.User.phone == phone).first()
    if not user and email and email_verified:
        user = db.query(models.User).filter(func.lower(models.User.email) == email).first()

    if not user:
        user = create_user(db, phone=phone, email=email if email_verified else None, name=name, auth_provider=provider)
    else:
        ensure_active(user)
        # Fill in details we did not have yet.
        if email and email_verified and not user.email:
            user.email = email
        if phone and not user.phone:
            user.phone = phone
        if name and not user.name:
            user.name = name
    db.add(models.UserIdentity(user_id=user.id, firebase_uid=uid, provider=provider))
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
        return ensure_active(user)
    return get_or_create_user(db, verify_id_token(token))
