"""
Admin management from the command line (there is deliberately no default admin).

    python -m app.admin.cli create-admin you@example.com superadmin
    python -m app.admin.cli reset-password you@example.com
"""
import getpass
import sys

from ..database import SessionLocal
from .. import models
from .security import ROLES, hash_password


def _password() -> str:
    pw = getpass.getpass("Password (min 10 chars): ")
    if len(pw) < 10:
        sys.exit("Password too short.")
    if pw != getpass.getpass("Repeat: "):
        sys.exit("Passwords do not match.")
    return pw


def main(argv: list[str]) -> None:
    if len(argv) >= 3 and argv[0] == "create-admin":
        email, role = argv[1].strip().lower(), argv[2]
        if role not in ROLES:
            sys.exit(f"Role must be one of: {', '.join(ROLES)}")
        db = SessionLocal()
        if db.query(models.AdminUser).filter(models.AdminUser.email == email).first():
            sys.exit("An admin with that email already exists.")
        db.add(models.AdminUser(email=email, role=role, password_hash=hash_password(_password())))
        db.commit()
        print(f"Created {role} {email}")
    elif len(argv) >= 2 and argv[0] == "reset-password":
        db = SessionLocal()
        admin = db.query(models.AdminUser).filter(models.AdminUser.email == argv[1].strip().lower()).first()
        if not admin:
            sys.exit("No such admin.")
        admin.password_hash = hash_password(_password())
        db.commit()
        print("Password updated.")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
