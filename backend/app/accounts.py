"""Creating app users: the one place that applies the signup switch and welcome credits."""
import datetime as dt

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models, settings_store


def create_user(db: Session, **fields) -> models.User:
    if not settings_store.get_value(db, "signups_enabled"):
        raise HTTPException(403, "signups_closed")
    user = models.User(**fields)
    db.add(user)
    db.flush()
    welcome = settings_store.get_value(db, "welcome_credits")
    if welcome > 0:
        user.credits_balance = welcome
        db.add(models.CreditTransaction(user_id=user.id, credits=welcome, amount_inr=0, status="adjusted",
                                        note="Welcome credits", paid_at=dt.datetime.utcnow()))
    return user


def ensure_active(user: models.User) -> models.User:
    """Blocked or erased accounts cannot use the API."""
    if user.deleted_at is not None:
        raise HTTPException(401, "account_deleted")
    if user.is_blocked:
        raise HTTPException(403, "account_blocked")
    return user
