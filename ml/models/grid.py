"""Puente entre los modelos ML/DL y el simulador.

Construye la matriz de goles esperados (λ) para los equipos del Mundial usando el
estado actual de cada equipo, de modo que XGBoost / NN / bayesiano alimenten el
Monte Carlo igual que el baseline Elo.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from ..features.build_features import DEFAULT_STATE
from .elo import fold_name

WC_WEIGHT = 60.0  # importancia "Mundial" para las features pre-partido


def pair_feature_frame(teams: list[str], state: dict[str, dict], weight: float = WC_WEIGHT) -> pd.DataFrame:
    """DataFrame de todos los pares ordenados (local, visitante) en sede neutral."""
    folded = {fold_name(k): v for k, v in state.items()}

    def get(team: str) -> dict:
        return folded.get(fold_name(team), DEFAULT_STATE)

    rows = []
    for a in teams:
        sa = get(a)
        for b in teams:
            sb = get(b)
            rows.append(
                {
                    "home_team": a,
                    "away_team": b,
                    "neutral": 1,
                    "elo_home": sa["elo"],
                    "elo_away": sb["elo"],
                    "elo_diff": sa["elo"] - sb["elo"],
                    "form_home_pts": sa["form_pts"],
                    "form_away_pts": sb["form_pts"],
                    "gf_home": sa["gf"],
                    "ga_home": sa["ga"],
                    "gf_away": sb["gf"],
                    "ga_away": sb["ga"],
                    "weight": weight,
                }
            )
    return pd.DataFrame(rows)


def lambda_matrix(model, teams: list[str], state: dict[str, dict]) -> np.ndarray:
    """L[a,b] = (λ_a, λ_b) en sede neutral, según `model.predict_lambdas`."""
    df = pair_feature_frame(teams, state)
    lh, la = model.predict_lambdas(df)
    n = len(teams)
    L = np.zeros((n, n, 2))
    L[:, :, 0] = np.asarray(lh, dtype=float).reshape(n, n)
    L[:, :, 1] = np.asarray(la, dtype=float).reshape(n, n)
    return L


def make_goal_model(model, state: dict[str, dict]) -> Callable[[list[str]], np.ndarray]:
    """Devuelve un goal_model(teams) -> L listo para `simulate_tournament`."""
    return lambda teams: lambda_matrix(model, teams, state)
