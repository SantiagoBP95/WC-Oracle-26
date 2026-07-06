"""Verifica el cálculo de fuerza bayesiana + intervalos. Ejecutar:
    python scripts/smoke_bayes.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.app.database import SessionLocal
from backend.app.services.modeling import bayesian_team_strength


def main() -> int:
    db = SessionLocal()
    try:
        data = bayesian_team_strength(db)
        if not data:
            print("[FALLO] no hay datos (¿bayesiano sin entrenar?)")
            return 1
        print(f"equipos con fuerza bayesiana: {len(data)}")
        print(f"  {'Equipo':16s} {'fuerza':>7s}  {'IC 95%':>16s}   att / def")
        for d in data[:10]:
            ci = f"[{d['overall_lo']:.2f}, {d['overall_hi']:.2f}]"
            print(f"  {d['display_name']:16s} {d['overall']:7.2f}  {ci:>16s}   {d['att']:.2f} / {d['defense']:.2f}")
        # chequeos
        ok = all(d["overall_lo"] <= d["overall"] <= d["overall_hi"] for d in data)
        print(f"\n[{'OK' if ok else 'FALLO'}] todos los intervalos contienen la media")
        ordered = all(data[i]["overall"] >= data[i + 1]["overall"] for i in range(len(data) - 1))
        print(f"[{'OK' if ordered else 'FALLO'}] ordenados por fuerza descendente")
        return 0 if (ok and ordered) else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
