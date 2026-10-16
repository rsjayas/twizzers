"""
Admin dashboard API (served under /admin/api). Every route needs an admin
token; changes are role-checked and written to the audit log.
"""
import datetime as dt
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_
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


def _admin_out(a: models.AdminUser) -> dict:
    return {
        "id": a.id,
        "email": a.email,
        "role": a.role,
        "is_active": a.is_active,
        "created_at": _iso(a.created_at),
        "last_login_at": _iso(a.last_login_at),
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
        "revenue_inr": _daily(db, models.CreditTransaction.paid_at, since,
                              models.CreditTransaction.status == "paid", models.CreditTransaction.amount_inr),
    }
    dates = [str(today - dt.timedelta(days=days - 1 - i)) for i in range(days)]
    daily = [{"date": d, **{k: v.get(d, 0) for k, v in series.items()}} for d in dates]

    by_status = dict(db.query(models.Creation.status, func.count()).group_by(models.Creation.status).all())
    revenue = db.query(func.coalesce(func.sum(models.CreditTransaction.amount_inr), 0)).filter(
        models.CreditTransaction.status == "paid").scalar()
    return {
        "totals": {
            "users": db.query(func.count(models.User.id)).scalar(),
            "poems": db.query(func.count(models.Poem.id)).scalar(),
            "creations": db.query(func.count(models.Creation.id)).scalar(),
            "shares": db.query(func.count(models.Share.id)).scalar(),
            "revenue_inr": int(revenue),
            "credits_outstanding": int(db.query(func.coalesce(func.sum(models.User.credits_balance), 0)).scalar()),
        },
        "creations_by_status": by_status,
        "daily": daily,
    }


# --------------------------------------------------------------- users

def _user_out(u: models.User) -> dict:
    return {"id": u.id, "name": u.name, "phone": u.phone, "email": u.email,
            "providers": sorted({i.provider for i in u.identities}), "credits_balance": u.credits_balance or 0,
            "created_at": _iso(u.created_at)}


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


class Reason(BaseModel):
    reason: str = Field(..., min_length=3, max_length=200)


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
def list_audit(limit: int = 50, offset: int = 0, db: Session = Depends(get_db),
               admin: models.AdminUser = Depends(require("view_audit"))):
    limit, offset = _page(limit, offset)
    query = db.query(models.AuditLog)
    total = query.count()
    rows = query.order_by(models.AuditLog.created_at.desc()).limit(limit).offset(offset).all()
    return {"total": total, "items": [
        {"id": r.id, "admin_email": r.admin_email, "action": r.action, "target_type": r.target_type,
         "target_id": r.target_id, "details": r.details, "created_at": _iso(r.created_at)} for r in rows]}
