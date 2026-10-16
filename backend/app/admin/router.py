"""
Admin dashboard API (served under /admin/api). Every route needs an admin
token; changes are role-checked and written to the audit log.
"""
import csv
import datetime as dt
import io
import os
from typing import Optional

import httpx
import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from .. import models, settings_store
from ..database import get_db
from ..routers import creations as creations_router
from . import security
from .security import audit, get_current_admin, require

router = APIRouter(prefix="/admin/api", tags=["admin"])

MAX_PAGE = 100


def _page(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(limit, MAX_PAGE)), max(0, offset)


def _iso(value: Optional[dt.datetime]) -> Optional[str]:
    return value.isoformat() if value else None


# ---------------------------------------------------------------- auth

class LoginRequest(BaseModel):
    email: str
    password: str
    code: Optional[str] = None  # authenticator-app code, needed when the admin turned on 2FA


def _admin_out(a: models.AdminUser) -> dict:
    return {
        "id": a.id,
        "email": a.email,
        "role": a.role,
        "is_active": a.is_active,
        "created_at": _iso(a.created_at),
        "last_login_at": _iso(a.last_login_at),
        "totp_enabled": bool(a.totp_enabled),
        "permissions": sorted(p for p, roles in security.PERMISSIONS.items() if a.role in roles),
    }


@router.post("/login")
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    keys = (f"ip:{security.client_ip(request)}", f"email:{email}")
    security.check_login_allowed(*keys)
    admin = db.query(models.AdminUser).filter(models.AdminUser.email == email).first()
    # Same error and same work for "no such admin" and "wrong password".
    ok = security.check_password(payload.password, admin.password_hash if admin else _DUMMY_HASH)
    if not admin or not ok or not admin.is_active:
        security.record_login_failure(*keys)
        raise HTTPException(401, "Wrong email or password")
    if admin.totp_enabled:
        if not payload.code:
            raise HTTPException(401, "2fa_required")  # not counted as a failed attempt
        if not pyotp.TOTP(admin.totp_secret).verify(payload.code.strip(), valid_window=1):
            security.record_login_failure(*keys)
            raise HTTPException(401, "Wrong code")
    security.clear_login_failures(*keys)
    admin.last_login_at = dt.datetime.utcnow()
    audit(db, admin, "admin.login")
    db.commit()
    return {"token": security.make_token(admin), "admin": _admin_out(admin)}


_DUMMY_HASH = security.hash_password("not-a-real-password")


@router.get("/me")
def me(admin: models.AdminUser = Depends(get_current_admin)):
    return _admin_out(admin)


# --------------------------------------------------------------- stats

def _daily(db: Session, column, since: dt.datetime, extra_filter=None, value=None) -> dict:
    """Counts (or sums of `value`) per day since `since`: {date: number}."""
    day = func.date(column)
    agg = func.coalesce(func.sum(value), 0) if value is not None else func.count()
    q = db.query(day, agg).filter(column >= since)
    if extra_filter is not None:
        q = q.filter(extra_filter)
    return {str(d): int(n) for d, n in q.group_by(day).all()}


@router.get("/stats")
def stats(days: int = 30, db: Session = Depends(get_db), admin: models.AdminUser = Depends(get_current_admin)):
    days = max(1, min(days, 180))
    today = dt.datetime.utcnow().date()
    since = dt.datetime.combine(today - dt.timedelta(days=days - 1), dt.time.min)
    series = {
        "signups": _daily(db, models.User.created_at, since),
        "poems": _daily(db, models.Poem.created_at, since),
        "creations": _daily(db, models.Creation.created_at, since),
        "shares": _daily(db, models.Share.shared_at, since),
        "revenue_inr": _daily(db, models.CreditTransaction.paid_at, since,
                              models.CreditTransaction.status == "paid", models.CreditTransaction.amount_inr),
    }
    dates = [str(today - dt.timedelta(days=days - 1 - i)) for i in range(days)]
    daily = [{"date": d, **{k: v.get(d, 0) for k, v in series.items()}} for d in dates]

    by_status = dict(db.query(models.Creation.status, func.count()).group_by(models.Creation.status).all())
    revenue = db.query(func.coalesce(func.sum(models.CreditTransaction.amount_inr), 0)).filter(
        models.CreditTransaction.status == "paid").scalar()

    def distinct_users(col, *joins):
        q = db.query(func.count(func.distinct(col)))
        for j in joins:
            q = q.join(*j)
        return q.scalar()

    funnel = {
        "signed_up": db.query(func.count(models.User.id)).filter(models.User.deleted_at.is_(None)).scalar(),
        "made_a_poem": distinct_users(models.Poem.user_id),
        "made_a_video": distinct_users(models.Creation.user_id),
        "shared": distinct_users(models.Creation.user_id, (models.Share, models.Share.creation_id == models.Creation.id)),
    }

    def top(model, name_col, fk):
        rows = (db.query(name_col, func.count(models.Creation.id))
                .join(models.Creation, fk == model.id)
                .filter(models.Creation.created_at >= since)
                .group_by(name_col).order_by(func.count(models.Creation.id).desc()).limit(5).all())
        return [{"name": n, "count": c} for n, c in rows]

    in_range = db.query(models.Creation.status, func.count()).filter(models.Creation.created_at >= since) \
        .group_by(models.Creation.status).all()
    range_counts = dict(in_range)
    finished = range_counts.get("ready", 0) + range_counts.get("failed", 0)

    return {
        "totals": {
            "users": db.query(func.count(models.User.id)).scalar(),
            "poems": db.query(func.count(models.Poem.id)).scalar(),
            "creations": db.query(func.count(models.Creation.id)).scalar(),
            "shares": db.query(func.count(models.Share.id)).scalar(),
            "revenue_inr": int(revenue),
            "credits_outstanding": int(db.query(func.coalesce(func.sum(models.User.credits_balance), 0)).scalar()),
            "open_reports": db.query(func.count(models.Report.id)).filter(models.Report.status == "open").scalar(),
        },
        "creations_by_status": by_status,
        "render_failure_rate": round(range_counts.get("failed", 0) / finished, 3) if finished else 0,
        "funnel": funnel,
        "shares_by_channel": [{"name": n, "count": c} for n, c in
                              db.query(models.Share.channel, func.count()).filter(models.Share.shared_at >= since)
                              .group_by(models.Share.channel).order_by(func.count().desc()).all()],
        "top_templates": top(models.Template, models.Template.name, models.Creation.template_id),
        "top_music": top(models.MusicTrack, models.MusicTrack.title, models.Creation.music_track_id),
        "daily": daily,
    }


# --------------------------------------------------------------- users

def _user_out(u: models.User) -> dict:
    return {"id": u.id, "name": u.name, "phone": u.phone, "email": u.email,
            "providers": sorted({i.provider for i in u.identities}), "credits_balance": u.credits_balance or 0,
            "is_blocked": bool(u.is_blocked), "blocked_reason": u.blocked_reason,
            "deleted": u.deleted_at is not None, "created_at": _iso(u.created_at)}


def _creation_out(c: models.Creation) -> dict:
    return {"id": c.id, "user_id": c.user_id, "status": c.status, "rendered_video_url": c.rendered_video_url,
            "thumbnail_url": c.thumbnail_url, "share_link_slug": c.share_link_slug,
            "recipient_view_count": c.recipient_view_count or 0, "created_at": _iso(c.created_at),
            "poem": (c.poem.content if c.poem else None)}


def _txn_out(t: models.CreditTransaction) -> dict:
    return {"id": t.id, "user_id": t.user_id, "credits": t.credits, "amount_inr": t.amount_inr,
            "status": t.status, "note": t.note, "cashfree_order_id": t.cashfree_order_id,
            "created_at": _iso(t.created_at), "paid_at": _iso(t.paid_at)}


@router.get("/users")
def list_users(q: str = "", limit: int = 25, offset: int = 0, db: Session = Depends(get_db),
               admin: models.AdminUser = Depends(get_current_admin)):
    limit, offset = _page(limit, offset)
    query = db.query(models.User)
    term = q.strip()
    if term:
        like = f"%{term}%"
        query = query.filter(or_(models.User.name.ilike(like), models.User.phone.ilike(like),
                                 models.User.email.ilike(like), models.User.id == term))
    total = query.count()
    rows = query.order_by(models.User.created_at.desc()).limit(limit).offset(offset).all()
    return {"total": total, "items": [_user_out(u) for u in rows]}


@router.get("/users/{user_id}")
def get_user(user_id: str, db: Session = Depends(get_db), admin: models.AdminUser = Depends(get_current_admin)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    creations = db.query(models.Creation).filter(models.Creation.user_id == user_id) \
        .order_by(models.Creation.created_at.desc()).limit(20).all()
    txns = db.query(models.CreditTransaction).filter(models.CreditTransaction.user_id == user_id) \
        .order_by(models.CreditTransaction.created_at.desc()).limit(20).all()
    return {
        **_user_out(user),
        "poem_count": db.query(func.count(models.Poem.id)).filter(models.Poem.user_id == user_id).scalar(),
        "creations": [_creation_out(c) for c in creations],
        "transactions": [_txn_out(t) for t in txns],
    }


class CreditAdjustment(BaseModel):
    delta: int = Field(..., ge=-1000, le=1000)
    reason: str = Field(..., min_length=3, max_length=200)


@router.post("/users/{user_id}/credits")
def adjust_credits(user_id: str, payload: CreditAdjustment, db: Session = Depends(get_db),
                   admin: models.AdminUser = Depends(require("adjust_credits"))):
    if payload.delta == 0:
        raise HTTPException(400, "Adjustment cannot be zero")
    user = db.query(models.User).filter(models.User.id == user_id).with_for_update().first()
    if not user:
        raise HTTPException(404, "User not found")
    new_balance = (user.credits_balance or 0) + payload.delta
    if new_balance < 0:
        raise HTTPException(400, f"Balance cannot go below zero (currently {user.credits_balance or 0})")
    user.credits_balance = new_balance
    db.add(models.CreditTransaction(user_id=user.id, credits=payload.delta, amount_inr=0, status="adjusted",
                                    note=payload.reason, paid_at=dt.datetime.utcnow()))
    audit(db, admin, "credits.adjust", "user", user.id, {"delta": payload.delta, "reason": payload.reason,
                                                         "new_balance": new_balance})
    db.commit()
    return {"credits_balance": new_balance}


class Reason(BaseModel):
    reason: str = Field(..., min_length=3, max_length=200)


@router.post("/users/{user_id}/block")
def block_user(user_id: str, payload: Reason, db: Session = Depends(get_db),
               admin: models.AdminUser = Depends(require("block_users"))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.deleted_at is not None:
        raise HTTPException(400, "This account was erased")
    user.is_blocked, user.blocked_reason = True, payload.reason
    audit(db, admin, "user.block", "user", user.id, {"reason": payload.reason})
    db.commit()
    return _user_out(user)


@router.post("/users/{user_id}/unblock")
def unblock_user(user_id: str, payload: Reason, db: Session = Depends(get_db),
                 admin: models.AdminUser = Depends(require("block_users"))):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if user.deleted_at is not None:
        raise HTTPException(400, "This account was erased")
    user.is_blocked, user.blocked_reason = False, None
    audit(db, admin, "user.unblock", "user", user.id, {"reason": payload.reason})
    db.commit()
    return _user_out(user)


class EraseUser(BaseModel):
    reason: str = Field(..., min_length=3, max_length=200)
    confirm_user_id: str  # must equal the user's id, a guard against clicking the wrong account


@router.post("/users/{user_id}/erase")
def erase_user(user_id: str, payload: EraseUser, db: Session = Depends(get_db),
               admin: models.AdminUser = Depends(require("delete_users"))):
    """Privacy erasure: removes sign-in methods, poems, videos and shares and blanks the profile.
    Payment records stay (they are financial records) but no longer identify anyone. Video files in
    storage (R2) are not deleted by this yet."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    if payload.confirm_user_id != user.id:
        raise HTTPException(400, "Confirmation does not match the user id")
    if user.deleted_at is not None:
        raise HTTPException(400, "Already erased")
    creation_ids = [c.id for c in db.query(models.Creation.id).filter(models.Creation.user_id == user.id)]
    poem_ids = [p.id for p in db.query(models.Poem.id).filter(models.Poem.user_id == user.id)]
    removed = {"creations": len(creation_ids), "poems": len(poem_ids)}
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
    audit(db, admin, "user.erase", "user", user.id, {"reason": payload.reason, **removed})
    db.commit()
    return {"ok": True, **removed}


# ----------------------------------------------------------- creations

@router.get("/creations")
def list_creations(status: str = "", limit: int = 25, offset: int = 0, db: Session = Depends(get_db),
                   admin: models.AdminUser = Depends(get_current_admin)):
    limit, offset = _page(limit, offset)
    query = db.query(models.Creation)
    if status:
        query = query.filter(models.Creation.status == status)
    total = query.count()
    rows = query.order_by(models.Creation.created_at.desc()).limit(limit).offset(offset).all()
    return {"total": total, "items": [_creation_out(c) for c in rows]}


def _get_creation(db: Session, creation_id: str) -> models.Creation:
    creation = db.query(models.Creation).filter(models.Creation.id == creation_id).first()
    if not creation:
        raise HTTPException(404, "Creation not found")
    return creation


@router.post("/creations/{creation_id}/retry")
async def retry_render(creation_id: str, db: Session = Depends(get_db),
                       admin: models.AdminUser = Depends(require("retry_render"))):
    creation = _get_creation(db, creation_id)
    if creation.status not in ("failed", "rendering"):
        raise HTTPException(400, f"Only failed or stuck renders can be retried (status is {creation.status})")
    if not creations_router.RENDER_SERVICE_URL:
        raise HTTPException(503, "No render service is configured")
    creation.status = "rendering"
    try:
        await creations_router._dispatch_render(creation, creation.poem, creation.template, creation.music_track)
    except httpx.HTTPError:
        creation.status = "failed"
    audit(db, admin, "creation.retry", "creation", creation.id, {"result": creation.status})
    db.commit()
    return _creation_out(creation)


@router.post("/creations/{creation_id}/takedown")
def takedown(creation_id: str, payload: Reason, db: Session = Depends(get_db),
             admin: models.AdminUser = Depends(require("takedown"))):
    creation = _get_creation(db, creation_id)
    previous = creation.status
    creation.status = "removed"  # the public link stops working
    audit(db, admin, "creation.takedown", "creation", creation.id, {"reason": payload.reason, "previous": previous})
    db.commit()
    return _creation_out(creation)


@router.post("/creations/{creation_id}/restore")
def restore(creation_id: str, payload: Reason, db: Session = Depends(get_db),
            admin: models.AdminUser = Depends(require("takedown"))):
    creation = _get_creation(db, creation_id)
    if creation.status != "removed":
        raise HTTPException(400, "Creation is not removed")
    creation.status = "ready" if creation.rendered_video_url else "failed"
    audit(db, admin, "creation.restore", "creation", creation.id, {"reason": payload.reason})
    db.commit()
    return _creation_out(creation)


# -------------------------------------------------------- transactions

@router.get("/transactions")
def list_transactions(status: str = "", limit: int = 25, offset: int = 0, db: Session = Depends(get_db),
                      admin: models.AdminUser = Depends(get_current_admin)):
    limit, offset = _page(limit, offset)
    query = db.query(models.CreditTransaction)
    if status:
        query = query.filter(models.CreditTransaction.status == status)
    total = query.count()
    rows = query.order_by(models.CreditTransaction.created_at.desc()).limit(limit).offset(offset).all()
    return {"total": total, "items": [_txn_out(t) for t in rows]}


# ------------------------------------------------------------- content

class TemplateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: str = Field(..., min_length=1, max_length=100)
    mood_tags: list[str] = []
    lottie_file_url: Optional[str] = None
    rive_file_url: Optional[str] = None
    preview_thumbnail_url: Optional[str] = None
    is_active: bool = True


class TemplatePatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    mood_tags: Optional[list[str]] = None
    lottie_file_url: Optional[str] = None
    rive_file_url: Optional[str] = None
    preview_thumbnail_url: Optional[str] = None
    is_active: Optional[bool] = None


class MusicIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    artist: Optional[str] = None
    license_source: Optional[str] = None
    mood_tags: list[str] = []
    audio_file_url: str = Field(..., min_length=1)
    duration_seconds: Optional[int] = Field(None, ge=1, le=3600)


class MusicPatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=100)
    artist: Optional[str] = None
    license_source: Optional[str] = None
    mood_tags: Optional[list[str]] = None
    audio_file_url: Optional[str] = Field(None, min_length=1)
    duration_seconds: Optional[int] = Field(None, ge=1, le=3600)


class PackIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    credits: int = Field(..., ge=1, le=100000)
    price_inr: int = Field(..., ge=1, le=100000)
    is_active: bool = True


class PackPatch(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    credits: Optional[int] = Field(None, ge=1, le=100000)
    price_inr: Optional[int] = Field(None, ge=1, le=100000)
    is_active: Optional[bool] = None


def _row_out(row, fields: list[str]) -> dict:
    return {"id": row.id, **{f: getattr(row, f) for f in fields}}


TEMPLATE_FIELDS = ["name", "category", "mood_tags", "lottie_file_url", "rive_file_url", "preview_thumbnail_url", "is_active"]
MUSIC_FIELDS = ["title", "artist", "license_source", "mood_tags", "audio_file_url", "duration_seconds"]
PACK_FIELDS = ["label", "credits", "price_inr", "is_active"]


def _crud(prefix: str, model, fields: list[str], create_schema, patch_schema, noun: str, order):
    """Registers list/create/update routes for a content table (no hard delete:
    templates and packs are hidden with is_active, because creations point at them)."""

    @router.get(f"/{prefix}", name=f"list_{prefix}")
    def list_rows(db: Session = Depends(get_db), admin: models.AdminUser = Depends(get_current_admin)):
        return [_row_out(r, fields) for r in db.query(model).order_by(order).all()]

    @router.post(f"/{prefix}", name=f"create_{prefix}")
    def create_row(payload: create_schema, db: Session = Depends(get_db),
                   admin: models.AdminUser = Depends(require("manage_content"))):
        row = model(**payload.model_dump())
        db.add(row)
        db.flush()
        audit(db, admin, f"{noun}.create", noun, row.id, payload.model_dump())
        db.commit()
        return _row_out(row, fields)

    @router.patch(f"/{prefix}/{{row_id}}", name=f"update_{prefix}")
    def update_row(row_id: str, payload: patch_schema, db: Session = Depends(get_db),
                   admin: models.AdminUser = Depends(require("manage_content"))):
        row = db.query(model).filter(model.id == row_id).first()
        if not row:
            raise HTTPException(404, f"{noun.capitalize()} not found")
        changes = payload.model_dump(exclude_unset=True)
        for key, value in changes.items():
            setattr(row, key, value)
        audit(db, admin, f"{noun}.update", noun, row.id, changes)
        db.commit()
        return _row_out(row, fields)


_crud("templates", models.Template, TEMPLATE_FIELDS, TemplateIn, TemplatePatch, "template", models.Template.name)
_crud("music", models.MusicTrack, MUSIC_FIELDS, MusicIn, MusicPatch, "music", models.MusicTrack.title)
_crud("packs", models.CreditPack, PACK_FIELDS, PackIn, PackPatch, "pack", models.CreditPack.price_inr)


# ------------------------------------------------------------ settings

@router.get("/settings")
def get_settings(db: Session = Depends(get_db), admin: models.AdminUser = Depends(get_current_admin)):
    return settings_store.all_values(db)


class SettingsPatch(BaseModel):
    payments_enabled: Optional[bool] = None
    cost_per_story_credits: Optional[int] = None
    signups_enabled: Optional[bool] = None
    welcome_credits: Optional[int] = None


@router.put("/settings")
def update_settings(payload: SettingsPatch, db: Session = Depends(get_db),
                    admin: models.AdminUser = Depends(require("manage_settings"))):
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    old = settings_store.all_values(db)
    for key, value in changes.items():
        try:
            stored = settings_store.validate(key, value)
        except ValueError as e:
            raise HTTPException(400, str(e))
        row = db.query(models.Setting).filter(models.Setting.key == key).first()
        if row:
            row.value, row.updated_by = stored, admin.email
        else:
            db.add(models.Setting(key=key, value=stored, updated_by=admin.email))
    if changes:
        audit(db, admin, "settings.update", "settings", None, {"old": {k: old[k] for k in changes}, "new": changes})
    db.commit()
    return settings_store.all_values(db)


# --------------------------------------------------------------- admins

class AdminCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=10, max_length=200)
    role: str


class AdminPatch(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=10, max_length=200)
    reset_2fa: Optional[bool] = None  # turn off another admin's two-factor login (lost phone)


@router.get("/admins")
def list_admins(db: Session = Depends(get_db), admin: models.AdminUser = Depends(require("manage_admins"))):
    return [_admin_out(a) for a in db.query(models.AdminUser).order_by(models.AdminUser.created_at).all()]


@router.post("/admins")
def create_admin(payload: AdminCreate, db: Session = Depends(get_db),
                 admin: models.AdminUser = Depends(require("manage_admins"))):
    if payload.role not in security.ROLES:
        raise HTTPException(400, f"Role must be one of: {', '.join(security.ROLES)}")
    email = payload.email.strip().lower()
    if db.query(models.AdminUser).filter(models.AdminUser.email == email).first():
        raise HTTPException(409, "An admin with that email already exists")
    new = models.AdminUser(email=email, role=payload.role, password_hash=security.hash_password(payload.password))
    db.add(new)
    db.flush()
    audit(db, admin, "admin.create", "admin", new.id, {"email": email, "role": payload.role})
    db.commit()
    return _admin_out(new)


@router.patch("/admins/{admin_id}")
def update_admin(admin_id: str, payload: AdminPatch, db: Session = Depends(get_db),
                 admin: models.AdminUser = Depends(require("manage_admins"))):
    target = db.query(models.AdminUser).filter(models.AdminUser.id == admin_id).first()
    if not target:
        raise HTTPException(404, "Admin not found")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "role" in changes and changes["role"] not in security.ROLES:
        raise HTTPException(400, f"Role must be one of: {', '.join(security.ROLES)}")
    losing_super = target.role == "superadmin" and (
        changes.get("role", "superadmin") != "superadmin" or changes.get("is_active", True) is False)
    if losing_super:
        others = db.query(func.count(models.AdminUser.id)).filter(
            models.AdminUser.role == "superadmin", models.AdminUser.is_active.is_(True),
            models.AdminUser.id != target.id).scalar()
        if others == 0:
            raise HTTPException(400, "There must be at least one active superadmin")
    if target.id == admin.id and (changes.get("is_active") is False or "role" in changes):
        raise HTTPException(400, "You cannot change your own role or disable yourself")
    if changes.pop("reset_2fa", None):
        target.totp_secret, target.totp_enabled = None, False
        audit(db, admin, "admin.reset_2fa", "admin", target.id)
    if "password" in changes:
        target.password_hash = security.hash_password(changes.pop("password"))
        audit(db, admin, "admin.password_reset", "admin", target.id)
    for key, value in changes.items():
        setattr(target, key, value)
    if changes:
        audit(db, admin, "admin.update", "admin", target.id, changes)
    db.commit()
    return _admin_out(target)


# ---------------------------------------------------------------- audit

@router.get("/audit")
def list_audit(limit: int = 50, offset: int = 0, admin_email: str = "", action: str = "",
               db: Session = Depends(get_db), admin: models.AdminUser = Depends(require("view_audit"))):
    limit, offset = _page(limit, offset)
    query = db.query(models.AuditLog)
    if admin_email.strip():
        query = query.filter(models.AuditLog.admin_email.ilike(f"%{admin_email.strip()}%"))
    if action.strip():
        query = query.filter(models.AuditLog.action.ilike(f"{action.strip()}%"))
    total = query.count()
    rows = query.order_by(models.AuditLog.created_at.desc()).limit(limit).offset(offset).all()
    return {"total": total, "items": [
        {"id": r.id, "admin_email": r.admin_email, "action": r.action, "target_type": r.target_type,
         "target_id": r.target_id, "details": r.details, "created_at": _iso(r.created_at)} for r in rows]}


# -------------------------------------------------------------- reports

def _report_out(r: models.Report) -> dict:
    c = r.creation
    return {"id": r.id, "creation_id": r.creation_id, "reason": r.reason, "details": r.details, "status": r.status,
            "created_at": _iso(r.created_at), "handled_by": r.handled_by, "handled_at": _iso(r.handled_at),
            "resolution_note": r.resolution_note,
            "creation": {"status": c.status, "user_id": c.user_id, "share_link_slug": c.share_link_slug,
                         "rendered_video_url": c.rendered_video_url,
                         "poem": c.poem.content if c.poem else None} if c else None}


@router.get("/reports")
def list_reports(status: str = "open", limit: int = 25, offset: int = 0, db: Session = Depends(get_db),
                 admin: models.AdminUser = Depends(get_current_admin)):
    limit, offset = _page(limit, offset)
    query = db.query(models.Report)
    if status:
        query = query.filter(models.Report.status == status)
    total = query.count()
    rows = query.order_by(models.Report.created_at.desc()).limit(limit).offset(offset).all()
    return {"total": total, "items": [_report_out(r) for r in rows]}


class ResolveReport(BaseModel):
    action: str  # "takedown" removes the video and its public link; "dismiss" keeps it
    note: str = Field("", max_length=200)


@router.post("/reports/{report_id}/resolve")
def resolve_report(report_id: str, payload: ResolveReport, db: Session = Depends(get_db),
                   admin: models.AdminUser = Depends(require("takedown"))):
    if payload.action not in ("takedown", "dismiss"):
        raise HTTPException(400, "action must be takedown or dismiss")
    report = db.query(models.Report).filter(models.Report.id == report_id).first()
    if not report:
        raise HTTPException(404, "Report not found")
    if report.status != "open":
        raise HTTPException(400, "This report was already handled")
    now = dt.datetime.utcnow()
    if payload.action == "takedown":
        creation = report.creation
        if creation.status != "removed":
            creation.status = "removed"
        # Every open report on the same video is now resolved.
        for other in db.query(models.Report).filter(models.Report.creation_id == creation.id,
                                                    models.Report.status == "open").all():
            other.status, other.handled_by, other.handled_at = "actioned", admin.email, now
            other.resolution_note = payload.note or "Video taken down"
    else:
        report.status, report.handled_by, report.handled_at = "dismissed", admin.email, now
        report.resolution_note = payload.note or None
    audit(db, admin, f"report.{payload.action}", "report", report.id,
          {"creation_id": report.creation_id, "note": payload.note})
    db.commit()
    return _report_out(report)


# ---------------------------------------------------------------- poems

@router.get("/poems")
def list_poems(q: str = "", limit: int = 25, offset: int = 0, db: Session = Depends(get_db),
               admin: models.AdminUser = Depends(get_current_admin)):
    limit, offset = _page(limit, offset)
    query = db.query(models.Poem, models.User.name).outerjoin(models.User, models.User.id == models.Poem.user_id)
    term = q.strip()
    if term:
        query = query.filter(models.Poem.content.ilike(f"%{term}%"))
    total = query.count()
    rows = query.order_by(models.Poem.created_at.desc()).limit(limit).offset(offset).all()
    return {"total": total, "items": [
        {"id": p.id, "user_id": p.user_id, "user_name": name, "source": p.source, "status": p.status,
         "content": p.content, "created_at": _iso(p.created_at)} for p, name in rows]}


# --------------------------------------------------------------- system

@router.get("/system")
async def system_status(db: Session = Depends(get_db), admin: models.AdminUser = Depends(get_current_admin)):
    """What is configured and what needs attention. Never returns secrets."""
    try:
        db.execute(text("select 1"))
        database_ok = True
    except Exception:
        database_ok = False

    render_url = creations_router.RENDER_SERVICE_URL
    render = {"configured": bool(render_url), "reachable": None, "queued": None, "running": None}
    if render_url:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{render_url}/health")
            render.update(reachable=r.status_code == 200)
            if r.status_code == 200:
                render.update(queued=r.json().get("queued"), running=r.json().get("running"))
        except (httpx.HTTPError, ValueError):
            render["reachable"] = False

    now = dt.datetime.utcnow()
    attention = {
        "open_reports": db.query(func.count(models.Report.id)).filter(models.Report.status == "open").scalar(),
        "failed_renders_24h": db.query(func.count(models.Creation.id)).filter(
            models.Creation.status == "failed", models.Creation.created_at >= now - dt.timedelta(hours=24)).scalar(),
        "stuck_renders": db.query(func.count(models.Creation.id)).filter(
            models.Creation.status == "rendering", models.Creation.created_at <= now - dt.timedelta(minutes=15)).scalar(),
    }
    dev_bypass = os.getenv("AUTH_DEV_BYPASS", "false").lower() == "true"
    warnings = []
    if dev_bypass:
        warnings.append("AUTH_DEV_BYPASS is on: anyone can act as any user. Turn it off outside local development.")
    if not os.getenv("CORS_ORIGINS", "").strip() and not dev_bypass:
        warnings.append("CORS_ORIGINS is empty: browsers on other websites cannot call the API (fine unless the checkout page is hosted separately).")
    if not os.getenv("FIREBASE_PROJECT_ID"):
        warnings.append("FIREBASE_PROJECT_ID is not set: real sign-in cannot work.")
    if not os.getenv("ANTHROPIC_API_KEY"):
        warnings.append("ANTHROPIC_API_KEY is not set: poems are demo text.")
    if settings_store.get_value(db, "payments_enabled") and not (os.getenv("CASHFREE_CLIENT_ID") and os.getenv("CASHFREE_CLIENT_SECRET")):
        warnings.append("Payments are enabled but the Cashfree keys are missing.")
    if render_url and render["reachable"] is False:
        warnings.append("The render service is not reachable: new videos will fail.")
    if not render_url:
        warnings.append("RENDER_SERVICE_URL is not set: videos get placeholder links and are not really rendered.")
    return {
        "database_ok": database_ok,
        "render_service": render,
        "integrations": {
            "claude_api": bool(os.getenv("ANTHROPIC_API_KEY")),
            "firebase_auth": bool(os.getenv("FIREBASE_PROJECT_ID")),
            "cashfree": bool(os.getenv("CASHFREE_CLIENT_ID") and os.getenv("CASHFREE_CLIENT_SECRET")),
            "cashfree_environment": os.getenv("CASHFREE_ENV", "sandbox"),
        },
        "environment": {"auth_dev_bypass": dev_bypass, "origin_verify": bool(os.getenv("ORIGIN_VERIFY_SECRET")),
                        "cors_origins": [o for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]},
        "settings": settings_store.all_values(db),
        "attention": attention,
        "warnings": warnings,
    }


# -------------------------------------------------------------- exports

def _csv_cell(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        return str(value)  # numbers (including negative credits) stay numbers
    # Stops spreadsheet programs from running a text cell that starts like a formula.
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def _csv_response(filename: str, header: list[str], rows) -> Response:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    for row in rows:
        w.writerow([_csv_cell(v) for v in row])
    return Response(out.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@router.get("/export/users.csv")
def export_users(db: Session = Depends(get_db), admin: models.AdminUser = Depends(require("export_data"))):
    users = db.query(models.User).order_by(models.User.created_at).all()
    audit(db, admin, "export.users", "users", None, {"rows": len(users)})
    db.commit()
    return _csv_response("users.csv",
                         ["id", "name", "email", "phone", "sign_in_methods", "credits", "blocked", "erased", "created_at"],
                         [[u.id, u.name, u.email, u.phone, " ".join(sorted({i.provider for i in u.identities})),
                           u.credits_balance, u.is_blocked, u.deleted_at is not None, _iso(u.created_at)] for u in users])


@router.get("/export/transactions.csv")
def export_transactions(db: Session = Depends(get_db), admin: models.AdminUser = Depends(require("export_data"))):
    txns = db.query(models.CreditTransaction).order_by(models.CreditTransaction.created_at).all()
    audit(db, admin, "export.transactions", "transactions", None, {"rows": len(txns)})
    db.commit()
    return _csv_response("transactions.csv",
                         ["id", "user_id", "status", "credits", "amount_inr", "cashfree_order_id", "note", "created_at", "paid_at"],
                         [[t.id, t.user_id, t.status, t.credits, t.amount_inr, t.cashfree_order_id, t.note,
                           _iso(t.created_at), _iso(t.paid_at)] for t in txns])


# ----------------------------------------- my account: password and 2FA

class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=10, max_length=200)


@router.post("/me/password")
def change_password(payload: PasswordChange, db: Session = Depends(get_db),
                    admin: models.AdminUser = Depends(get_current_admin)):
    if not security.check_password(payload.current_password, admin.password_hash):
        raise HTTPException(400, "Current password is wrong")
    if payload.new_password == payload.current_password:
        raise HTTPException(400, "Choose a different password")
    admin.password_hash = security.hash_password(payload.new_password)
    audit(db, admin, "admin.change_password", "admin", admin.id)
    db.commit()
    return {"ok": True}


class PasswordOnly(BaseModel):
    password: str


@router.post("/me/2fa/setup")
def twofa_setup(payload: PasswordOnly, db: Session = Depends(get_db),
                admin: models.AdminUser = Depends(get_current_admin)):
    """Starts two-factor setup: returns a secret to add to an authenticator app. It only
    takes effect after /me/2fa/enable confirms a code."""
    if not security.check_password(payload.password, admin.password_hash):
        raise HTTPException(400, "Password is wrong")
    if admin.totp_enabled:
        raise HTTPException(400, "Two-factor login is already on")
    secret = pyotp.random_base32()
    admin.totp_secret = secret
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=admin.email, issuer_name="Tweezers admin")
    return {"secret": secret, "otpauth_uri": uri}


class CodeOnly(BaseModel):
    code: str


@router.post("/me/2fa/enable")
def twofa_enable(payload: CodeOnly, db: Session = Depends(get_db),
                 admin: models.AdminUser = Depends(get_current_admin)):
    if not admin.totp_secret:
        raise HTTPException(400, "Start the setup first")
    if not pyotp.TOTP(admin.totp_secret).verify(payload.code.strip(), valid_window=1):
        raise HTTPException(400, "That code is not right")
    admin.totp_enabled = True
    audit(db, admin, "admin.2fa_enabled", "admin", admin.id)
    db.commit()
    return _admin_out(admin)


class PasswordAndCode(BaseModel):
    password: str
    code: str


@router.post("/me/2fa/disable")
def twofa_disable(payload: PasswordAndCode, db: Session = Depends(get_db),
                  admin: models.AdminUser = Depends(get_current_admin)):
    if not admin.totp_enabled:
        raise HTTPException(400, "Two-factor login is not on")
    if not security.check_password(payload.password, admin.password_hash):
        raise HTTPException(400, "Password is wrong")
    if not pyotp.TOTP(admin.totp_secret).verify(payload.code.strip(), valid_window=1):
        raise HTTPException(400, "That code is not right")
    admin.totp_secret, admin.totp_enabled = None, False
    audit(db, admin, "admin.2fa_disabled", "admin", admin.id)
    db.commit()
    return _admin_out(admin)
