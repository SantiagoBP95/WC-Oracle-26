"""Crea una BD de DEMO (data/demo.db) con un torneo avanzado para capturas:
grupos cerrados -> R32 jugada (incluye un penalti) -> Octavos en curso.
No toca la BD real. Ejecutar:  python scripts/seed_demo_ko.py
"""
from __future__ import annotations

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ["DATABASE_URL"] = "sqlite:///./data/demo.db"

_p = pathlib.Path("data/demo.db")
if _p.exists():
    _p.unlink()

from backend.app.database import SessionLocal  # noqa: E402
from backend.app.models.football import Match, Team  # noqa: E402
from backend.app.services.knockouts import materialize_knockouts  # noqa: E402
from backend.app.services.modeling import (  # noqa: E402
    generate_predictions,
    run_simulation,
    update_team_elos,
)
from backend.app.services.seed import initialize_database  # noqa: E402
from ml.ingest.historical import get_results  # noqa: E402
from ml.models.elo import build_lookup, compute_elo  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        initialize_database(db)
        update_team_elos(db, build_lookup(compute_elo(get_results())))
        teams = {t.id: t for t in db.query(Team).all()}

        def score(m: Match) -> tuple[int, int]:
            return (2, 0) if teams[m.home_team_id].elo >= teams[m.away_team_id].elo else (0, 2)

        for m in db.query(Match).filter(Match.stage == "group").all():
            m.home_score, m.away_score = score(m)
            m.status = "finished"
        db.commit()
        materialize_knockouts(db)

        r32 = db.query(Match).filter(Match.stage == "R32").order_by(Match.slot).all()
        for i, m in enumerate(r32):
            if i == 0:  # un partido a penaltis para la demo
                m.home_score, m.away_score, m.winner_team_id = 1, 1, m.home_team_id
            else:
                m.home_score, m.away_score = score(m)
            m.status = "finished"
        db.commit()
        materialize_knockouts(db)

        # Jugar 4 de los 8 Octavos (deja la ronda en curso).
        for m in db.query(Match).filter(Match.stage == "R16").order_by(Match.slot).all()[:4]:
            m.home_score, m.away_score = score(m)
            m.status = "finished"
        db.commit()
        materialize_knockouts(db)

        generate_predictions(db)
        run_simulation(db, model_name="elo", notes="demo")

        print(
            "demo lista:",
            "R32", db.query(Match).filter(Match.stage == "R32").count(),
            "R16", db.query(Match).filter(Match.stage == "R16").count(),
            "QF", db.query(Match).filter(Match.stage == "QF").count(),
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
