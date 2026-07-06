"""Rating Elo internacional propio, calculado desde el histórico de partidos.

Implementa el esquema "World Football Elo": K base por importancia del torneo,
multiplicador por diferencia de goles y ventaja de localía (anulada en sede neutral).
Calcular el Elo nosotros (en vez de scrapear) lo hace reproducible y sin dependencias.
"""
from __future__ import annotations

import unicodedata

import pandas as pd

INITIAL_ELO = 1500.0
HFA_ELO = 65.0  # ventaja de localía en puntos Elo

# Alias: nombre del dataset (martj42) -> nombre canónico usado en el seed WC2026.
# Cubre renombrados y variantes que el plegado de acentos no resuelve.
ALIASES: dict[str, str] = {
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "Turkiye": "Turkey",
    "Korea Republic": "South Korea",
    "Korea DPR": "North Korea",
    "Côte d'Ivoire": "Ivory Coast",
    "Congo DR": "DR Congo",
    "Democratic Republic of the Congo": "DR Congo",
    "Cabo Verde": "Cape Verde",
    "Cape Verde Islands": "Cape Verde",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "IR Iran": "Iran",
    "USA": "United States",
    "United States of America": "United States",
    "Chinese Taipei": "Taiwan",
    "United States Virgin Islands": "US Virgin Islands",
}


def _fold(name: str) -> str:
    """Normaliza un nombre: minúsculas y sin acentos, para casar variantes."""
    canonical = ALIASES.get(name, name)
    stripped = unicodedata.normalize("NFKD", canonical).encode("ascii", "ignore").decode()
    return stripped.lower().strip()


# Alias público reutilizable (p. ej. para casar nombres de la API en vivo).
fold_name = _fold


def tournament_weight(tournament: str) -> float:
    """K base según la importancia del torneo (esquema World Football Elo)."""
    t = tournament.lower()
    is_qual = "qualif" in t
    if "world cup" in t and not is_qual:
        return 60.0
    if any(k in t for k in ("confederations cup",)):
        return 50.0
    # Finales continentales y torneos mayores.
    majors = ("euro", "copa américa", "copa america", "gold cup", "asian cup",
              "african cup", "africa cup", "nations championship", "confederation")
    if any(k in t for k in majors) and not is_qual:
        return 50.0
    if "nations league" in t:
        return 45.0
    if is_qual:
        return 40.0
    if "friendly" in t:
        return 20.0
    return 30.0


def _goal_diff_multiplier(margin: int) -> float:
    if margin <= 1:
        return 1.0
    if margin == 2:
        return 1.5
    return (11.0 + margin) / 8.0


def _expected(rating_home: float, rating_away: float, hfa: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-((rating_home + hfa) - rating_away) / 400.0))


def compute_elo(df: pd.DataFrame) -> dict[str, float]:
    """Calcula el Elo final de cada equipo iterando el histórico cronológicamente.

    `df` debe tener columnas: date, home_team, away_team, home_score, away_score,
    tournament, neutral. Devuelve {nombre_dataset: elo}.
    """
    df = df.sort_values("date")
    ratings: dict[str, float] = {}

    for row in df.itertuples(index=False):
        home, away = row.home_team, row.away_team
        rh = ratings.get(home, INITIAL_ELO)
        ra = ratings.get(away, INITIAL_ELO)

        hfa = 0.0 if bool(row.neutral) else HFA_ELO
        exp_home = _expected(rh, ra, hfa)

        hs, as_ = int(row.home_score), int(row.away_score)
        if hs > as_:
            score_home = 1.0
        elif hs == as_:
            score_home = 0.5
        else:
            score_home = 0.0

        k = tournament_weight(str(row.tournament)) * _goal_diff_multiplier(abs(hs - as_))
        delta = k * (score_home - exp_home)
        ratings[home] = rh + delta
        ratings[away] = ra - delta

    return ratings


def build_lookup(ratings: dict[str, float]) -> dict[str, float]:
    """Índice plegado (sin acentos/alias) -> elo, para resolver nombres del seed."""
    lookup: dict[str, float] = {}
    for name, elo in ratings.items():
        lookup[_fold(name)] = elo
    return lookup


def get_elo(lookup: dict[str, float], team_name: str, default: float = INITIAL_ELO) -> float:
    """Busca el Elo de un equipo del seed en el índice plegado."""
    return lookup.get(_fold(team_name), default)
