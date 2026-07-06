"""Sincronización en vivo de fixtures/resultados desde API-Football (tier gratuito).

Respeta la cuota (100 req/día): se aplica solo a partidos finalizados y se recalcula
únicamente si hubo cambios. Si no hay API key, las operaciones lo indican con claridad.
"""
from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from ml.models.elo import fold_name

from ..config import settings
from ..models.football import Match, Team
from .knockouts import materialize_knockouts
from .modeling import generate_predictions, recalc_all

WC_LEAGUE_ID = 1  # FIFA World Cup en API-Football
WC_SEASON = 2026
FINISHED_STATUSES = {"FT", "AET", "PEN"}


class LiveSyncError(RuntimeError):
    """Error de configuración/uso del sync en vivo (p. ej. sin API key)."""


class APIFootballClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.api_football_key
        self.base_url = (base_url or settings.api_football_base).rstrip("/")

    def get_fixtures(self, league: int = WC_LEAGUE_ID, season: int = WC_SEASON) -> dict:
        if not self.api_key:
            raise LiveSyncError("API_FOOTBALL_KEY no está configurada en el .env")
        headers = {"x-apisports-key": self.api_key}
        params = {"league": league, "season": season}
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base_url}/fixtures", headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()


def parse_fixtures(payload: dict) -> list[dict]:
    """Normaliza la respuesta de /fixtures de API-Football a dicts simples."""
    out: list[dict] = []
    for item in payload.get("response", []):
        teams = item.get("teams", {})
        goals = item.get("goals", {})
        fixture = item.get("fixture", {})
        status = fixture.get("status", {}).get("short", "")
        out.append(
            {
                "home": (teams.get("home") or {}).get("name", ""),
                "away": (teams.get("away") or {}).get("name", ""),
                "home_goals": goals.get("home"),
                "away_goals": goals.get("away"),
                "finished": status in FINISHED_STATUSES,
                "scheduled_at": fixture.get("date"),
                "venue": (fixture.get("venue") or {}).get("name", ""),
            }
        )
    return out


# ---- Proveedor: football-data.org (gratis, cubre el Mundial 2026) ----
FD_FINISHED_STATUSES = {"FINISHED"}


class FootballDataClient:
    def __init__(self, token: str | None = None, base: str | None = None) -> None:
        self.token = token if token is not None else settings.football_data_org_token
        self.base = (base or settings.football_data_org_base).rstrip("/")
        self.competition = settings.football_data_competition

    def get_matches(self) -> dict:
        if not self.token:
            raise LiveSyncError("FOOTBALL_DATA_ORG_TOKEN no está configurada en el .env")
        headers = {"X-Auth-Token": self.token}
        with httpx.Client(timeout=30) as client:
            resp = client.get(f"{self.base}/competitions/{self.competition}/matches", headers=headers)
            resp.raise_for_status()
            return resp.json()


def parse_footballdata(payload: dict) -> list[dict]:
    """Normaliza la respuesta de football-data.org /competitions/WC/matches."""
    out: list[dict] = []
    for m in payload.get("matches", []):
        ft = (m.get("score") or {}).get("fullTime") or {}
        venue = (m.get("venue") or {}).get("name", "") if isinstance(m.get("venue"), dict) else ""
        out.append(
            {
                "home": (m.get("homeTeam") or {}).get("name", ""),
                "away": (m.get("awayTeam") or {}).get("name", ""),
                "home_goals": ft.get("home"),
                "away_goals": ft.get("away"),
                "finished": m.get("status", "") in FD_FINISHED_STATUSES,
                "scheduled_at": m.get("utcDate"),
                "venue": venue,
            }
        )
    return out


def active_provider() -> str | None:
    """Proveedor activo según el .env (prioriza football-data.org, que cubre 2026)."""
    if settings.football_data_org_token:
        return "football-data"
    if settings.api_football_key:
        return "api-football"
    return None


def fetch_fixtures() -> list[dict]:
    """Descarga y normaliza los partidos del Mundial desde el proveedor activo."""
    provider = active_provider()
    if provider == "football-data":
        return parse_footballdata(FootballDataClient().get_matches())
    if provider == "api-football":
        return parse_fixtures(APIFootballClient().get_fixtures())
    raise LiveSyncError(
        "No hay fuente configurada. Define FOOTBALL_DATA_ORG_TOKEN (recomendado) o API_FOOTBALL_KEY."
    )


# Nombres que difieren entre football-data.org / API-Football y nuestro dataset (martj42)
_API_ALIASES: dict[str, str] = {
    "czechia": "czech republic",
    "bosnia-herzegovina": "bosnia and herzegovina",
    "usa": "united states",
    "iran": "ir iran",
    "south korea": "korea republic",
    "north korea": "korea dpr",
    "ivory coast": "cote d'ivoire",
    "cape verde": "cape verde islands",
    "trinidad & tobago": "trinidad and tobago",
    "st. kitts & nevis": "saint kitts and nevis",
    "antigua & barbuda": "antigua and barbuda",
}


def _team_index(db: Session) -> dict[str, Team]:
    """Índice plegado nombre -> Team, incluyendo aliases de API."""
    base = {fold_name(t.name): t for t in db.query(Team).all()}
    # Añadir alias: si el alias resuelve a un nombre conocido, agregarlo con la clave del alias
    for api_name, canonical in _API_ALIASES.items():
        canonical_key = fold_name(canonical)
        if canonical_key in base:
            base[api_name] = base[canonical_key]
    return base


def apply_fixtures(db: Session, fixtures: list[dict]) -> int:
    """Aplica fixtures al estado de la BD: fechas y resultados de fase de grupos.

    Para todos los partidos: actualiza scheduled_at y venue si faltan.
    Para partidos finalizados: actualiza marcador y status.
    Devuelve el número de marcadores actualizados (para decidir si recalcular).
    """
    from datetime import datetime

    idx = _team_index(db)
    score_updates = 0
    for fx in fixtures:
        if not fx.get("home") or not fx.get("away"):
            continue  # TBD (fixtures de eliminatorias sin equipos definidos)
        home = idx.get(fold_name(fx["home"]))
        away = idx.get(fold_name(fx["away"]))
        if home is None or away is None:
            continue

        match = (
            db.query(Match)
            .filter(
                Match.stage == "group",
                Match.home_team_id.in_([home.id, away.id]),
                Match.away_team_id.in_([home.id, away.id]),
            )
            .first()
        )
        if match is None:
            continue

        # Fechas y sede para todos los partidos (programados o finalizados)
        if fx.get("scheduled_at") and match.scheduled_at is None:  # type: ignore[truthy-iterable]
            dt_str = fx["scheduled_at"]
            if isinstance(dt_str, str):
                match.scheduled_at = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if fx.get("venue") and not match.venue:
            match.venue = fx["venue"]

        if not fx.get("finished"):
            continue
        if fx.get("home_goals") is None or fx.get("away_goals") is None:
            continue

        if match.home_team_id == home.id:
            hs, as_ = int(fx["home_goals"]), int(fx["away_goals"])
        else:
            hs, as_ = int(fx["away_goals"]), int(fx["home_goals"])

        if match.status == "finished" and match.home_score == hs and match.away_score == as_:
            continue  # sin cambios en el marcador
        match.home_score = hs
        match.away_score = as_
        match.status = "finished"
        score_updates += 1

    db.flush()
    return score_updates


def sync_from_api(db: Session) -> dict:
    """Descarga partidos del proveedor activo, aplica los finalizados y recalcula."""
    fixtures = fetch_fixtures()
    updated = apply_fixtures(db, fixtures)
    db.commit()
    if updated:
        materialize_knockouts(db)
        generate_predictions(db)
        recalc_all(db, notes=f"sincronización ({active_provider()})")
    return {
        "provider": active_provider(),
        "fetched": len(fixtures),
        "updated": updated,
        "recalculated": bool(updated),
    }
