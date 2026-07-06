"""Verifica la materialización de eliminatorias en una BD temporal (no destructiva).
    python scripts/smoke_knockouts.py
"""
from __future__ import annotations

import os
import pathlib
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
os.environ["DATABASE_URL"] = "sqlite:///./data/test_knockouts.db"  # antes de importar la app

_db_file = pathlib.Path("data/test_knockouts.db")
if _db_file.exists():
    _db_file.unlink()

from backend.app.database import SessionLocal, engine  # noqa: E402
from backend.app.models.football import Match, Team  # noqa: E402
from backend.app.services.knockouts import materialize_knockouts  # noqa: E402
from backend.app.services.seed import initialize_database  # noqa: E402

ok = fail = 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global ok, fail
    print(f"  [{'OK' if cond else 'FALLO'}] {name}" + ("" if cond else f"  {extra}"))
    ok += cond
    fail += not cond


def count(db, stage: str) -> int:
    return db.query(Match).filter(Match.stage == stage).count()


def play_stage(db, stage: str, draw_first_without_winner: bool = False) -> None:
    matches = db.query(Match).filter(Match.stage == stage).order_by(Match.slot).all()
    for i, m in enumerate(matches):
        if draw_first_without_winner and i == 0:
            m.home_score, m.away_score, m.winner_team_id = 1, 1, None  # empate sin ganador
        else:
            m.home_score, m.away_score, m.winner_team_id = 2, 0, None  # local avanza
        m.status = "finished"
    db.commit()


def main() -> int:
    db = SessionLocal()
    try:
        initialize_database(db)
        teams = {t.id: t for t in db.query(Team).all()}

        # Rank dentro de cada grupo por id (orden del seed) para standings deterministas.
        group_ids: dict[str, list[int]] = defaultdict(list)
        for t in teams.values():
            group_ids[t.group_label].append(t.id)
        rank = {tid: r for ids in group_ids.values() for r, tid in enumerate(sorted(ids))}

        # Fase de grupos: gana siempre el de menor rank dentro del grupo (2-0).
        for m in db.query(Match).filter(Match.stage == "group").all():
            if rank[m.home_team_id] < rank[m.away_team_id]:
                m.home_score, m.away_score = 2, 0
            else:
                m.home_score, m.away_score = 0, 2
            m.status = "finished"
        db.commit()

        res = materialize_knockouts(db)
        check("R32 materializada al cerrar grupos", res.get("status") == "ok", str(res))
        check("16 partidos en R32", count(db, "R32") == 16, str(count(db, "R32")))

        r32 = db.query(Match).filter(Match.stage == "R32").all()
        ids_in = {m.home_team_id for m in r32} | {m.away_team_id for m in r32}
        check("32 equipos distintos en R32", len(ids_in) == 32, str(len(ids_in)))
        clashes = sum(1 for m in r32 if teams[m.home_team_id].group_label == teams[m.away_team_id].group_label)
        check("sin cruces del mismo grupo en R32", clashes == 0, f"clashes={clashes}")

        # R32 con un empate sin ganador -> R16 NO debe materializarse.
        play_stage(db, "R32", draw_first_without_winner=True)
        materialize_knockouts(db)
        check("empate sin ganador bloquea Octavos", count(db, "R16") == 0, str(count(db, "R16")))

        # Definir el ganador por penaltis -> ahora sí avanza.
        m0 = db.query(Match).filter(Match.stage == "R32").order_by(Match.slot).first()
        m0.winner_team_id = m0.home_team_id
        db.commit()
        materialize_knockouts(db)
        check("tras penaltis se materializan Octavos (8)", count(db, "R16") == 8, str(count(db, "R16")))

        play_stage(db, "R16")
        materialize_knockouts(db)
        check("Cuartos (4)", count(db, "QF") == 4, str(count(db, "QF")))

        play_stage(db, "QF")
        materialize_knockouts(db)
        check("Semis (2)", count(db, "SF") == 2, str(count(db, "SF")))

        play_stage(db, "SF")
        materialize_knockouts(db)
        check("Final (1)", count(db, "Final") == 1, str(count(db, "Final")))

        play_stage(db, "Final")
        final = db.query(Match).filter(Match.stage == "Final").first()
        champ = teams[final.home_team_id] if final.home_score > final.away_score else teams[final.away_team_id]
        check("Final jugada y hay campeón", final.status == "finished")
        print(f"   Campeón (simulado determinista): {champ.display_name}")

        print(f"\nResultado: {ok} OK, {fail} fallos")
        return 1 if fail else 0
    finally:
        db.close()
        engine.dispose()
        if _db_file.exists():
            try:
                _db_file.unlink()
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
