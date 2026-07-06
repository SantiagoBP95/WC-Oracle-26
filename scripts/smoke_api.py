"""Smoke test de la API: auth, RBAC, cupos, tracking y recálculo.

Requiere el servidor corriendo en http://127.0.0.1:8000. Ejecutar:
    python scripts/smoke_api.py
"""
from __future__ import annotations

import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"
ok, fail = 0, 0


def wait_for_server(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if httpx.get(f"{BASE}/api/health", timeout=2).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    return False


def check(name: str, condition: bool, extra: str = "") -> None:
    global ok, fail
    if condition:
        ok += 1
        print(f"  [OK] {name}")
    else:
        fail += 1
        print(f"  [FALLO] {name} {extra}")


def main() -> int:
    if not wait_for_server():
        print("  [FALLO] el servidor no respondió en /api/health")
        return 1
    c = httpx.Client(base_url=BASE, timeout=30)

    # Salud
    r = c.get("/api/health")
    check("health 200", r.status_code == 200, str(r.status_code))

    # Login admin
    r = c.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    check("login admin 200", r.status_code == 200, r.text[:200])
    admin_token = r.json().get("access_token", "")
    admin_h = {"Authorization": f"Bearer {admin_token}"}

    # /me
    r = c.get("/api/auth/me", headers=admin_h)
    check("me devuelve perfil admin", r.status_code == 200 and r.json()["profile"] == "admin")
    check("admin tiene manage_users", "manage_users" in r.json().get("permissions", []))

    # Equipos
    r = c.get("/api/teams", headers=admin_h)
    check("48 equipos", r.status_code == 200 and len(r.json()) == 48, str(len(r.json())))

    # Simulación
    r = c.get("/api/simulations/latest", headers=admin_h)
    sim = r.json()
    check("simulación con 48 probs", r.status_code == 200 and len(sim["probs"]) == 48)
    top = sim["probs"][0]
    check("favorito coherente (top p_winner > 8%)", top["p_winner"] > 0.08, str(top))
    total_win = round(sum(p["p_winner"] for p in sim["probs"]), 2)
    check("suma P(campeón) ~ 1.0", abs(total_win - 1.0) < 0.02, str(total_win))

    # Partidos de grupo
    r = c.get("/api/matches", params={"stage": "group"}, headers=admin_h)
    matches = r.json()
    check("72 partidos de grupo", r.status_code == 200 and len(matches) == 72, str(len(matches)))
    check("partido trae predicción", matches[0].get("prediction") is not None)

    # --- RBAC: crear un cliente 'viewer' (limpiando corridas previas) ---
    users = c.get("/api/admin/users", headers=admin_h).json()
    for u in users:
        if u["username"] == "cliente1":
            c.delete(f"/api/admin/users/{u['id']}", headers=admin_h)
    r = c.post(
        "/api/admin/users",
        headers=admin_h,
        json={"username": "cliente1", "password": "secret123", "email": "c1@local", "profile": "viewer"},
    )
    check("crear usuario viewer 201", r.status_code == 201, r.text[:200])

    # Login como viewer y comprobar permisos
    r = c.post("/api/auth/login", data={"username": "cliente1", "password": "secret123"})
    viewer_token = r.json().get("access_token", "")
    viewer_h = {"Authorization": f"Bearer {viewer_token}"}
    r = c.get("/api/teams", headers=viewer_h)
    check("viewer puede ver equipos", r.status_code == 200)
    r = c.get("/api/admin/users", headers=viewer_h)
    check("viewer NO puede gestionar usuarios (403)", r.status_code == 403, str(r.status_code))
    r = c.post("/api/simulations/run", headers=viewer_h, json={"runs": 100})
    check("viewer NO puede correr simulación (403)", r.status_code == 403, str(r.status_code))

    # --- Cupo por perfil: crear un perfil con cupo 1 y forzar 409 ---
    profiles = c.get("/api/admin/profiles", headers=admin_h).json()
    for p in profiles:
        if p["name"] == "vip":
            # borrar usuarios y el perfil para idempotencia
            for u in c.get("/api/admin/users", headers=admin_h).json():
                if u["profile"] == "vip":
                    c.delete(f"/api/admin/users/{u['id']}", headers=admin_h)
            c.delete(f"/api/admin/profiles/{p['id']}", headers=admin_h)
    r = c.post(
        "/api/admin/profiles",
        headers=admin_h,
        json={"name": "vip", "description": "cupo 1", "max_users": 1, "permissions": ["view_dashboard"]},
    )
    check("crear perfil con cupo 1", r.status_code == 201, r.text[:200])
    r = c.post(
        "/api/admin/users",
        headers=admin_h,
        json={"username": "vip1", "password": "secret123", "profile": "vip"},
    )
    check("primer usuario en perfil vip OK", r.status_code == 201, r.text[:200])
    r = c.post(
        "/api/admin/users",
        headers=admin_h,
        json={"username": "vip2", "password": "secret123", "profile": "vip"},
    )
    check("segundo usuario excede cupo (409)", r.status_code == 409, str(r.status_code))

    # --- Tracking: registrar un resultado dispara recálculo ---
    sim_before = c.get("/api/simulations/latest", headers=admin_h).json()["id"]
    match_id = matches[0]["id"]
    r = c.post(f"/api/matches/{match_id}/result", headers=admin_h, json={"home_score": 2, "away_score": 1})
    check("registrar resultado 200", r.status_code == 200, r.text[:200])
    check("partido queda 'finished'", r.json()["status"] == "finished")
    sim_after = c.get("/api/simulations/latest", headers=admin_h).json()["id"]
    check("se recalculó la simulación", sim_after > sim_before, f"{sim_before} -> {sim_after}")

    # --- Sync en vivo sin API key configurada -> 400 claro ---
    r = c.post("/api/matches/sync", headers=admin_h)
    check("sync sin API key responde 400", r.status_code == 400, str(r.status_code))

    print(f"\nResultado: {ok} OK, {fail} fallos")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
