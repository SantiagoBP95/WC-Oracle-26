"""Simulaciones Monte Carlo: última corrida, ejecutar nueva y evolución temporal."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.rbac import require_permission
from ..database import get_db
from ..models.football import SimulationRun, Team, TeamAdvanceProb
from ..models.rbac import User
from ..schemas.football import (
    BayesStrengthOut,
    ModelInfo,
    SimulationOut,
    SimulationRunRequest,
    TeamProbOut,
)
from ..services.modeling import (
    available_models,
    bayesian_team_strength,
    run_simulation,
    train_ml_models,
)

router = APIRouter(prefix="/api/simulations", tags=["simulations"])

MODEL_LABELS = {
    "elo": "Elo + Dixon-Coles",
    "xgboost": "XGBoost",
    "nn": "Red neuronal",
    "bayesian": "Bayesiano (PyMC)",
}


class EvolutionPoint(BaseModel):
    run_id: int
    created_at: datetime
    p_advance: float
    p_winner: float
    p_final: float


def _sim_out(db: Session, run: SimulationRun) -> SimulationOut:
    rows = (
        db.query(TeamAdvanceProb, Team)
        .join(Team, TeamAdvanceProb.team_id == Team.id)
        .filter(TeamAdvanceProb.run_id == run.id)
        .all()
    )
    probs = [
        TeamProbOut(
            team=t.name,
            display_name=t.display_name,
            code=t.code,
            confederation=t.confederation,
            group_label=t.group_label,
            p_group_winner=round(tp.p_group_winner, 4),
            p_group_runner_up=round(tp.p_group_runner_up, 4),
            p_advance=round(tp.p_advance, 4),
            p_r16=round(tp.p_r16, 4),
            p_qf=round(tp.p_qf, 4),
            p_sf=round(tp.p_sf, 4),
            p_final=round(tp.p_final, 4),
            p_winner=round(tp.p_winner, 4),
        )
        for tp, t in rows
    ]
    probs.sort(key=lambda p: p.p_winner, reverse=True)
    return SimulationOut(
        id=run.id,
        created_at=run.created_at,
        runs=run.runs,
        model_name=run.model_name,
        notes=run.notes,
        probs=probs,
    )


@router.get("/models", response_model=list[ModelInfo])
def list_models(
    db: Session = Depends(get_db), _: User = Depends(require_permission("view_dashboard"))
):
    """Modelos disponibles y si ya tienen alguna simulación."""
    avail = set(available_models())
    with_runs = {m[0] for m in db.query(SimulationRun.model_name).distinct().all()}
    return [
        ModelInfo(name=name, label=label, available=name in avail, has_run=name in with_runs)
        for name, label in MODEL_LABELS.items()
    ]


@router.get("/compare", response_model=list[SimulationOut])
def compare_models(
    db: Session = Depends(get_db), _: User = Depends(require_permission("view_models"))
):
    """Última simulación de cada modelo disponible, para comparar lado a lado."""
    out = []
    for name in available_models():
        run = (
            db.query(SimulationRun)
            .filter(SimulationRun.model_name == name)
            .order_by(SimulationRun.id.desc())
            .first()
        )
        if run is not None:
            out.append(_sim_out(db, run))
    return out


@router.get("/bayesian-strength", response_model=list[BayesStrengthOut])
def bayesian_strength(
    db: Session = Depends(get_db), _: User = Depends(require_permission("view_models"))
):
    """Fuerza att/def por equipo con intervalos de credibilidad (modelo bayesiano)."""
    data = bayesian_team_strength(db)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail="El modelo bayesiano no está entrenado (python -m ml.train --bayes).",
        )
    return data


@router.get("/latest", response_model=SimulationOut)
def latest_simulation(
    model: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("view_dashboard")),
):
    q = db.query(SimulationRun)
    if model:
        q = q.filter(SimulationRun.model_name == model)
    run = q.order_by(SimulationRun.id.desc()).first()
    if run is None:
        raise HTTPException(status_code=404, detail="Aún no hay simulaciones para ese modelo.")
    return _sim_out(db, run)


@router.post("/run", response_model=SimulationOut)
def run_new_simulation(
    body: SimulationRunRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("run_simulation")),
):
    if body.model not in available_models():
        raise HTTPException(
            status_code=400,
            detail=f"Modelo '{body.model}' no disponible. Entrena primero (python -m ml.train --models).",
        )
    run = run_simulation(db, runs=body.runs, notes=body.notes or "manual", model_name=body.model)
    return _sim_out(db, run)


@router.post("/train-models")
def train_models_endpoint(
    db: Session = Depends(get_db), _: User = Depends(require_permission("run_simulation"))
):
    """Entrena los modelos ML (XGBoost, NN) y corre una simulación de cada uno."""
    trained = train_ml_models()
    for name in trained:
        run_simulation(db, notes=f"entrenamiento {name}", model_name=name)
    return {"trained": trained}


@router.get("/evolution", response_model=list[EvolutionPoint])
def team_evolution(
    team: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("view_dashboard")),
):
    """Evolución de las probabilidades de un equipo a través de las corridas."""
    team_obj = db.query(Team).filter(Team.name == team).first()
    if team_obj is None:
        raise HTTPException(status_code=404, detail="Equipo no encontrado")
    rows = (
        db.query(TeamAdvanceProb, SimulationRun)
        .join(SimulationRun, TeamAdvanceProb.run_id == SimulationRun.id)
        .filter(TeamAdvanceProb.team_id == team_obj.id)
        .order_by(SimulationRun.id)
        .all()
    )
    return [
        EvolutionPoint(
            run_id=run.id,
            created_at=run.created_at,
            p_advance=round(tp.p_advance, 4),
            p_winner=round(tp.p_winner, 4),
            p_final=round(tp.p_final, 4),
        )
        for tp, run in rows
    ]
