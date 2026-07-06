import httpx, sys
sys.stdout.reconfigure(encoding='utf-8')

r = httpx.post("http://localhost:8000/api/auth/login",
               data={"username": "admin", "password": "0tOqq22YHkli9X_j"},
               headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=5)
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

matches = httpx.get("http://localhost:8000/api/matches", headers=h, timeout=5).json()
print(f"Total partidos: {len(matches)}")

shown = 0
for m in matches:
    mid = m["id"]
    ht = m["home_team"]["display_name"]
    at = m["away_team"]["display_name"]
    bets = httpx.get(f"http://localhost:8000/api/bets/matches/{mid}", headers=h, timeout=5).json()
    pm = bets.get("player_markets", [])
    if not pm:
        continue
    print(f"\n{ht} vs {at} (id={mid})")
    for p in pm:
        name = p.get("player", "?")
        sot = p.get("sot_per_90", 0)
        src = p.get("source", "?")
        lines = p.get("lines", [])
        best_line = lines[0] if lines else {}
        print(f"  {name}: SOT/90={sot:.3f} [{src}] | linea 0.5: {best_line.get('prob',0)*100:.1f}%")
    shown += 1
    if shown >= 5:
        break

if shown == 0:
    print("Sin player_markets en ningun partido — comprobando primer partido crudo:")
    m = matches[0]
    mid = m["id"]
    bets = httpx.get(f"http://localhost:8000/api/bets/matches/{mid}", headers=h, timeout=5).json()
    print(list(bets.keys()))
    print("home_team_id:", m["home_team"]["id"])
