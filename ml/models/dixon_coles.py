"""Modelo Dixon-Coles (Poisson bivariado) sobre goles esperados derivados del Elo.

Pipeline: diferencia de Elo -> supremacía de goles -> (lambda_local, lambda_visitante)
-> matriz de probabilidades de marcador con corrección Dixon-Coles para marcadores bajos
-> probabilidades 1X2, marcador más probable y goles esperados.

La corrección Dixon-Coles (1997) ajusta el conteo de empates bajos (0-0, 1-1) que el
Poisson simple subestima. Constantes calibrables en Fase 2 mediante backtesting.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import poisson

# --- Constantes del modelo (calibrables vía backtesting en Fase 2) ---
BASE_TOTAL_GOALS = 2.6      # goles esperados totales en un partido parejo
SUPREMACY_PER_100 = 0.40    # supremacía de goles por cada 100 puntos de Elo de ventaja
RHO = -0.13                 # dependencia Dixon-Coles para marcadores bajos (negativo => más empates)
HFA_ELO = 65.0              # ventaja de localía en puntos Elo (0 en sede neutral)
MAX_GOALS = 10              # tope de goles para la matriz de marcadores
MIN_LAMBDA = 0.05
MAX_LAMBDA = 6.0


@dataclass
class MatchPrediction:
    p_home: float
    p_draw: float
    p_away: float
    exp_home_goals: float
    exp_away_goals: float
    top_scoreline: str
    score_matrix: np.ndarray  # shape (MAX_GOALS+1, MAX_GOALS+1)


def elo_to_lambdas(elo_home: float, elo_away: float, is_neutral: bool = True) -> tuple[float, float]:
    """Convierte ratings Elo en goles esperados (lambda_home, lambda_away)."""
    hfa = 0.0 if is_neutral else HFA_ELO
    diff = (elo_home + hfa) - elo_away
    supremacy = SUPREMACY_PER_100 * diff / 100.0
    lh = (BASE_TOTAL_GOALS + supremacy) / 2.0
    la = (BASE_TOTAL_GOALS - supremacy) / 2.0
    lh = float(np.clip(lh, MIN_LAMBDA, MAX_LAMBDA))
    la = float(np.clip(la, MIN_LAMBDA, MAX_LAMBDA))
    return lh, la


def _dc_correction(lh: float, la: float, rho: float) -> np.ndarray:
    """Matriz de factores tau de Dixon-Coles aplicada a la esquina de marcadores bajos."""
    tau = np.ones((MAX_GOALS + 1, MAX_GOALS + 1))
    tau[0, 0] = 1.0 - lh * la * rho
    tau[0, 1] = 1.0 + lh * rho
    tau[1, 0] = 1.0 + la * rho
    tau[1, 1] = 1.0 - rho
    return tau


def score_matrix(lh: float, la: float, rho: float = RHO) -> np.ndarray:
    """Matriz normalizada P(goles_local=i, goles_visitante=j)."""
    goals = np.arange(MAX_GOALS + 1)
    home_pmf = poisson.pmf(goals, lh)
    away_pmf = poisson.pmf(goals, la)
    matrix = np.outer(home_pmf, away_pmf)
    matrix *= _dc_correction(lh, la, rho)
    matrix = np.clip(matrix, 0.0, None)
    total = matrix.sum()
    if total > 0:
        matrix /= total
    return matrix


def outcome_probs(matrix: np.ndarray) -> tuple[float, float, float]:
    """(P(local gana), P(empate), P(visitante gana)) a partir de la matriz de marcadores."""
    p_home = float(np.tril(matrix, -1).sum())  # local > visitante
    p_draw = float(np.trace(matrix))           # diagonal
    p_away = float(np.triu(matrix, 1).sum())   # visitante > local
    return p_home, p_draw, p_away


def probs_from_lambdas(lh: float, la: float, rho: float = RHO) -> tuple[float, float, float]:
    """1X2 directamente desde los goles esperados (para modelos ML/DL que predicen λ)."""
    return outcome_probs(score_matrix(lh, la, rho))


def predict(elo_home: float, elo_away: float, is_neutral: bool = True, rho: float = RHO) -> MatchPrediction:
    """Predicción completa de un partido a partir de los Elo de ambos equipos."""
    lh, la = elo_to_lambdas(elo_home, elo_away, is_neutral)
    matrix = score_matrix(lh, la, rho)
    p_home, p_draw, p_away = outcome_probs(matrix)
    sh = math.floor(lh + 0.3)  # <0.7→abajo, ≥0.7→arriba
    sa = math.floor(la + 0.3)
    return MatchPrediction(
        p_home=p_home,
        p_draw=p_draw,
        p_away=p_away,
        exp_home_goals=lh,
        exp_away_goals=la,
        top_scoreline=f"{sh}-{sa}",
        score_matrix=matrix,
    )
