"""Modelos ORM. Importar todo aquí asegura que se registren en Base.metadata."""
from .football import (
    Match,
    Player,
    Prediction,
    RatingSnapshot,
    SimulationRun,
    Team,
    TeamAdvanceProb,
)
from .rbac import AuditLog, Permission, Profile, User, UserSession, profile_permissions

__all__ = [
    "AuditLog",
    "Permission",
    "Profile",
    "User",
    "UserSession",
    "profile_permissions",
    "Team",
    "Match",
    "Player",
    "Prediction",
    "SimulationRun",
    "TeamAdvanceProb",
    "RatingSnapshot",
]
