"""Control de acceso basado en permisos (RBAC) y validación de cupos por perfil."""
from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.rbac import Profile, User
from .deps import get_current_user

# Catálogo de permisos disponibles (clave -> descripción).
PERMISSIONS: dict[str, str] = {
    "view_dashboard": "Ver dashboard y predicciones",
    "view_models": "Ver detalle y comparativa de modelos",
    "run_simulation": "Ejecutar simulaciones Monte Carlo",
    "record_result": "Registrar y editar resultados de partidos",
    "manage_users": "Crear, editar y eliminar usuarios",
    "manage_profiles": "Crear y editar perfiles y sus permisos",
}

# Perfiles por defecto que se crean al inicializar (nombre -> (descripción, permisos, max_users, is_system)).
DEFAULT_PROFILES: dict[str, tuple[str, list[str], int | None, bool]] = {
    "admin": ("Administrador del sistema", list(PERMISSIONS.keys()), None, True),
    "analyst": (
        "Analista: consulta y ejecuta simulaciones",
        ["view_dashboard", "view_models", "run_simulation", "record_result"],
        5,
        False,
    ),
    "viewer": ("Cliente de solo lectura", ["view_dashboard"], 50, False),
    "preview": (
        "Vista previa gratuita — solo Dashboard y predicción del próximo partido",
        ["view_dashboard"],
        200,
        False,
    ),
}


def require_permission(key: str) -> Callable[..., User]:
    """Dependencia que exige un permiso concreto; devuelve 403 si falta."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if key not in user.permission_keys:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permiso requerido: {key}",
            )
        return user

    return checker


def ensure_profile_capacity(db: Session, profile: Profile, adding: int = 1) -> None:
    """Valida el cupo del perfil; lanza 409 si se superaría `max_users`."""
    if profile.max_users is None:
        return
    current = db.query(func.count(User.id)).filter(User.profile_id == profile.id).scalar() or 0
    if current + adding > profile.max_users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"El perfil '{profile.name}' alcanzó su cupo máximo "
                f"({profile.max_users} usuarios)."
            ),
        )
