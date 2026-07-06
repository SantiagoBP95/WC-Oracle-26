"""Equipos participantes."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.rbac import require_permission
from ..database import get_db
from ..models.football import Team
from ..models.rbac import User
from ..schemas.football import TeamOut

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.get("", response_model=list[TeamOut])
def list_teams(
    db: Session = Depends(get_db), _: User = Depends(require_permission("view_dashboard"))
):
    teams = db.query(Team).order_by(Team.group_label, Team.name).all()
    return [
        TeamOut(
            id=t.id,
            name=t.name,
            display_name=t.display_name,
            code=t.code,
            confederation=t.confederation,
            group_label=t.group_label,
            is_host=t.is_host,
            elo=round(t.elo, 1),
        )
        for t in teams
    ]
