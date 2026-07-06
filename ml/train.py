"""CLI de entrenamiento: histórico -> Elo -> predicciones -> simulación (sobre la BD).

Uso (desde la raíz del repo, con el venv activo):
    python -m ml.train                 # inicializa, entrena y simula
    python -m ml.train --force         # fuerza la re-descarga del histórico
    python -m ml.train --runs 20000    # número de simulaciones Monte Carlo
"""
from __future__ import annotations

import argparse

from backend.app.database import SessionLocal
from backend.app.models.football import Team, TeamAdvanceProb
from backend.app.services.modeling import full_train
from backend.app.services.seed import initialize_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrenamiento del modelo del Mundial 2026")
    parser.add_argument("--force", action="store_true", help="fuerza re-descarga del histórico")
    parser.add_argument("--runs", type=int, default=None, help="nº de simulaciones Monte Carlo")
    parser.add_argument("--models", action="store_true", help="entrena también XGBoost y la red neuronal")
    parser.add_argument("--bayes", action="store_true", help="entrena también el modelo bayesiano (PyMC, lento)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("Inicializando base de datos (idempotente)...")
        initialize_database(db)

        msg = "Elo + ML/DL" + (" + Bayes" if args.bayes else "") if (args.models or args.bayes) else "Elo"
        print(f"Entrenando ({msg}): histórico -> Elo -> predicciones -> simulación...")
        run = full_train(
            db, force_download=args.force, runs=args.runs,
            with_ml=args.models or args.bayes, with_bayes=args.bayes,
        )

        rows = (
            db.query(TeamAdvanceProb, Team)
            .join(Team, TeamAdvanceProb.team_id == Team.id)
            .filter(TeamAdvanceProb.run_id == run.id)
            .all()
        )
        rows.sort(key=lambda r: r[0].p_winner, reverse=True)

        print(f"\nSimulación #{run.id} ({run.runs:,} torneos). Top 12 por título:")
        print(f"  {'Equipo':22s} {'Campeón':>8s} {'Final':>7s} {'Clasifica':>9s}")
        for tp, team in rows[:12]:
            print(
                f"  {team.display_name:22s} {tp.p_winner*100:7.1f}% "
                f"{tp.p_final*100:6.1f}% {tp.p_advance*100:8.1f}%"
            )
        print("\nListo. Arranca la API con:  uvicorn backend.app.main:app --host 0.0.0.0 --port 8000")
    finally:
        db.close()


if __name__ == "__main__":
    main()
