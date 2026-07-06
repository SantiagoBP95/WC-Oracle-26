"""Verificación del núcleo ML (sin base de datos).

Descarga el histórico, calcula Elo, casa los 48 equipos del seed y corre una
simulación corta. Imprime chequeos de coherencia. Ejecutar desde la raíz del repo:

    python -m ml.verify_core
"""
from __future__ import annotations

import json
from pathlib import Path

from ml.ingest.historical import get_results
from ml.models.elo import build_lookup, compute_elo, get_elo
from ml.simulation.monte_carlo import GROUP_LABELS, simulate_tournament


def main() -> None:
    seed = json.loads(Path("data/seed/wc2026.json").read_text(encoding="utf-8"))
    groups = {label: [t["name"] for t in teams] for label, teams in seed["groups"].items()}

    print("Descargando/cargando histórico...")
    df = get_results()
    print(f"  partidos: {len(df):,}  rango: {df['date'].min().date()} -> {df['date'].max().date()}")

    ratings = compute_elo(df)
    lookup = build_lookup(ratings)

    elos: dict[str, float] = {}
    missing: list[str] = []
    for teams in groups.values():
        for name in teams:
            e = get_elo(lookup, name)
            elos[name] = e
            if abs(e - 1500.0) < 1e-6:
                missing.append(name)

    print(f"\nEquipos sin Elo (no casaron con el histórico): {missing or 'ninguno'}")

    print("\nTop 10 por Elo:")
    for name, e in sorted(elos.items(), key=lambda x: -x[1])[:10]:
        print(f"  {name:22s} {e:7.1f}")

    print("\nCorriendo simulación (3.000 torneos)...")
    res = simulate_tournament(groups, elos, runs=3000, seed=42)

    print("\nTop 12 por probabilidad de título:")
    print(f"  {'Equipo':22s} {'Campeón':>8s} {'Final':>7s} {'Clasif':>7s}")
    for tp in res.ranked_by_title()[:12]:
        print(f"  {tp.team:22s} {tp.p_winner*100:7.1f}% {tp.p_final*100:6.1f}% {tp.p_advance*100:6.1f}%")

    # --- Chequeos de coherencia ---
    total_win = sum(tp.p_winner for tp in res.probs.values())
    total_final = sum(tp.p_final for tp in res.probs.values())
    print("\nChequeos:")
    print(f"  suma P(campeón)     = {total_win:.3f}  (esperado ~1.0)")
    print(f"  suma P(finalista)   = {total_final:.3f}  (esperado ~2.0)")
    for label in GROUP_LABELS:
        s_gw = sum(res.probs[t].p_group_winner for t in groups[label])
        assert abs(s_gw - 1.0) < 1e-6, f"Grupo {label}: suma 1º = {s_gw}"
    print("  suma P(1º de grupo) = 1.000 en los 12 grupos  OK")
    n_advance = sum(tp.p_advance for tp in res.probs.values())
    print(f"  suma P(clasificar)  = {n_advance:.3f}  (esperado 32.0)")


if __name__ == "__main__":
    main()
