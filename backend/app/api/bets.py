"""Mercados de apuesta: probabilidades Poisson por partido y combinador de cuotas."""
from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from scipy.stats import poisson
from sqlalchemy.orm import Session

from ..core.rbac import require_permission
from ..database import get_db
from ..models.football import Match, Player, Prediction
from ..models.rbac import User

router = APIRouter(prefix="/api/bets", tags=["bets"])

# Medias históricas mundiales (FIFA WC 2014-2022)
_BASE_CORNERS = 9.8
_BASE_CARDS = 3.6
_BASE_SHOTS = 23.5
_BASE_SOT = 10.8   # disparos a puerta totales (WC 2018+2022 promedio)
_SOT_CONV = 0.30   # tasa conversión SOT→gol: SOT ≈ λ / _SOT_CONV
_AVG_GOALS = 2.64  # referencia para escalar


def _p_over(lam: float, line: float) -> float:
    return float(1.0 - poisson.cdf(math.floor(line), lam))


def _btts(lh: float, la: float) -> float:
    return float((1 - poisson.cdf(0, lh)) * (1 - poisson.cdf(0, la)))


def _clamp(p: float) -> float:
    return round(max(0.01, min(0.99, p)), 4)


def _build_markets(pred: Prediction, home_elo: float, away_elo: float) -> list[dict]:
    lh = pred.exp_home_goals
    la = pred.exp_away_goals
    total = lh + la
    elo_diff = abs(home_elo - away_elo) / 400.0
    scale = total / _AVG_GOALS

    corner_lam = _BASE_CORNERS * scale * (1 + 0.05 * elo_diff)
    card_lam = _BASE_CARDS * (1 + 0.18 * elo_diff)
    shots_lam = _BASE_SHOTS * scale
    # Disparos a puerta: λ_sot = λ_goles / tasa_conversión, escalado por media WC
    sot_lam_h = max(0.5, lh / _SOT_CONV)
    sot_lam_a = max(0.5, la / _SOT_CONV)
    sot_lam_total = sot_lam_h + sot_lam_a

    def mk(id_: str, category: str, label: str, prob: float) -> dict:
        p = _clamp(prob)
        return {"id": id_, "category": category, "label": label, "prob": p, "odds": round(1 / p, 2)}

    markets: list[dict] = []

    # Resultado 1X2
    markets += [
        mk("1x2_home", "Resultado", "Victoria local (1)", pred.p_home),
        mk("1x2_draw", "Resultado", "Empate (X)", pred.p_draw),
        mk("1x2_away", "Resultado", "Victoria visitante (2)", pred.p_away),
    ]

    # Goles totales
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        p = _p_over(total, line)
        label_line = str(line)
        markets += [
            mk(f"goals_over_{line}", "Goles", f"Más de {label_line} goles", p),
            mk(f"goals_under_{line}", "Goles", f"Menos de {label_line} goles", 1 - p),
        ]

    # BTTS
    p_btts = _btts(lh, la)
    markets += [
        mk("btts_yes", "Goles", "Ambos equipos marcan (BTTS: Sí)", p_btts),
        mk("btts_no", "Goles", "No ambos marcan (BTTS: No)", 1 - p_btts),
    ]

    # Goles de cada equipo
    for line in (0.5, 1.5, 2.5):
        markets += [
            mk(f"home_over_{line}", "Goles local", f"Local más de {line}", _p_over(lh, line)),
            mk(f"away_over_{line}", "Goles visitante", f"Visitante más de {line}", _p_over(la, line)),
        ]

    # Córners
    for line in (7.5, 8.5, 9.5, 10.5, 11.5):
        p = _p_over(corner_lam, line)
        markets += [
            mk(f"corners_over_{line}", "Córners", f"Más de {line} córners", p),
            mk(f"corners_under_{line}", "Córners", f"Menos de {line} córners", 1 - p),
        ]

    # Tarjetas amarillas
    for line in (1.5, 2.5, 3.5, 4.5, 5.5):
        p = _p_over(card_lam, line)
        markets += [
            mk(f"cards_over_{line}", "Tarjetas", f"Más de {line} tarjetas", p),
            mk(f"cards_under_{line}", "Tarjetas", f"Menos de {line} tarjetas", 1 - p),
        ]

    # Tiros totales (con + sin puerta, ambos equipos)
    for line in (19.5, 22.5, 24.5, 27.5):
        p = _p_over(shots_lam, line)
        markets += [
            mk(f"shots_over_{line}", "Tiros totales", f"Más de {line} tiros (con + sin puerta)", p),
            mk(f"shots_under_{line}", "Tiros totales", f"Menos de {line} tiros (con + sin puerta)", 1 - p),
        ]

    # Tiros a puerta — partido completo (ambos equipos sumados)
    for line in (7.5, 8.5, 9.5, 10.5, 11.5, 12.5):
        p = _p_over(sot_lam_total, line)
        markets += [
            mk(f"sot_over_{line}", "Tiros a puerta · Partido", f"Más de {line} tiros a puerta en el partido", p),
            mk(f"sot_under_{line}", "Tiros a puerta · Partido", f"Menos de {line} tiros a puerta en el partido", 1 - p),
        ]

    # Tiros a puerta — total del equipo local
    for line in (2.5, 3.5, 4.5, 5.5, 6.5):
        p = _p_over(sot_lam_h, line)
        markets += [
            mk(f"sot_home_over_{line}", "Tiros a puerta · Equipo local", f"Equipo local: más de {line} tiros a puerta", p),
            mk(f"sot_home_under_{line}", "Tiros a puerta · Equipo local", f"Equipo local: menos de {line} tiros a puerta", 1 - p),
        ]

    # Tiros a puerta — total del equipo visitante
    for line in (2.5, 3.5, 4.5, 5.5, 6.5):
        p = _p_over(sot_lam_a, line)
        markets += [
            mk(f"sot_away_over_{line}", "Tiros a puerta · Equipo visitante", f"Equipo visitante: más de {line} tiros a puerta", p),
            mk(f"sot_away_under_{line}", "Tiros a puerta · Equipo visitante", f"Equipo visitante: menos de {line} tiros a puerta", 1 - p),
        ]

    return markets


def _player_markets(team_id: int | None, side: str, intensity: float, db: Session) -> list[dict]:
    """Genera mercados de disparos a puerta para los top-3 delanteros de un equipo."""
    if team_id is None:
        return []

    raw_players = (
        db.query(Player)
        .filter(
            Player.team_id == team_id,
            Player.sot_per_90 > 0,
            Player.in_squad.is_(True),
        )
        .order_by(Player.sot_per_90.desc())
        .limit(10)
        .all()
    )
    # Deduplicate by first two name tokens (handles "Kylian Mbappé" vs "Kylian Mbappé Lottin")
    seen: set[str] = set()
    players = []
    for p in raw_players:
        key = " ".join(p.name.lower().split()[:2])
        if key not in seen:
            seen.add(key)
            players.append(p)
        if len(players) == 3:
            break
    if not players:
        return []

    lado = "local" if side == "local" else "visitante"
    category = f"Tiros a puerta · Jugador {lado}"
    _source_es = {"statsbomb": "StatsBomb", "fbref": "FBref", "merged": "Combinado"}
    markets: list[dict] = []
    for player in players:
        lam = max(0.1, player.sot_per_90 * intensity)
        short_name = player.name.split(",")[0] if "," in player.name else player.name
        # Un item por jugador con las 3 líneas embebidas como lista
        lines = []
        for line in (0.5, 1.5, 2.5):
            p = _clamp(_p_over(lam, line))
            lines.append({"line": line, "prob": p, "odds": round(1 / p, 2)})
        markets.append({
            "id": f"sot_{side}_{player.id}",
            "category": category,
            "label": short_name,
            "prob": lines[0]["prob"],   # prob base (línea 0.5) — para el combinador
            "odds": lines[0]["odds"],
            "player": short_name,
            "sot_per_90": round(player.sot_per_90, 2),
            "source": _source_es.get(player.source, player.source),
            "lines": lines,
        })
    return markets


@router.get("/matches/{match_id}")
def match_markets(
    match_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission("view_dashboard")),
):
    m = db.get(Match, match_id)
    if m is None:
        raise HTTPException(404, "Partido no encontrado")
    pred = db.query(Prediction).filter(Prediction.match_id == match_id).first()
    if pred is None:
        raise HTTPException(404, "Sin predicción disponible para este partido")

    home_elo = m.home_team.elo if m.home_team else 1500.0
    away_elo = m.away_team.elo if m.away_team else 1500.0

    total_exp = pred.exp_home_goals + pred.exp_away_goals
    intensity = total_exp / _AVG_GOALS  # factor de intensidad relativo al promedio WC

    team_markets = _build_markets(pred, home_elo, away_elo)
    player_markets_home = _player_markets(m.home_team_id, "local", intensity, db)
    player_markets_away = _player_markets(m.away_team_id, "visitante", intensity, db)

    return {
        "match_id": match_id,
        "home": m.home_team.display_name if m.home_team else "—",
        "away": m.away_team.display_name if m.away_team else "—",
        "status": m.status,
        "exp_goals_home": round(pred.exp_home_goals, 2),
        "exp_goals_away": round(pred.exp_away_goals, 2),
        "markets": team_markets + player_markets_home + player_markets_away,
    }


class CombineIn(BaseModel):
    probs: list[float]


@router.post("/combine")
def combine(
    body: CombineIn,
    _: User = Depends(require_permission("view_dashboard")),
):
    if not body.probs:
        return {"prob": 0.0, "odds": 0.0}
    result = 1.0
    for p in body.probs:
        result *= max(0.001, min(0.999, p))
    result = round(result, 6)
    return {"prob": result, "odds": round(1 / result, 2)}
