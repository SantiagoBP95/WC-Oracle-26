"""Verifica el sync en vivo SIN red: parseo, mapeo de nombres (alias y orientación)
y manejo sin API key. No persiste cambios (hace rollback).

Ejecutar desde la raíz del repo:  python scripts/smoke_livesync.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.app.database import SessionLocal
from backend.app.models.football import Match, Team
from backend.app.services.livesync import (
    APIFootballClient,
    LiveSyncError,
    apply_fixtures,
    parse_fixtures,
)
from backend.app.services.seed import initialize_database

ok, fail = 0, 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global ok, fail
    print(f"  [{'OK' if cond else 'FALLO'}] {name}" + ("" if cond else f"  {extra}"))
    if cond:
        ok += 1
    else:
        fail += 1


def match_between(db, a: str, b: str) -> Match | None:
    ta = db.query(Team).filter(Team.name == a).first()
    tb = db.query(Team).filter(Team.name == b).first()
    return (
        db.query(Match)
        .filter(
            Match.home_team_id.in_([ta.id, tb.id]),
            Match.away_team_id.in_([ta.id, tb.id]),
        )
        .first()
    )


def main() -> int:
    db = SessionLocal()
    try:
        initialize_database(db)

        # parse_fixtures normaliza la respuesta cruda de API-Football
        raw = {
            "response": [
                {
                    "fixture": {"status": {"short": "FT"}},
                    "teams": {"home": {"name": "Mexico"}, "away": {"name": "South Africa"}},
                    "goals": {"home": 3, "away": 1},
                }
            ]
        }
        parsed = parse_fixtures(raw)
        check("parse_fixtures normaliza", parsed[0]["home"] == "Mexico" and parsed[0]["finished"])

        # Fixtures sintéticos: orientación normal, invertida + alias, alias USA, y uno sin terminar
        fixtures = [
            {"home": "Mexico", "away": "South Africa", "home_goals": 3, "away_goals": 1, "finished": True},
            {"home": "Czechia", "away": "Korea Republic", "home_goals": 1, "away_goals": 3, "finished": True},
            {"home": "USA", "away": "Australia", "home_goals": 2, "away_goals": 0, "finished": True},
            {"home": "Brazil", "away": "Morocco", "home_goals": None, "away_goals": None, "finished": False},
        ]
        updated = apply_fixtures(db, fixtures)
        check("apply_fixtures actualiza 3 (ignora el no finalizado)", updated == 3, f"updated={updated}")

        m1 = match_between(db, "Mexico", "South Africa")
        check("orientación normal (Mexico 3-1)", m1.home_score == 3 and m1.away_score == 1 and m1.status == "finished")

        m2 = match_between(db, "South Korea", "Czech Republic")
        check(
            "orientación invertida + alias (Corea 3-1 Chequia)",
            m2.home_score == 3 and m2.away_score == 1,
            f"{m2.home_score}-{m2.away_score}",
        )

        m3 = match_between(db, "United States", "Australia")
        check("alias USA -> United States (2-0)", m3.home_score == 2 and m3.away_score == 0)

        # No persistir los datos de prueba
        db.rollback()

        # Sin API key -> LiveSyncError claro
        try:
            APIFootballClient(api_key="").get_fixtures()
            check("get_fixtures sin key lanza error", False)
        except LiveSyncError:
            check("get_fixtures sin key lanza LiveSyncError", True)

        print(f"\nResultado: {ok} OK, {fail} fallos")
        return 1 if fail else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
