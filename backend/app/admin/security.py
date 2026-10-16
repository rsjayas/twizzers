"""
Admin dashboard authentication and permissions.

Admins are separate from app users: email + password (bcrypt), a short-lived
signed token (HS256, ADMIN_JWT_SECRET), and one of three roles. Create the
first admin with `python -m app.admin.cli create-admin`.
"""
import datetime as dt
import os
import time
from collections import defaultdict, deque

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db

TOKEN_HOURS = 8
ROLES = ("superadmin", "support", "content")

# permission -> roles that have it
PERMISSIONS = {
    "adjust_credits": {"superadmin", "support"},
    "retry_render": {"superadmin", "support"},
    "takedown": {"superadmin", "support"},
    "manage_content": {"superadmin", "content"},
    "manage_settings": {"superadmin"},
    "manage_admins": {"superadmin"},
    "view_audit": {"superadmin"},
}


def _secret() -> str:
    secret = os.getenv("ADMIN_JWT_SECRET", "")
    if len(secret) < 16:
        raise HTTPException(503, "Admin dashboard is not configured (set ADMIN_JWT_SECRET, 16+ characters)")
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(admin: models.AdminUser) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    return jwt.encode(
        {"sub": admin.id, "role": admin.role, "iat": now, "exp": now + dt.timedelta(hours=TOKEN_HOURS)},
        _secret(),
        algorithm="HS256",
    )


# --- login throttling (in memory: per process, resets on restart) ---
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 15 * 60
_failures: dict[str, deque] = defaultdict(deque)


def _recent_failures(key: str) -> deque:
    q = _failures[key]
    cutoff = time.time() - _WINDOW_SECONDS
    while q and q[0] < cutoff:
        q.popleft()
    return q


def check_login_allowed(*keys: str) -> None:
    if any(len(_recent_failures(k)) >= _MAX_ATTEMPTS for k in keys):
        raise HTTPException(429, "Too many failed attempts. Try again in 15 minutes.")


def record_login_failure(*keys: str) -> None:
    for k in keys:
        _failures[k].append(time.time())


def clear_login_failures(*keys: str) -> None:
    for k in keys:
        _failures.pop(k, None)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_current_admin(authorization: str = Header(default=""), db: Session = Depends(get_db)) -> models.AdminUser:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "Missing token")
    try:
        claims = jwt.decode(token, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    admin = db.query(models.AdminUser).filter(models.AdminUser.id == claims.get("sub")).first()
    # Role and active flag are read from the database on every request, so a
    # demoted or disabled admin loses access immediately.
    if not admin or not admin.is_active:
        raise HTTPException(401, "Account disabled")
    return admin


def require(permission: str):
    def dependency(admin: models.AdminUser = Depends(get_current_admin)) -> models.AdminUser:
        if admin.role not in PERMISSIONS[permission]:
            raise HTTPException(403, "Your role cannot do this")
        return admin

    return dependency


def audit(db: Session, admin: models.AdminUser, action: str, target_type: str | None = None,
          target_id: str | None = None, details: dict | None = None) -> None:
    """Adds an audit row to the current transaction (committed with the change)."""
    db.add(models.AuditLog(admin_id=admin.id, admin_email=admin.email, action=action,
                           target_type=target_type, target_id=target_id, details=details or {}))
