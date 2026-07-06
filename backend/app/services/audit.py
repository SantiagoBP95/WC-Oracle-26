"""Registro de auditoría de acciones sensibles."""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models.rbac import AuditLog


def log_action(db: Session, user_id: int | None, action: str, detail: str = "") -> None:
    db.add(AuditLog(user_id=user_id, action=action, detail=detail))
    db.commit()
