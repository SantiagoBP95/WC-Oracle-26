"""Dependencias de FastAPI: usuario autenticado a partir del token JWT."""
from __future__ import annotations

from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.rbac import User, UserSession
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    try:
        payload = decode_token(token)
    except jwt.PyJWTError:
        raise _credentials_exc
    if payload.get("type") != "access":
        raise _credentials_exc
    username = payload.get("sub")
    jti = payload.get("jti")
    if not username or not jti:
        raise _credentials_exc

    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active:
        raise _credentials_exc

    session = db.query(UserSession).filter(UserSession.jti == jti).first()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión cerrada o expirada",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now = datetime.now(timezone.utc)
    if session.expires_at is not None and session.expires_at.replace(tzinfo=timezone.utc) < now:
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada. Vuelve a iniciar sesión.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session.last_seen = now
    db.commit()

    return user
