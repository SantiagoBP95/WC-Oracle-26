"""Verifica el token de football-data.org y el acceso a los partidos del Mundial.
    python scripts/check_footballdata.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import httpx

from backend.app.config import settings
from backend.app.services.livesync import parse_footballdata


def main() -> int:
    token = settings.football_data_org_token
    if not token:
        print("[FALLO] No hay FOOTBALL_DATA_ORG_TOKEN en .env")
        print("  Regístrate gratis en https://www.football-data.org/client/register")
        return 1
    print(f"Token cargado: {token[:4]}…{token[-4:]}")
    base = settings.football_data_org_base.rstrip("/")
    comp = settings.football_data_competition

    with httpx.Client(timeout=30, headers={"X-Auth-Token": token}) as c:
        r = c.get(f"{base}/competitions/{comp}/matches")
        if r.status_code != 200:
            print(f"[FALLO] HTTP {r.status_code}: {r.text[:200]}")
            return 1
        data = r.json()
        comp_info = data.get("competition", {})
        parsed = parse_footballdata(data)
        finished = sum(1 for p in parsed if p["finished"])
        print(f"  Competición: {comp_info.get('name', comp)}  ({comp_info.get('code', '')})")
        print(f"  Partidos: {len(parsed)}  finalizados: {finished}")
        for p in parsed[:6]:
            mark = "FT" if p["finished"] else "—"
            print(f"   [{mark}] {p['home']} vs {p['away']}  {p['home_goals']}-{p['away_goals']}")

    if parsed:
        print("\n[OK] Token válido y Mundial accesible. Reinicia el backend para el sync automático.")
        return 0
    print("\n[AVISO] 0 partidos (¿la temporada 2026 aún no está publicada en football-data.org?).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
