"""Verifica la API key de API-Football y el acceso a los fixtures del Mundial 2026.
    python scripts/check_apifootball.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import httpx

from backend.app.config import settings
from backend.app.services.livesync import WC_LEAGUE_ID, WC_SEASON, parse_fixtures


def main() -> int:
    key = settings.api_football_key
    if not key:
        print("[FALLO] No hay API_FOOTBALL_KEY en .env")
        return 1
    season = int(sys.argv[1]) if len(sys.argv) > 1 else WC_SEASON
    print(f"Key cargada: {key[:4]}…{key[-4:]}  (probando season={season})")
    headers = {"x-apisports-key": key}
    base = settings.api_football_base

    with httpx.Client(timeout=30, headers=headers) as c:
        status = c.get(f"{base}/status").json()
        resp = status.get("response", {})
        if not resp:
            print("[FALLO] /status sin respuesta:", status.get("errors") or status)
            return 1
        acc = resp.get("account", {})
        sub = resp.get("subscription", {})
        req = resp.get("requests", {})
        print(f"  Cuenta: {acc.get('firstname','?')} <{acc.get('email','?')}>")
        print(f"  Plan: {sub.get('plan')}  activo: {sub.get('active')}")
        print(f"  Peticiones hoy: {req.get('current')}/{req.get('limit_day')}")

        fx = c.get(f"{base}/fixtures", params={"league": WC_LEAGUE_ID, "season": season}).json()
        n = fx.get("results", 0)
        print(f"\nFixtures Mundial (league={WC_LEAGUE_ID}, season={season}): {n}")
        if fx.get("errors"):
            print("  Avisos:", fx["errors"])

        if n:
            parsed = parse_fixtures(fx)
            finished = sum(1 for p in parsed if p["finished"])
            print(f"  Parseados: {len(parsed)}  finalizados: {finished}")
            for p in parsed[:5]:
                mark = "FT" if p["finished"] else "—"
                print(f"   [{mark}] {p['home']} vs {p['away']}  {p['home_goals']}-{p['away_goals']}")
            print("\n[OK] La key funciona y los fixtures del Mundial son accesibles.")
            return 0

        # Si no hay fixtures, buscar la liga correcta.
        print("  (0 fixtures — buscando la liga 'World Cup' para confirmar id/season)")
        lg = c.get(f"{base}/leagues", params={"search": "world cup"}).json()
        for item in lg.get("response", [])[:8]:
            seasons = [s["year"] for s in item.get("seasons", [])]
            print(f"   id={item['league']['id']:>4}  {item['league']['name']}  ({item['country']['name']})  seasons~{seasons[-3:]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
