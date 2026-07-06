"""Primitivas de seguridad: hashing de contraseñas (bcrypt) y tokens JWT."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from ..config import settings

ALGORITHM = "HS256"
_BCRYPT_MAX_BYTES = 72  # límite de bcrypt
MAX_CONCURRENT_SESSIONS = 1


def hash_password(password: str) -> str:
    payload = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(payload, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        payload = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(payload, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def new_jti() -> str:
    return uuid.uuid4().hex


def _create_token(subject: str, extra: dict[str, Any], expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + expires_delta, **extra}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_access_token(username: str, permissions: list[str], profile: str, jti: str) -> str:
    return _create_token(
        username,
        {"type": "access", "perms": permissions, "profile": profile, "jti": jti},
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(username: str, jti: str) -> str:
    return _create_token(
        username,
        {"type": "refresh", "jti": jti},
        timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
