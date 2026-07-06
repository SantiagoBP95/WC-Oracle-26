"""Métricas de rendimiento del modelo: precisión, Brier score y detalle por partido."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..core.rbac import require_permission
from ..database import get_db
from ..models.football import Match, Prediction
from ..models.rbac import User

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("")
def get_metrics(
    model: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("view_dashboard")),
):
    req_model = model if model and model not in ("elo",) else "dixon_coles"
    rows = (
        db.query(Match, Prediction)
        .join(Prediction, Prediction.match_id == Match.id)
        .filter(Match.status == "finished", Prediction.model_name == req_model)
        .all()
    )
    if not rows:
        rows = (
            db.query(Match, Prediction)
            .join(Prediction, Prediction.match_id == Match.id)
            .filter(Match.status == "finished", Prediction.model_name == "dixon_coles")
            .all()
        )

    matches = []
    for m, pred in rows:
        hs, as_ = m.home_score, m.away_score
        if hs > as_:
            actual, p_correct = "home", pred.p_home
        elif hs < as_:
            actual, p_correct = "away", pred.p_away
        else:
            actual, p_correct = "draw", pred.p_draw

        if pred.p_home >= pred.p_draw and pred.p_home >= pred.p_away:
            predicted = "home"
        elif pred.p_away >= pred.p_draw:
            predicted = "away"
        else:
            predicted = "draw"

        brier = (
            (pred.p_home - (1 if actual == "home" else 0)) ** 2
            + (pred.p_draw - (1 if actual == "draw" else 0)) ** 2
            + (pred.p_away - (1 if actual == "away" else 0)) ** 2
        ) / 3

        real_scoreline = f"{hs}-{as_}"
        scoreline_correct = pred.top_scoreline == real_scoreline if pred.top_scoreline else False

        matches.append({
            "match_id": m.id,
            "home": m.home_team.display_name if m.home_team else "?",
            "away": m.away_team.display_name if m.away_team else "?",
            "home_score": hs,
            "away_score": as_,
            "stage": m.stage,
            "predicted": predicted,
            "actual": actual,
            "correct": actual == predicted,
            "top_scoreline": pred.top_scoreline or "—",
            "scoreline_correct": scoreline_correct,
            "p_correct": round(p_correct, 3),
            "p_home": round(pred.p_home, 3),
            "p_draw": round(pred.p_draw, 3),
            "p_away": round(pred.p_away, 3),
            "exp_home": round(pred.exp_home_goals, 2),
            "exp_away": round(pred.exp_away_goals, 2),
            "brier": round(brier, 4),
        })

    n = len(matches)
    if n == 0:
        return {"total": 0, "correct": 0, "accuracy": None,
                "avg_brier": None, "avg_p_correct": None, "matches": []}

    n_correct = sum(1 for r in matches if r["correct"])
    n_scoreline = sum(1 for r in matches if r["scoreline_correct"])
    return {
        "total": n,
        "correct": n_correct,
        "accuracy": round(n_correct / n, 4),
        "scoreline_correct": n_scoreline,
        "scoreline_accuracy": round(n_scoreline / n, 4),
        "avg_brier": round(sum(r["brier"] for r in matches) / n, 4),
        "avg_p_correct": round(sum(r["p_correct"] for r in matches) / n, 4),
        "matches": sorted(matches, key=lambda x: x["match_id"]),
    }
