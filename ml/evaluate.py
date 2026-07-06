"""Backtesting: métricas probabilísticas para predicciones 1X2 y split temporal.

- RPS (Ranked Probability Score): estándar para fútbol (resultados ordenados). Menor = mejor.
- Log-loss y Brier: calidad probabilística. Menor = mejor.
- Accuracy: aciertos del resultado más probable. Mayor = mejor.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def outcomes_from_goals(home_goals: np.ndarray, away_goals: np.ndarray) -> np.ndarray:
    """0 = gana local, 1 = empate, 2 = gana visitante."""
    return np.where(home_goals > away_goals, 0, np.where(home_goals == away_goals, 1, 2))


def evaluate_probs(probs: np.ndarray, outcomes: np.ndarray) -> dict[str, float]:
    """probs: [N,3] (local, empate, visitante); outcomes: [N] en {0,1,2}."""
    probs = np.asarray(probs, dtype=float)
    outcomes = np.asarray(outcomes, dtype=int)
    n = len(outcomes)
    onehot = np.eye(3)[outcomes]

    eps = 1e-15
    p = np.clip(probs, eps, 1.0)
    log_loss = float(-np.mean(np.sum(onehot * np.log(p), axis=1)))
    brier = float(np.mean(np.sum((probs - onehot) ** 2, axis=1)))

    cum_p = np.cumsum(probs, axis=1)
    cum_o = np.cumsum(onehot, axis=1)
    rps = float(np.mean(np.sum((cum_p - cum_o) ** 2, axis=1) / 2.0))  # r-1 = 2

    accuracy = float(np.mean(np.argmax(probs, axis=1) == outcomes))
    return {"rps": rps, "log_loss": log_loss, "brier": brier, "accuracy": accuracy, "n": n}


def temporal_split(feat: pd.DataFrame, cutoff: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Divide por fecha: entrena con fechas < cutoff, evalúa con >= cutoff."""
    train = feat[feat["date"] < cutoff].reset_index(drop=True)
    test = feat[feat["date"] >= cutoff].reset_index(drop=True)
    return train, test


def format_table(results: dict[str, dict[str, float]]) -> str:
    """Tabla comparativa de modelos -> métricas."""
    header = f"  {'Modelo':16s} {'RPS':>8s} {'LogLoss':>9s} {'Brier':>8s} {'Acc':>7s}"
    lines = [header, "  " + "-" * 50]
    for name, m in results.items():
        lines.append(
            f"  {name:16s} {m['rps']:8.4f} {m['log_loss']:9.4f} {m['brier']:8.4f} {m['accuracy']*100:6.1f}%"
        )
    return "\n".join(lines)
