"""Panel de administración (RBAC): usuarios, perfiles y permisos.

Aplica cupos por perfil (HTTP 409 al superar `max_users`) y protege contra el
bloqueo del sistema (no se queda sin administradores ni se borran perfiles del sistema).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.rbac import PERMISSIONS, ensure_profile_capacity, require_permission
from ..core.security import hash_password
from ..database import get_db
from ..models.football import Player, Team
from ..models.rbac import Permission, Profile, User
from ..schemas.rbac import (
    PermissionOut,
    ProfileCreate,
    ProfileOut,
    ProfileUpdate,
    UserCreate,
    UserOut,
    UserUpdate,
)
from ..services.audit import log_action

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------- Serializadores ----------
def _profile_out(db: Session, p: Profile) -> ProfileOut:
    count = db.query(func.count(User.id)).filter(User.profile_id == p.id).scalar() or 0
    return ProfileOut(
        id=p.id,
        name=p.name,
        description=p.description,
        max_users=p.max_users,
        is_system=p.is_system,
        permissions=sorted(p.permission_keys),
        user_count=count,
    )


def _user_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        username=u.username,
        email=u.email,
        profile=u.profile.name,
        is_active=u.is_active,
        created_at=u.created_at,
        last_login=u.last_login,
    )


def _resolve_permissions(db: Session, keys: list[str]) -> list[Permission]:
    unknown = [k for k in keys if k not in PERMISSIONS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Permisos desconocidos: {unknown}")
    return db.query(Permission).filter(Permission.key.in_(keys)).all()


# ---------- Permisos ----------
@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(_: User = Depends(require_permission("manage_profiles"))):
    return [PermissionOut(key=k, description=v) for k, v in PERMISSIONS.items()]


# ---------- Perfiles ----------
@router.get("/profiles", response_model=list[ProfileOut])
def list_profiles(
    db: Session = Depends(get_db), _: User = Depends(require_permission("manage_profiles"))
):
    return [_profile_out(db, p) for p in db.query(Profile).order_by(Profile.id).all()]


@router.post("/profiles", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(
    body: ProfileCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("manage_profiles")),
):
    if db.query(Profile).filter(Profile.name == body.name).first():
        raise HTTPException(status_code=409, detail="Ya existe un perfil con ese nombre")
    profile = Profile(
        name=body.name,
        description=body.description,
        max_users=body.max_users,
        is_system=False,
        permissions=_resolve_permissions(db, body.permissions),
    )
    db.add(profile)
    db.commit()
    log_action(db, admin.id, "create_profile", body.name)
    return _profile_out(db, profile)


@router.patch("/profiles/{profile_id}", response_model=ProfileOut)
def update_profile(
    profile_id: int,
    body: ProfileUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("manage_profiles")),
):
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    fields = body.model_dump(exclude_unset=True)

    if "permissions" in fields:
        if profile.is_system:
            raise HTTPException(
                status_code=403, detail="No se pueden cambiar los permisos de un perfil del sistema"
            )
        profile.permissions = _resolve_permissions(db, fields["permissions"])
    if "description" in fields:
        profile.description = fields["description"]
    if "max_users" in fields:
        profile.max_users = fields["max_users"]

    db.commit()
    log_action(db, admin.id, "update_profile", profile.name)
    return _profile_out(db, profile)


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("manage_profiles")),
):
    profile = db.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    if profile.is_system:
        raise HTTPException(status_code=403, detail="No se puede eliminar un perfil del sistema")
    if db.query(func.count(User.id)).filter(User.profile_id == profile.id).scalar():
        raise HTTPException(status_code=409, detail="El perfil tiene usuarios asignados")
    db.delete(profile)
    db.commit()
    log_action(db, admin.id, "delete_profile", profile.name)


# ---------- Usuarios ----------
@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db), _: User = Depends(require_permission("manage_users"))
):
    return [_user_out(u) for u in db.query(User).order_by(User.id).all()]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("manage_users")),
):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=409, detail="El nombre de usuario ya existe")
    profile = db.query(Profile).filter(Profile.name == body.profile).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Perfil no encontrado")
    ensure_profile_capacity(db, profile)  # 409 si el cupo está lleno

    user = User(
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        profile_id=profile.id,
        is_active=True,
    )
    db.add(user)
    db.commit()
    log_action(db, admin.id, "create_user", f"{body.username} -> {profile.name}")
    return _user_out(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("manage_users")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    fields = body.model_dump(exclude_unset=True)

    if "profile" in fields and fields["profile"] != user.profile.name:
        target = db.query(Profile).filter(Profile.name == fields["profile"]).first()
        if target is None:
            raise HTTPException(status_code=404, detail="Perfil destino no encontrado")
        ensure_profile_capacity(db, target)
        _guard_last_admin(db, user, leaving=True)
        user.profile_id = target.id
    if "email" in fields:
        user.email = fields["email"]
    if "is_active" in fields:
        if not fields["is_active"]:
            _guard_last_admin(db, user, leaving=True)
        user.is_active = fields["is_active"]
    if "password" in fields and fields["password"]:
        user.password_hash = hash_password(fields["password"])

    db.commit()
    log_action(db, admin.id, "update_user", user.username)
    return _user_out(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("manage_users")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    _guard_last_admin(db, user, leaving=True)
    db.delete(user)
    db.commit()
    log_action(db, admin.id, "delete_user", user.username)


@router.post("/ingest/players", tags=["admin"])
def ingest_players(
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("manage_users")),
):
    """Dispara la ingesta de estadísticas de jugadores desde StatsBomb y FBref.
    Puede tardar varios minutos la primera vez (descarga datos de partidos).
    """
    from ..services.seed import run_player_ingestion
    from ..services.audit import log_action

    result = run_player_ingestion(db)
    log_action(db, admin.id, "ingest_players", str(result))
    return result


@router.post("/sync/squads", tags=["admin"])
def sync_squads(
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("manage_users")),
):
    """Sincroniza las listas oficiales de convocados WC2026 desde football-data.org.
    Actualiza el campo in_squad de cada jugador en la DB.
    Requiere FOOTBALL_DATA_ORG_TOKEN en .env
    """
    try:
        import importlib.util, pathlib
        spec = importlib.util.spec_from_file_location(
            "sync_squads",
            pathlib.Path(__file__).parent.parent.parent.parent / "scripts" / "sync_squads.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        result = mod.sync(dry_run=False)
        log_action(db, admin.id, "sync_squads", str(result))
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/players", tags=["admin"])
def list_players(
    team_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("manage_users")),
):
    """Lista jugadores de la BD, opcionalmente filtrados por equipo."""
    q = db.query(Player)
    if team_id:
        q = q.filter(Player.team_id == team_id)
    players = q.order_by(Player.team_id, Player.sot_per_90.desc()).all()
    teams = {t.id: t.display_name for t in db.query(Team).all()}
    return [
        {
            "id": p.id,
            "name": p.name,
            "team_id": p.team_id,
            "team": teams.get(p.team_id, "—"),
            "position": p.position,
            "sot_per_90": round(p.sot_per_90, 2),
            "source": p.source,
        }
        for p in players
    ]


@router.delete("/players/{player_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["admin"])
def delete_player(
    player_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_permission("manage_users")),
):
    """Elimina un jugador de la BD (quitar de convocatoria)."""
    p = db.get(Player, player_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    db.delete(p)
    db.commit()
    from ..services.audit import log_action
    log_action(db, admin.id, "delete_player", f"player {player_id} ({p.name})")


def _guard_last_admin(db: Session, user: User, leaving: bool) -> None:
    """Impide dejar el sistema sin ningún administrador activo."""
    if "manage_users" not in user.permission_keys:
        return
    active_admins = (
        db.query(func.count(User.id))
        .join(Profile, User.profile_id == Profile.id)
        .join(Profile.permissions)
        .filter(Permission.key == "manage_users", User.is_active.is_(True))
        .scalar()
        or 0
    )
    if leaving and active_admins <= 1:
        raise HTTPException(
            status_code=409,
            detail="No se puede dejar el sistema sin administradores activos",
        )
