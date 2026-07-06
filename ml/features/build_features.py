"""Tabla de features pre-partido (sin fuga de datos) para los modelos ML/DL.

Una sola pasada cronológica produce, por partido y ANTES de jugarse:
- Elo de ambos equipos (variable en el tiempo).
- Forma reciente (últimos K partidos): puntos promedio y goles a favor/en contra.
- Sede neutral y peso de importancia del torneo.
- Objetivos: goles de local y de visitante.

`compute_current_state` devuelve el estado MÁS RECIENTE por equipo (para predecir el
Mundial). Ambas funciones comparten la misma actualización Elo/forma.
"""
from __future__ import annotations

from collections import defaultdict, deque

import numpy as np
import pandas as pd

from ..models.elo import HFA_ELO, INITIAL_ELO, tournament_weight

FORM_WINDOW = 5

FEATURE_COLUMNS = [
    "neutral",
    "elo_home",
    "elo_away",
    "elo_diff",
    "form_home_pts",
    "form_away_pts",
    "gf_home",
    "ga_home",
    "gf_away",
    "ga_away",
    "weight",
]

DEFAULT_STATE = {"elo": INITIAL_ELO, "form_pts": 1.0, "gf": 1.0, "ga": 1.0}


def _gd_multiplier(margin: int) -> float:
    if margin <= 1:
        return 1.0
    if margin == 2:
        return 1.5
    return (11.0 + margin) / 8.0


def _apply_match(ratings, form, home, away, hs, as_, tournament, neutral) -> None:
    """Actualiza Elo y forma (post-partido) in place."""
    rh, ra = ratings[home], ratings[away]
    hfa = 0.0 if neutral else HFA_ELO
    exp_home = 1.0 / (1.0 + 10.0 ** (-((rh + hfa) - ra) / 400.0))
    sh = 1.0 if hs > as_ else 0.5 if hs == as_ else 0.0
    k = tournament_weight(tournament) * _gd_multiplier(abs(hs - as_))
    delta = k * (sh - exp_home)
    ratings[home] = rh + delta
    ratings[away] = ra - delta
    form[home].append((3 if hs > as_ else 1 if hs == as_ else 0, hs, as_))
    form[away].append((3 if as_ > hs else 1 if hs == as_ else 0, as_, hs))


def _agg_form(f: deque) -> tuple[float, float, float]:
    if not f:
        return 1.0, 1.0, 1.0  # priors neutros
    arr = np.array(f, dtype=float)
    return float(arr[:, 0].mean()), float(arr[:, 1].mean()), float(arr[:, 2].mean())


def build_features(df: pd.DataFrame, form_window: int = FORM_WINDOW) -> pd.DataFrame:
    df = df.sort_values("date").reset_index(drop=True)
    ratings: dict[str, float] = defaultdict(lambda: INITIAL_ELO)
    form: dict[str, deque] = defaultdict(lambda: deque(maxlen=form_window))

    rows = []
    for r in df.itertuples(index=False):
        home, away = r.home_team, r.away_team
        rh, ra = ratings[home], ratings[away]
        neutral = bool(r.neutral)
        hfa = 0.0 if neutral else HFA_ELO
        hp, hgf, hga = _agg_form(form[home])
        ap, agf, aga = _agg_form(form[away])

        rows.append(
            {
                "date": r.date,
                "home_team": home,
                "away_team": away,
                "neutral": int(neutral),
                "elo_home": rh,
                "elo_away": ra,
                "elo_diff": (rh + hfa) - ra,
                "form_home_pts": hp,
                "form_away_pts": ap,
                "gf_home": hgf,
                "ga_home": hga,
                "gf_away": agf,
                "ga_away": aga,
                "weight": tournament_weight(str(r.tournament)),
                "home_goals": int(r.home_score),
                "away_goals": int(r.away_score),
            }
        )
        _apply_match(ratings, form, home, away, int(r.home_score), int(r.away_score),
                     str(r.tournament), neutral)

    return pd.DataFrame(rows)


def compute_current_state(df: pd.DataFrame, form_window: int = FORM_WINDOW) -> dict[str, dict]:
    """Estado más reciente por equipo: {team: {elo, form_pts, gf, ga}}."""
    df = df.sort_values("date").reset_index(drop=True)
    ratings: dict[str, float] = defaultdict(lambda: INITIAL_ELO)
    form: dict[str, deque] = defaultdict(lambda: deque(maxlen=form_window))

    for r in df.itertuples(index=False):
        _apply_match(ratings, form, r.home_team, r.away_team, int(r.home_score),
                     int(r.away_score), str(r.tournament), bool(r.neutral))

    state: dict[str, dict] = {}
    for team in set(ratings) | set(form):
        pts, gf, ga = _agg_form(form[team])
        state[team] = {"elo": ratings[team], "form_pts": pts, "gf": gf, "ga": ga}
    return state
