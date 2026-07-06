"""Comprueba que los nombres de equipos de football-data.org casan con la BD.
    python scripts/check_wc_names.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.app.database import SessionLocal
from backend.app.models.football import Team
from backend.app.services.livesync import FootballDataClient, parse_footballdata
from ml.models.elo import fold_name


def main() -> int:
    db = SessionLocal()
    try:
        db_folds = {fold_name(t.name) for t in db.query(Team).all()}
    finally:
        db.close()

    matches = parse_footballdata(FootballDataClient().get_matches())
    names = set()
    for m in matches:
        for k in ("home", "away"):
            if m[k]:
                names.add(m[k])

    unmatched = sorted(n for n in names if fold_name(n) not in db_folds)
    print(f"Nombres únicos en football-data: {len(names)}")
    print(f"  Casan con la BD: {len(names) - len(unmatched)}")
    if unmatched:
        print(f"  NO casan ({len(unmatched)}): {unmatched}")
        print("  -> añade alias en ml/models/elo.py (ALIASES) para estos.")
        return 1
    print("  [OK] Todos los equipos casan; sus resultados se aplicarán correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
