"""Schemas de dominio (equipos, partidos, predicciones, simulaciones)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TeamRef(BaseModel):
    id: int
    name: str
    display_name: str
    code: str


class TeamOut(BaseModel):
    id: int
    name: str
    display_name: str
    code: str
    confederation: str
    group_label: str | None
    is_host: bool
    elo: float


class PredictionOut(BaseModel):
    model_name: str
    p_home: float
    p_draw: float
    p_away: float
    exp_home_goals: float
    exp_away_goals: float
    top_scoreline: str


class MatchOut(BaseModel):
    id: int
    stage: str
    group_label: str | None
    slot: str | None
    home_team: TeamRef | None
    away_team: TeamRef | None
    scheduled_at: datetime | None
    venue: str
    is_neutral: bool
    status: str
    home_score: int | None
    away_score: int | None
    winner_team_id: int | None = None
    prediction: PredictionOut | None = None


class MatchResultIn(BaseModel):
    home_score: int
    away_score: int
    # Ganador en eliminatorias si el 90' acaba empatado: "home" | "away" (penaltis).
    winner: str | None = None


class TeamProbOut(BaseModel):
    team: str
    display_name: str
    code: str
    confederation: str
    group_label: str | None
    p_group_winner: float
    p_group_runner_up: float
    p_advance: float
    p_r16: float
    p_qf: float
    p_sf: float
    p_final: float
    p_winner: float


class SimulationOut(BaseModel):
    id: int
    created_at: datetime
    runs: int
    model_name: str
    notes: str
    probs: list[TeamProbOut]


class SimulationRunRequest(BaseModel):
    runs: int | None = None
    notes: str = ""
    model: str = "elo"


class ModelInfo(BaseModel):
    name: str
    label: str
    available: bool
    has_run: bool


class BayesStrengthOut(BaseModel):
    team: str
    display_name: str
    code: str
    confederation: str
    group_label: str | None
    att: float
    att_std: float
    defense: float
    def_std: float
    overall: float
    overall_lo: float
    overall_hi: float
