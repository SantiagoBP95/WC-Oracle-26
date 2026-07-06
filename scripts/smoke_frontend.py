"""Verifica el stack completo a través del dev server de Vite (proxy /api -> backend).

Requiere backend en :8000 y `npm run dev` en :5173. Ejecutar:
    python scripts/smoke_frontend.py
"""
from __future__ import annotations

import sys
import time

import httpx

BASE = "http://localhost:5173"
ok, fail = 0, 0


def check(name: str, cond: bool, extra: str = "") -> None:
    global ok, fail
    if cond:
        ok += 1
        print(f"  [OK] {name}")
    else:
        fail += 1
        print(f"  [FALLO] {name} {extra}")


def wait(url: str, timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(url, timeout=2)
            return True
        except httpx.HTTPError:
            time.sleep(0.6)
    return False


def main() -> int:
    if not wait(f"{BASE}/"):
        print("  [FALLO] el dev server de Vite no respondió en :5173")
        return 1
    c = httpx.Client(base_url=BASE, timeout=20)

    r = c.get("/")
    check("SPA sirve index.html", r.status_code == 200 and 'id="root"' in r.text, str(r.status_code))

    r = c.get("/api/health")
    check("proxy /api -> backend (health 200)", r.status_code == 200 and r.json()["status"] == "ok")

    r = c.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    check("login a través del proxy", r.status_code == 200, r.text[:160])
    token = r.json().get("access_token", "")
    h = {"Authorization": f"Bearer {token}"}

    r = c.get("/api/simulations/latest", headers=h)
    check("simulación vía proxy con token", r.status_code == 200 and len(r.json()["probs"]) == 48)

    print(f"\nResultado: {ok} OK, {fail} fallos")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
