"""Promote (or demote) an existing BILLOMADFX account to administrator.

Run from the backend directory (or point DATABASE_URL at the target database):

    python make_admin.py user@example.com            # promote to admin
    python make_admin.py user@example.com --revoke   # back to regular user
    python make_admin.py --list                      # show all accounts

Administrators can view the Administration page and the audit log endpoint.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy.exc import OperationalError  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import User  # noqa: E402

UNINITIALIZED = "The database has no tables yet. Start the server once (uvicorn app.main:app) to create them, then run this command again."


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in {"-h", "--help"}:
        print(__doc__)
        return 0
    if args[0] == "--list":
        db = SessionLocal()
        try:
            users = db.query(User).order_by(User.id).all()
        except OperationalError:
            print(UNINITIALIZED)
            return 1
        finally:
            db.close()
        if not users:
            print("No accounts yet.")
        for user in users:
            print(f"{user.id:>4}  {user.role:<8}  {user.email}")
        return 0

    email = args[0].strip().lower()
    revoke = "--revoke" in args[1:]
    db = SessionLocal()
    try:
        try:
            user = db.query(User).filter(User.email == email).one_or_none()
        except OperationalError:
            print(UNINITIALIZED)
            return 1
        if user is None:
            print(f"Error: no account with email {email!r}. Create it in the app first, then promote it.")
            return 1
        user.role = "user" if revoke else "admin"
        db.commit()
        action = "demoted to regular user" if revoke else "promoted to administrator"
        print(f"OK: {email} {action}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
