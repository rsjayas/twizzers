"""
Runtime settings editable from the admin dashboard.

Each setting has a default taken from the environment (so existing deployments
keep working); a row in the `settings` table overrides it without a redeploy.
"""
import os

from sqlalchemy.orm import Session

from . import models

# key -> (type, default from env)
DEFINITIONS = {
    "payments_enabled": ("bool", lambda: os.getenv("PAYMENTS_ENABLED", "false").lower() == "true"),
    "cost_per_story_credits": ("int", lambda: int(os.getenv("COST_PER_STORY_CREDITS", "5"))),
    "signups_enabled": ("bool", lambda: True),          # false: no new accounts (existing users keep working)
    "welcome_credits": ("int", lambda: 0),              # credits given to every new account
}


def _parse(kind: str, raw: str):
    if kind == "bool":
        return raw.lower() == "true"
    return int(raw)


def get_value(db: Session, key: str):
    kind, default = DEFINITIONS[key]
    row = db.query(models.Setting).filter(models.Setting.key == key).first()
    if row is None:
        return default()
    try:
        return _parse(kind, row.value)
    except ValueError:
        return default()


def all_values(db: Session) -> dict:
    return {key: get_value(db, key) for key in DEFINITIONS}


def validate(key: str, value) -> str:
    """Returns the string to store, or raises ValueError."""
    if key not in DEFINITIONS:
        raise ValueError(f"Unknown setting: {key}")
    kind, _ = DEFINITIONS[key]
    if kind == "bool":
        if not isinstance(value, bool):
            raise ValueError(f"{key} must be true or false")
        return "true" if value else "false"
    if isinstance(value, bool) or not isinstance(value, int) or not (0 <= value <= 1000):
        raise ValueError(f"{key} must be a whole number between 0 and 1000")
    return str(value)
