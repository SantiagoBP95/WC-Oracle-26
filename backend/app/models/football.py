"""Modelos de dominio: Team, Match, Prediction, SimulationRun, TeamAdvanceProb, RatingSnapshot."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nombre canónico alineado con el dataset histórico (martj42).
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64), default="")
    code: Mapped[str] = mapped_column(String(8), default="")
    confederation: Mapped[str] = mapped_column(String(16), default="")
    is_host: Mapped[bool] = mapped_column(Boolean, default=False)
    group_label: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    # Ratings actuales (los actualiza el entrenamiento).
    elo: Mapped[float] = mapped_column(Float, default=1500.0)
    attack: Mapped[float] = mapped_column(Float, default=1.0)
    defense: Mapped[float] = mapped_column(Float, default=1.0)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    stage: Mapped[str] = mapped_column(String(16), index=True)  # group, R32, R16, QF, SF, Final
    group_label: Mapped[str | None] = mapped_column(String(2), nullable=True)
    slot: Mapped[str | None] = mapped_column(String(16), nullable=True)  # id de partido en el bracket
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    venue: Mapped[str] = mapped_column(String(64), default="")
    is_neutral: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="scheduled")  # scheduled, finished
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Ganador en eliminatorias cuando el 90' termina empatado (penaltis).
    winner_team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)

    home_team: Mapped["Team | None"] = relationship(foreign_keys=[home_team_id])
    away_team: Mapped["Team | None"] = relationship(foreign_keys=[away_team_id])


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    model_name: Mapped[str] = mapped_column(String(32), default="dixon_coles")
    p_home: Mapped[float] = mapped_column(Float)
    p_draw: Mapped[float] = mapped_column(Float)
    p_away: Mapped[float] = mapped_column(Float)
    exp_home_goals: Mapped[float] = mapped_column(Float)
    exp_away_goals: Mapped[float] = mapped_column(Float)
    top_scoreline: Mapped[str] = mapped_column(String(8), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    runs: Mapped[int] = mapped_column(Integer, default=10000)
    model_name: Mapped[str] = mapped_column(String(32), default="dixon_coles")
    notes: Mapped[str] = mapped_column(String(255), default="")

    team_probs: Mapped[list["TeamAdvanceProb"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class TeamAdvanceProb(Base):
    """Probabilidades de avance/título de un equipo en una corrida de simulación.

    Cada SimulationRun es una 'foto' en el tiempo → habilita la evolución de probabilidades.
    """

    __tablename__ = "team_advance_probs"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    p_group_winner: Mapped[float] = mapped_column(Float, default=0.0)
    p_group_runner_up: Mapped[float] = mapped_column(Float, default=0.0)
    p_advance: Mapped[float] = mapped_column(Float, default=0.0)  # llega a Ronda de 32
    p_r16: Mapped[float] = mapped_column(Float, default=0.0)
    p_qf: Mapped[float] = mapped_column(Float, default=0.0)
    p_sf: Mapped[float] = mapped_column(Float, default=0.0)
    p_final: Mapped[float] = mapped_column(Float, default=0.0)
    p_winner: Mapped[float] = mapped_column(Float, default=0.0)

    run: Mapped["SimulationRun"] = relationship(back_populates="team_probs")
    team: Mapped["Team"] = relationship()


class RatingSnapshot(Base):
    __tablename__ = "rating_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    elo: Mapped[float] = mapped_column(Float)


class Player(Base):
    """Delantero / mediocampista con estadísticas de disparos a puerta.

    Alimentado por StatsBomb (WC 2018+2022) y FBref reciente vía soccerdata.
    sot_per_90 es la métrica principal usada por el Bet Builder.
    """

    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    nationality: Mapped[str] = mapped_column(String(64), default="")
    position: Mapped[str] = mapped_column(String(20), default="FW")   # FW, MF
    sot_per_90: Mapped[float] = mapped_column(Float, default=0.0)
    shots_per_90: Mapped[float] = mapped_column(Float, default=0.0)
    minutes_played: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(64), default="")       # "statsbomb", "fbref", "merged"
    in_squad: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    team: Mapped["Team | None"] = relationship(foreign_keys=[team_id])
