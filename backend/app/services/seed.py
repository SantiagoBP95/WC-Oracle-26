"""Inicialización idempotente de la base de datos.

Crea las tablas, los permisos, los perfiles por defecto, el usuario admin semilla
y los equipos + partidos de fase de grupos a partir de data/seed/wc2026.json.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, inspect, text
from sqlalchemy.orm import Session

from ..config import settings
from ..core.rbac import DEFAULT_PROFILES, PERMISSIONS
from ..core.security import hash_password
from ..database import Base, engine
from ..models.football import Match, Team
from ..models.rbac import Permission, Profile, User

SEED_PATH = Path("data/seed/wc2026.json")
# 6 partidos por grupo (índices locales 0..3). Coincide con el simulador.
GROUP_PAIRINGS = [(0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2)]


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_schema()


def _ensure_schema() -> None:
    """Migración ligera idempotente para BD existentes (sin Alembic)."""
    insp = inspect(engine)
    tables = insp.get_table_names()
    if "matches" in tables:
        cols = {c["name"] for c in insp.get_columns("matches")}
        if "winner_team_id" not in cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE matches ADD COLUMN winner_team_id INTEGER"))
    # Tabla de sesiones concurrentes (max 2 por usuario).
    if "user_sessions" not in tables:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    jti TEXT NOT NULL UNIQUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_agent TEXT DEFAULT ''
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_sessions_user_id ON user_sessions(user_id)"))
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_user_sessions_jti ON user_sessions(jti)"))
    # Tabla de jugadores (StatsBomb + FBref).
    if "players" not in tables:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE players (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    team_id INTEGER REFERENCES teams(id),
                    nationality TEXT DEFAULT '',
                    position TEXT DEFAULT 'FW',
                    sot_per_90 REAL DEFAULT 0.0,
                    shots_per_90 REAL DEFAULT 0.0,
                    minutes_played INTEGER DEFAULT 0,
                    source TEXT DEFAULT '',
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_players_team_id ON players(team_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_players_name ON players(name)"))

    # Migración: columna in_squad (TRUE por defecto para datos ya ingresados)
    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(players)")).fetchall()]
        if "in_squad" not in cols:
            conn.execute(text("ALTER TABLE players ADD COLUMN in_squad INTEGER NOT NULL DEFAULT 1"))


def seed_permissions(db: Session) -> dict[str, Permission]:
    existing = {p.key: p for p in db.query(Permission).all()}
    for key, desc in PERMISSIONS.items():
        if key not in existing:
            perm = Permission(key=key, description=desc)
            db.add(perm)
            existing[key] = perm
    db.flush()
    return existing


def seed_profiles(db: Session, perms: dict[str, Permission]) -> None:
    for name, (desc, perm_keys, max_users, is_system) in DEFAULT_PROFILES.items():
        profile = db.query(Profile).filter(Profile.name == name).first()
        if profile is None:
            profile = Profile(
                name=name, description=desc, max_users=max_users, is_system=is_system
            )
            profile.permissions = [perms[k] for k in perm_keys if k in perms]
            db.add(profile)
    db.flush()


def seed_admin(db: Session) -> None:
    admin_profile = db.query(Profile).filter(Profile.name == "admin").first()
    if admin_profile is None:
        return
    exists = db.query(User).filter(User.username == settings.admin_username).first()
    if exists is None:
        db.add(
            User(
                username=settings.admin_username,
                email=settings.admin_email,
                password_hash=hash_password(settings.admin_password),
                profile_id=admin_profile.id,
                is_active=True,
            )
        )
    db.flush()


def seed_teams_and_matches(db: Session, seed_path: Path = SEED_PATH) -> None:
    if db.query(func.count(Team.id)).scalar():
        return  # ya sembrado
    data = json.loads(seed_path.read_text(encoding="utf-8"))

    team_by_name: dict[str, Team] = {}
    for label, members in data["groups"].items():
        for t in members:
            team = Team(
                name=t["name"],
                display_name=t.get("display", t["name"]),
                code=t.get("code", ""),
                confederation=t.get("confederation", ""),
                is_host=bool(t.get("host", False)),
                group_label=label,
            )
            db.add(team)
            team_by_name[t["name"]] = team
    db.flush()

    for label, members in data["groups"].items():
        names = [t["name"] for t in members]
        for i, j in GROUP_PAIRINGS:
            db.add(
                Match(
                    stage="group",
                    group_label=label,
                    is_neutral=True,
                    status="scheduled",
                    home_team_id=team_by_name[names[i]].id,
                    away_team_id=team_by_name[names[j]].id,
                )
            )
    db.flush()


def initialize_database(db: Session) -> None:
    """Punto de entrada: crea tablas y siembra todo lo necesario (idempotente)."""
    create_tables()
    perms = seed_permissions(db)
    seed_profiles(db, perms)
    seed_admin(db)
    seed_teams_and_matches(db)
    db.commit()


def run_player_ingestion(db: Session) -> dict:
    """Lanza la ingesta de jugadores (StatsBomb + FBref). Llamable desde el endpoint admin."""
    from ..ingest.player_stats import run_ingestion
    return run_ingestion(db)
