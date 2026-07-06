"""Autenticación: login (OAuth2 password flow), refresh, /me y /logout."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..core.ratelimit import limiter
from ..core.security import (
    MAX_CONCURRENT_SESSIONS,
    create_access_token,
    create_refresh_token,
    decode_token,
    new_jti,
    verify_password,
)
from ..database import get_db
from ..models.rbac import User, UserSession
from ..schemas.auth import RefreshRequest, Token, UserMe

router = APIRouter(prefix="/api/auth", tags=["auth"])


_SESSIONS_BY_PROFILE: dict[str, int] = {
    "preview": 3,
}

_SESSION_TTL_BY_PROFILE: dict[str, timedelta] = {
    "preview": timedelta(days=1),
}


def _issue_tokens(user: User, db: Session, user_agent: str = "") -> Token:
    """Genera tokens y registra la sesión. Expulsa la más antigua si hay >= MAX sesiones."""
    profile_name = user.profile.name if user.profile else ""
    limit = _SESSIONS_BY_PROFILE.get(profile_name, MAX_CONCURRENT_SESSIONS)
    sessions = (
        db.query(UserSession)
        .filter(UserSession.user_id == user.id)
        .order_by(UserSession.created_at.asc())
        .all()
    )
    while len(sessions) >= limit:
        db.delete(sessions.pop(0))

    jti = new_jti()
    now = datetime.now(timezone.utc)
    ttl = _SESSION_TTL_BY_PROFILE.get(profile_name)
    db.add(UserSession(
        user_id=user.id,
        jti=jti,
        last_seen=now,
        user_agent=user_agent[:255],
        expires_at=now + ttl if ttl else None,
    ))
    db.commit()

    perms = sorted(user.permission_keys)
    return Token(
        access_token=create_access_token(user.username, perms, user.profile.name, jti),
        refresh_token=create_refresh_token(user.username, jti),
    )


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Usuario desactivado"
        )
    user.last_login = datetime.now(timezone.utc)
    ua = request.headers.get("user-agent", "")
    return _issue_tokens(user, db, ua)


@router.post("/refresh", response_model=Token)
def refresh(request: Request, body: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    try:
        payload = decode_token(body.refresh_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Refresh token inválido")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="El token no es de refresco")

    old_jti = payload.get("jti")
    if old_jti:
        old = db.query(UserSession).filter(UserSession.jti == old_jti).first()
        if old:
            db.delete(old)

    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario inválido")

    ua = request.headers.get("user-agent", "")
    return _issue_tokens(user, db, ua)


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    try:
        payload = decode_token(token)
        jti = payload.get("jti")
        if jti:
            db.query(UserSession).filter(UserSession.jti == jti).delete()
            db.commit()
    except jwt.PyJWTError:
        pass


@router.get("/me", response_model=UserMe)
def me(user: User = Depends(get_current_user)) -> UserMe:
    return UserMe(
        id=user.id,
        username=user.username,
        email=user.email,
        profile=user.profile.name,
        permissions=sorted(user.permission_keys),
    )
