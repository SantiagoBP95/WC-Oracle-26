"""Partidos: listado con predicciones, registro de resultados y sync en vivo."""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.rbac import require_permission
from ..database import get_db
from ..models.football import Match, Prediction, Team
from ..models.rbac import User
from ..schemas.football import MatchOut, MatchResultIn, PredictionOut, TeamRef
from ..services.audit import log_action
from ..services.knockouts import materialize_knockouts
from ..services.livesync import LiveSyncError, sync_from_api
from ..services.modeling import generate_all_predictions, recalc_all

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _team_ref(t: Team | None) -> TeamRef | None:
    if t is None:
        return None
    return TeamRef(id=t.id, name=t.name, display_name=t.display_name, code=t.code)


def _match_out(m: Match, teams: dict[int, Team], pred: Prediction | None) -> MatchOut:
    prediction = None
    if pred is not None:
        prediction = PredictionOut(
            model_name=pred.model_name,
            p_home=round(pred.p_home, 4),
            p_draw=round(pred.p_draw, 4),
            p_away=round(pred.p_away, 4),
            exp_home_goals=round(pred.exp_home_goals, 2),
            exp_away_goals=round(pred.exp_away_goals, 2),
            top_scoreline=pred.top_scoreline,
        )
    return MatchOut(
        id=m.id,
        stage=m.stage,
        group_label=m.group_label,
        slot=m.slot,
        home_team=_team_ref(teams.get(m.home_team_id)),
        away_team=_team_ref(teams.get(m.away_team_id)),
        scheduled_at=m.scheduled_at,
        venue=m.venue,
        is_neutral=m.is_neutral,
        status=m.status,
        home_score=m.home_score,
        away_score=m.away_score,
        winner_team_id=m.winner_team_id,
        prediction=prediction,
    )


@router.get("", response_model=list[MatchOut])
def list_matches(
    stage: str | None = None,
    group: str | None = None,
    model: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("view_dashboard")),
):
    q = db.query(Match)
    if stage:
        q = q.filter(Match.stage == stage)
    if group:
        q = q.filter(Match.group_label == group)
    matches = q.order_by(Match.group_label, Match.id).all()
    teams = {t.id: t for t in db.query(Team).all()}

    # Selecciona predicciones del modelo pedido; fallback a dixon_coles si no hay
    req = model if model and model not in ("elo",) else "dixon_coles"
    all_preds = db.query(Prediction).filter(Prediction.model_name == req).all()
    if not all_preds:
        all_preds = db.query(Prediction).filter(Prediction.model_name == "dixon_coles").all()
    preds = {p.match_id: p for p in all_preds}

    return [_match_out(m, teams, preds.get(m.id)) for m in matches]


@router.post("/{match_id}/result", response_model=MatchOut)
def record_result(
    match_id: int,
    body: MatchResultIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("record_result")),
):
    if body.home_score < 0 or body.away_score < 0:
        raise HTTPException(status_code=422, detail="Los marcadores no pueden ser negativos")
    m = db.get(Match, match_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Partido no encontrado")

    # En eliminatorias, un empate en el 90' requiere indicar el ganador (penaltis).
    is_knockout = m.stage != "group"
    if is_knockout and body.home_score == body.away_score:
        if body.winner not in ("home", "away"):
            raise HTTPException(
                status_code=422,
                detail="En eliminatorias, si hay empate indica el ganador (penaltis): 'home' o 'away'.",
            )
        m.winner_team_id = m.home_team_id if body.winner == "home" else m.away_team_id
    else:
        m.winner_team_id = None

    m.home_score = body.home_score
    m.away_score = body.away_score
    m.status = "finished"
    db.commit()
    log_action(
        db, user.id, "record_result", f"match {match_id}: {body.home_score}-{body.away_score}"
    )

    # Materializa/avanza las eliminatorias, regenera predicciones y recalcula simulaciones.
    materialize_knockouts(db)
    recalc_all(db, notes=f"recálculo tras partido {match_id}")

    teams = {t.id: t for t in db.query(Team).all()}
    pred = db.query(Prediction).filter(
        Prediction.match_id == m.id, Prediction.model_name == "dixon_coles"
    ).first()
    return _match_out(m, teams, pred)


@router.post("/sync")
def sync_results(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission("record_result")),
):
    """Sincroniza resultados desde API-Football y recalcula si hubo cambios."""
    try:
        result = sync_from_api(db)
    except LiveSyncError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Error consultando API-Football: {e}")
    log_action(db, user.id, "sync_api", str(result))
    return result
