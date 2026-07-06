"""Simulador Monte Carlo del Mundial 2026 (vectorizado con numpy).

- Fase de grupos: muestrea marcadores reales (Dixon-Coles) para resolver puntos,
  diferencia de goles y goles a favor, y rankear cada grupo.
- Mejores terceros: ranking de los 12 terceros y selección de los 8 mejores.
- Eliminatorias: **bracket oficial** del Mundial 2026 (R32 partidos 73-88 → Final),
  con asignación de los 8 terceros a sus huecos mediante emparejamiento bipartito que
  respeta los conjuntos de grupos elegibles del Anexo C de FIFA (sin revanchas de grupo).
- Resultados ya jugados condicionan la simulación (recálculo en vivo).

Devuelve, por equipo, la probabilidad de ganar el grupo, quedar segundo, clasificar,
y alcanzar cada ronda hasta el título.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from ..models.dixon_coles import MAX_GOALS, elo_to_lambdas, outcome_probs, score_matrix

GROUP_LABELS = list("ABCDEFGHIJKL")
GROUP_PAIRINGS = [(0, 1), (2, 3), (0, 2), (1, 3), (0, 3), (1, 2)]  # 6 partidos por grupo
_GI = {g: i for i, g in enumerate(GROUP_LABELS)}  # letra -> índice 0..11


def _idx(letters: str) -> set[int]:
    return {_GI[c] for c in letters}


# Bracket oficial: 16 partidos de R32 (orden M73..M88). Slots:
#   ("W", grupo) = 1º, ("R", grupo) = 2º, ("T", "sN") = hueco de mejor tercero N.
R32_MATCHES: list[tuple[tuple[str, str], tuple[str, str]]] = [
    (("R", "A"), ("R", "B")),    # 73
    (("W", "E"), ("T", "s0")),   # 74
    (("W", "F"), ("R", "C")),    # 75
    (("W", "C"), ("R", "F")),    # 76
    (("W", "I"), ("T", "s1")),   # 77
    (("R", "E"), ("R", "I")),    # 78
    (("W", "A"), ("T", "s2")),   # 79
    (("W", "L"), ("T", "s3")),   # 80
    (("W", "D"), ("T", "s4")),   # 81
    (("W", "G"), ("T", "s5")),   # 82
    (("R", "K"), ("R", "L")),    # 83
    (("W", "H"), ("R", "J")),    # 84
    (("W", "B"), ("T", "s6")),   # 85
    (("W", "J"), ("R", "H")),    # 86
    (("W", "K"), ("T", "s7")),   # 87
    (("R", "D"), ("R", "G")),    # 88
]

# Conjuntos de grupos elegibles para cada hueco de mejor tercero (Anexo C).
SLOT_ELIGIBLE: list[set[int]] = [
    _idx("ABCDF"),  # s0 (M74)
    _idx("CDFGH"),  # s1 (M77)
    _idx("CEFHI"),  # s2 (M79)
    _idx("EHIJK"),  # s3 (M80)
    _idx("BEFIJ"),  # s4 (M81)
    _idx("AEHIJ"),  # s5 (M82)
    _idx("EFGIJ"),  # s6 (M85)
    _idx("DEIJL"),  # s7 (M87)
]
SLOT_INDEX = {f"s{k}": k for k in range(8)}

# Árbol del bracket (índices de partido dentro de su ronda).
R16_PAIRS = [(1, 4), (0, 2), (3, 5), (6, 7), (10, 11), (8, 9), (13, 15), (12, 14)]
QF_PAIRS = [(0, 1), (4, 5), (2, 3), (6, 7)]
SF_PAIRS = [(0, 1), (2, 3)]
FINAL_PAIR = (0, 1)


@dataclass
class TeamProbs:
    team: str
    p_group_winner: float = 0.0
    p_group_runner_up: float = 0.0
    p_advance: float = 0.0
    p_r16: float = 0.0
    p_qf: float = 0.0
    p_sf: float = 0.0
    p_final: float = 0.0
    p_winner: float = 0.0


@dataclass
class SimulationResult:
    runs: int
    teams: list[str]
    probs: dict[str, TeamProbs] = field(default_factory=dict)

    def ranked_by_title(self) -> list[TeamProbs]:
        return sorted(self.probs.values(), key=lambda p: p.p_winner, reverse=True)


def _match_thirds(groups: tuple[int, ...]) -> dict[int, int]:
    """Empareja los grupos de los 8 mejores terceros con sus huecos (Anexo C).

    Devuelve {indice_grupo: indice_hueco}. Usa caminos aumentantes (Kuhn) y, por
    robustez, asigna cualquier grupo sin emparejar a un hueco libre.
    """
    slot_to_group = [-1] * 8

    def assign(g: int, seen: list[bool]) -> bool:
        for s in range(8):
            if g in SLOT_ELIGIBLE[s] and not seen[s]:
                seen[s] = True
                if slot_to_group[s] == -1 or assign(slot_to_group[s], seen):
                    slot_to_group[s] = g
                    return True
        return False

    for g in groups:
        assign(g, [False] * 8)

    matching = {g: s for s, g in enumerate(slot_to_group) if g != -1}
    free = [s for s in range(8) if slot_to_group[s] == -1]
    for g in groups:
        if g not in matching:
            matching[g] = free.pop()
    return matching


def _lambda_matrix_from_elos(elos: np.ndarray) -> np.ndarray:
    """Matriz λ por defecto (Elo → Dixon-Coles): L[a,b] = (λ_a, λ_b) en sede neutral."""
    n = len(elos)
    L = np.zeros((n, n, 2))
    for a in range(n):
        for b in range(n):
            if a == b:
                continue
            la, lb = elo_to_lambdas(elos[a], elos[b], is_neutral=True)
            L[a, b, 0], L[a, b, 1] = la, lb
    return L


def _advance_matrix(L: np.ndarray) -> np.ndarray:
    """p_adv[a,b] = prob. de que el equipo a elimine al b (90' + penaltis).

    El penalti se deriva de las probabilidades de victoria del propio modelo (agnóstico).
    """
    n = L.shape[0]
    p_adv = np.zeros((n, n))
    for a in range(n):
        for b in range(n):
            if a == b:
                continue
            p_home, p_draw, p_away = outcome_probs(score_matrix(L[a, b, 0], L[a, b, 1]))
            pen_a = float(np.clip(p_home / (p_home + p_away + 1e-9), 0.35, 0.65))
            p_adv[a, b] = p_home + p_draw * pen_a
    return p_adv


def _group_pair_distributions(group_idx: list[int], L: np.ndarray) -> list[np.ndarray]:
    """Distribución plana de marcadores para cada uno de los 6 partidos del grupo."""
    dists = []
    for i, j in GROUP_PAIRINGS:
        a, b = group_idx[i], group_idx[j]
        dists.append(score_matrix(L[a, b, 0], L[a, b, 1]).ravel())
    return dists


def simulate_tournament(
    groups: dict[str, list[str]],
    elos: dict[str, float] | None = None,
    runs: int = 10000,
    seed: int | None = None,
    fixed_results: dict[tuple[str, str], tuple[int, int]] | None = None,
    goal_model: Callable[[list[str]], np.ndarray] | None = None,
) -> SimulationResult:
    """Simula el torneo `runs` veces.

    `fixed_results` condiciona la simulación sobre partidos de grupo ya jugados:
    clave (equipo_local, equipo_visitante) -> (goles_local, goles_visitante).

    `goal_model(teams) -> L[N,N,2]` permite usar otro modelo (XGBoost, NN, bayesiano):
    L[a,b] = (goles esperados de a, de b) en sede neutral. Si es None, usa Elo→Dixon-Coles.
    """
    rng = np.random.default_rng(seed)
    fixed_results = fixed_results or {}
    n_side = MAX_GOALS + 1

    teams: list[str] = []
    for label in GROUP_LABELS:
        teams.extend(groups[label])
    index = {t: k for k, t in enumerate(teams)}
    group_global = {label: [index[t] for t in groups[label]] for label in GROUP_LABELS}

    if goal_model is not None:
        L = np.asarray(goal_model(teams), dtype=float)
    else:
        elo_arr = np.array([(elos or {}).get(t, 1500.0) for t in teams], dtype=float)
        L = _lambda_matrix_from_elos(elo_arr)

    p_adv = _advance_matrix(L)

    n_teams = len(teams)
    c_gw = np.zeros(n_teams)
    c_ru = np.zeros(n_teams)
    c_adv = np.zeros(n_teams)
    c_r16 = np.zeros(n_teams)
    c_qf = np.zeros(n_teams)
    c_sf = np.zeros(n_teams)
    c_final = np.zeros(n_teams)
    c_win = np.zeros(n_teams)

    winners: dict[str, np.ndarray] = {}
    runners: dict[str, np.ndarray] = {}
    third_global = np.zeros((12, runs), dtype=int)
    third_score = np.zeros((12, runs))

    # --- Fase de grupos (vectorizada por simulación) ---
    for gi, label in enumerate(GROUP_LABELS):
        gidx = group_global[label]
        dists = _group_pair_distributions(gidx, L)
        points = np.zeros((runs, 4))
        gf = np.zeros((runs, 4))
        ga = np.zeros((runs, 4))

        for (i, j), dist in zip(GROUP_PAIRINGS, dists):
            fixed = fixed_results.get((teams[gidx[i]], teams[gidx[j]]))
            if fixed is not None:
                gh = np.full(runs, fixed[0])
                gj = np.full(runs, fixed[1])
            else:
                flat = rng.choice(n_side * n_side, size=runs, p=dist)
                gh, gj = flat // n_side, flat % n_side
            points[:, i] += np.where(gh > gj, 3, np.where(gh == gj, 1, 0))
            points[:, j] += np.where(gj > gh, 3, np.where(gh == gj, 1, 0))
            gf[:, i] += gh
            ga[:, i] += gj
            gf[:, j] += gj
            ga[:, j] += gh

        gd = gf - ga
        rand = rng.random((runs, 4))
        composite = points * 1.0e6 + gd * 1.0e3 + gf * 1.0e1 + rand
        order = np.argsort(-composite, axis=1)

        gidx_arr = np.array(gidx)
        winners[label] = gidx_arr[order[:, 0]]
        runners[label] = gidx_arr[order[:, 1]]
        third_global[gi] = gidx_arr[order[:, 2]]
        third_score[gi] = np.take_along_axis(composite, order[:, 2][:, None], axis=1).ravel()

        np.add.at(c_gw, winners[label], 1)
        np.add.at(c_ru, runners[label], 1)

    # --- 8 mejores terceros (por grupo) ---
    third_order = np.argsort(-third_score, axis=0)  # [12, runs]
    top8_groups = third_order[:8, :]                # [8, runs] índices de grupo 0..11

    # --- Asignar los 8 terceros a sus huecos (matching por combinación, con caché) ---
    third_slot_team = np.empty((8, runs), dtype=int)
    cache: dict[tuple[int, ...], dict[int, int]] = {}
    for n in range(runs):
        gcol = top8_groups[:, n]
        key = tuple(sorted(int(g) for g in gcol))
        matching = cache.get(key)
        if matching is None:
            matching = _match_thirds(key)
            cache[key] = matching
        for g in gcol:
            gi_ = int(g)
            third_slot_team[matching[gi_], n] = third_global[gi_, n]

    # --- Construir entrantes de Ronda de 32 (bracket oficial) ---
    def resolve(slot: tuple[str, str]) -> np.ndarray:
        kind, ref = slot
        if kind == "W":
            return winners[ref]
        if kind == "R":
            return runners[ref]
        return third_slot_team[SLOT_INDEX[ref]]

    r32_matches = [(resolve(a), resolve(b)) for a, b in R32_MATCHES]

    for a, b in r32_matches:
        np.add.at(c_adv, a, 1)
        np.add.at(c_adv, b, 1)

    # --- Eliminatorias (vectorizadas) ---
    def play(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return np.where(rng.random(len(a)) < p_adv[a, b], a, b)

    r32_winners = [play(a, b) for a, b in r32_matches]
    for w in r32_winners:
        np.add.at(c_r16, w, 1)

    r16_winners = [play(r32_winners[i], r32_winners[j]) for i, j in R16_PAIRS]
    for w in r16_winners:
        np.add.at(c_qf, w, 1)

    qf_winners = [play(r16_winners[i], r16_winners[j]) for i, j in QF_PAIRS]
    for w in qf_winners:
        np.add.at(c_sf, w, 1)

    sf_winners = [play(qf_winners[i], qf_winners[j]) for i, j in SF_PAIRS]
    for w in sf_winners:
        np.add.at(c_final, w, 1)

    champions = play(sf_winners[FINAL_PAIR[0]], sf_winners[FINAL_PAIR[1]])
    np.add.at(c_win, champions, 1)

    # --- Agregar probabilidades ---
    result = SimulationResult(runs=runs, teams=teams)
    for k, t in enumerate(teams):
        result.probs[t] = TeamProbs(
            team=t,
            p_group_winner=c_gw[k] / runs,
            p_group_runner_up=c_ru[k] / runs,
            p_advance=c_adv[k] / runs,
            p_r16=c_r16[k] / runs,
            p_qf=c_qf[k] / runs,
            p_sf=c_sf[k] / runs,
            p_final=c_final[k] / runs,
            p_winner=c_win[k] / runs,
        )
    return result
