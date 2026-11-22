from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from .config import settings

ALGORITHM = "HS256"
password_hash = PasswordHash((Argon2Hasher(),))

# Verifying against a real Argon2 hash when the account does not exist keeps
# the login response time identical for unknown emails (no user enumeration).
DUMMY_HASH = password_hash.hash("timing-equalization-dummy-password")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return password_hash.verify(password, hashed)
    except Exception:
        return False


def create_access_token(user_id: int, token_version: int) -> tuple[str, int]:
    expires_in = settings.access_token_minutes * 60
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "tv": token_version, "jti": uuid4().hex, "iat": now, "exp": now + timedelta(seconds=expires_in)}
    return jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM), expires_in


def decode_access_token(token: str) -> tuple[int, int]:
    """Return (user_id, token_version). Raises jwt.InvalidTokenError when invalid."""
    payload = jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
    subject = payload.get("sub")
    version = payload.get("tv")
    if not isinstance(subject, str) or not subject.isdigit():
        raise jwt.InvalidTokenError("Invalid subject")
    if not isinstance(version, int):
        raise jwt.InvalidTokenError("Missing token version")
    return int(subject), version
