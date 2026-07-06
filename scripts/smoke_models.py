"""Smoke test de selección de modelo. Requiere el servidor en :8000.
    python scripts/smoke_models.py
"""
from __future__ import annotations

import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"
ok = fail = 0


def check(name, cond, extra=""):
    global ok, fail
    print(f"  [{'OK' if cond else 'FALLO'}] {name}" + ("" if cond else f"  {extra}"))
    ok += cond
    fail += not cond


def main() -> int:
    for _ in range(60):
        try:
            if httpx.get(f"{BASE}/api/health", timeout=2).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.5)
    c = httpx.Client(base_url=BASE, timeout=60)
    tok = c.post("/api/auth/login", data={"username": "admin", "password": "admin123"}).json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    models = c.get("/api/simulations/models", headers=h).json()
    avail = {m["name"] for m in models if m["available"]}
    check("modelos disponibles incluyen elo/xgboost/nn", {"elo", "xgboost", "nn"} <= avail, str(avail))

    tops = {}
    for model in ["elo", "xgboost", "nn"]:
        r = c.get("/api/simulations/latest", params={"model": model}, headers=h)
        check(f"latest model={model} 200 con 48 probs", r.status_code == 200 and len(r.json()["probs"]) == 48)
        if r.status_code == 200:
            sim = r.json()
            check(f"  sim model={model} etiquetada", sim["model_name"] == model, sim["model_name"])
            tops[model] = sim["probs"][0]["display_name"]

    check("los modelos dan resultados (favoritos)", len(tops) == 3, str(tops))
    print("   favoritos por modelo:", tops)

    r = c.post("/api/simulations/run", headers=h, json={"model": "xgboost", "runs": 1500})
    check("run model=xgboost 200", r.status_code == 200, r.text[:150])

    r = c.post("/api/simulations/run", headers=h, json={"model": "inexistente", "runs": 100})
    check("run modelo inexistente -> 400", r.status_code == 400, str(r.status_code))

    print(f"\nResultado: {ok} OK, {fail} fallos")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
