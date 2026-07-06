"""Schemas de RBAC (permisos, perfiles, usuarios)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PermissionOut(BaseModel):
    key: str
    description: str


# ---- Perfiles ----
class ProfileCreate(BaseModel):
    name: str = Field(min_length=2, max_length=64)
    description: str = ""
    max_users: int | None = Field(default=None, ge=1)  # None = ilimitado
    permissions: list[str] = []


class ProfileUpdate(BaseModel):
    description: str | None = None
    max_users: int | None = Field(default=None, ge=1)
    permissions: list[str] | None = None


class ProfileOut(BaseModel):
    id: int
    name: str
    description: str
    max_users: int | None
    is_system: bool
    permissions: list[str]
    user_count: int


# ---- Usuarios ----
class UserCreate(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=6, max_length=128)
    email: str = ""
    profile: str  # nombre del perfil


class UserUpdate(BaseModel):
    email: str | None = None
    profile: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    profile: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None
