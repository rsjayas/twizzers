"""Creating app users: the one place that applies the signup switch and welcome credits."""
import datetime as dt

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models, render_client, settings_store


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


def erase_user_data(db: Session, user: models.User) -> dict:
    """Privacy erasure, used by admins and by users deleting their own account.

    Removes sign-in methods, poems, videos and shares, and blanks the profile. Payment records
    stay (financial records) but no longer identify anyone. The caller adds any audit entry and
    commits; call finish_erase() afterwards to delete the video files."""
    creation_ids = [c.id for c in db.query(models.Creation.id).filter(models.Creation.user_id == user.id)]
    poem_ids = [p.id for p in db.query(models.Poem.id).filter(models.Poem.user_id == user.id)]
    if creation_ids:
        db.query(models.Report).filter(models.Report.creation_id.in_(creation_ids)).delete(synchronize_session=False)
        db.query(models.Share).filter(models.Share.creation_id.in_(creation_ids)).delete(synchronize_session=False)
        db.query(models.Creation).filter(models.Creation.id.in_(creation_ids)).delete(synchronize_session=False)
    if poem_ids:
        db.query(models.PoemVariant).filter(models.PoemVariant.poem_id.in_(poem_ids)).delete(synchronize_session=False)
        db.query(models.Poem).filter(models.Poem.id.in_(poem_ids)).delete(synchronize_session=False)
    db.query(models.Partner).filter(models.Partner.user_id == user.id).delete(synchronize_session=False)
    db.query(models.UserIdentity).filter(models.UserIdentity.user_id == user.id).delete(synchronize_session=False)
    user.name, user.email, user.phone = "Deleted user", None, None
    user.is_blocked, user.blocked_reason = True, "Account erased"
    user.deleted_at = dt.datetime.utcnow()
    return {"creations": len(creation_ids), "poems": len(poem_ids), "creation_ids": creation_ids}


def finish_erase(erased: dict) -> dict:
    """After the database commit: delete the video files, and return the public summary."""
    render_client.delete_render_files(erased["creation_ids"])
    return {"creations": erased["creations"], "poems": erased["poems"]}
