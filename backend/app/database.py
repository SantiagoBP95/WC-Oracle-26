"""Motor SQLAlchemy, sesión y Base declarativa."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

# Asegura que la carpeta de la BD SQLite exista antes de crear el engine.
if settings.database_url.startswith("sqlite"):
    db_path = settings.database_url.split("sqlite:///")[-1]
    Path(db_path).resolve().parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False}
else:
    connect_args = {}

engine = create_engine(settings.database_url, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base declarativa para todos los modelos ORM."""


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI que entrega una sesión por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
