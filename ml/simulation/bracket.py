"""Resolución determinista del bracket a partir de resultados REALES (no simulados).

Reutiliza la estructura oficial del Mundial 2026 (de `monte_carlo`) para, dadas las
posiciones reales de los grupos, materializar los cruces de la Ronda de 32. Los
emparejamientos de rondas posteriores se exponen como plantillas (R16/QF/SF/Final).
"""
from __future__ import annotations

from .monte_carlo import (
    FINAL_PAIR,
    GROUP_LABELS,
    QF_PAIRS,
    R16_PAIRS,
    R32_MATCHES,
    SF_PAIRS,
    SLOT_INDEX,
    _match_thirds,
)

GroupResult = tuple[str, str, int, int]  # (local, visitante, goles_local, goles_visitante)


def group_table(results: list[GroupResult]) -> tuple[list[str], dict[str, dict]]:
    """Tabla del grupo ordenada por puntos, diferencia de goles, goles a favor, nombre."""
    teams: dict[str, dict] = {}

    def ensure(t: str) -> None:
        teams.setdefault(t, {"pts": 0, "gf": 0, "ga": 0})

    for home, away, hs, as_ in results:
        ensure(home)
        ensure(away)
        teams[home]["gf"] += hs
        teams[home]["ga"] += as_
        teams[away]["gf"] += as_
        teams[away]["ga"] += hs
        if hs > as_:
            teams[home]["pts"] += 3
        elif hs < as_:
            teams[away]["pts"] += 3
        else:
            teams[home]["pts"] += 1
            teams[away]["pts"] += 1

    def key(t: str):
        s = teams[t]
        return (s["pts"], s["gf"] - s["ga"], s["gf"], t)

    ranked = sorted(teams, key=key, reverse=True)
    return ranked, teams


def compute_positions(group_results: dict[str, list[GroupResult]]):
    """Devuelve winners, runners, thirds (dict label->equipo) y stats de los terceros."""
    winners: dict[str, str] = {}
    runners: dict[str, str] = {}
    thirds: dict[str, str] = {}
    third_stats: dict[str, tuple[int, int, int]] = {}
    for label, results in group_results.items():
        ranked, teams = group_table(results)
        winners[label], runners[label], thirds[label] = ranked[0], ranked[1], ranked[2]
        s = teams[ranked[2]]
        third_stats[label] = (s["pts"], s["gf"] - s["ga"], s["gf"])
    return winners, runners, thirds, third_stats


def best_eight_thirds(third_stats: dict[str, tuple[int, int, int]]) -> list[str]:
    """Las 8 mejores etiquetas de grupo por (puntos, dif. goles, goles a favor)."""
    order = sorted(
        third_stats,
        key=lambda g: (third_stats[g][0], third_stats[g][1], third_stats[g][2], g),
        reverse=True,
    )
    return order[:8]


def resolve_r32(group_results: dict[str, list[GroupResult]]) -> list[tuple[str, str]]:
    """16 partidos de R32 (M73..M88) como pares (equipo_local, equipo_visitante)."""
    winners, runners, thirds, third_stats = compute_positions(group_results)
    top8 = best_eight_thirds(third_stats)

    gi = {g: i for i, g in enumerate(GROUP_LABELS)}
    qualified = tuple(sorted(gi[g] for g in top8))
    matching = _match_thirds(qualified)  # indice_grupo -> indice_hueco

    slot_team: dict[int, str] = {}
    for g in top8:
        slot_team[matching[gi[g]]] = thirds[g]

    def resolve(slot: tuple[str, str]) -> str:
        kind, ref = slot
        if kind == "W":
            return winners[ref]
        if kind == "R":
            return runners[ref]
        return slot_team[SLOT_INDEX[ref]]  # ("T", "sN")

    return [(resolve(a), resolve(b)) for a, b in R32_MATCHES]


# Plantillas de emparejamiento de rondas posteriores (índices en el orden de la ronda previa).
ROUND_TEMPLATES = [
    ("R16", "R32", R16_PAIRS),
    ("QF", "R16", QF_PAIRS),
    ("SF", "QF", SF_PAIRS),
    ("Final", "SF", [FINAL_PAIR]),
]
