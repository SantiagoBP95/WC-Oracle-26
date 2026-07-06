"""
Sincroniza los squads oficiales del Mundial 2026 desde football-data.org
y actualiza el campo in_squad en la tabla players.

Uso:
    python scripts/sync_squads.py [--dry-run]

Requiere FOOTBALL_DATA_ORG_TOKEN en .env
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from unicodedata import normalize, category

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import httpx
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("sync_squads")

FOOTBALL_DATA_URL = "https://api.football-data.org/v4/competitions/WC/teams"


def _norm(name: str) -> str:
    """Normaliza nombre: minúsculas, sin diacríticos, sin guiones ni puntos."""
    nfkd = normalize("NFKD", name)
    ascii_str = "".join(c for c in nfkd if category(c) != "Mn")
    return "".join(c for c in ascii_str.lower() if c.isalpha() or c == " ").strip()


def fetch_official_squads(token: str) -> dict[str, list[str]]:
    """Devuelve {team_name_api: [player_name, ...]} para los 48 equipos."""
    log.info("Consultando football-data.org…")
    r = httpx.get(
        FOOTBALL_DATA_URL,
        headers={"X-Auth-Token": token},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    squads: dict[str, list[str]] = {}
    for team in data.get("teams", []):
        team_name = team["name"]
        players = [p["name"] for p in team.get("squad", [])]
        squads[team_name] = players
    log.info("  %d equipos, %d jugadores en total",
             len(squads), sum(len(v) for v in squads.values()))
    return squads


def sync(dry_run: bool = False) -> dict:
    token = os.getenv("FOOTBALL_DATA_ORG_TOKEN", "")
    if not token:
        log.error("FOOTBALL_DATA_ORG_TOKEN no configurado en .env")
        sys.exit(1)

    squads = fetch_official_squads(token)

    # Construir conjuntos normalizados de todos los jugadores convocados
    # También guardamos tokens (palabras) de cada nombre oficial para matching parcial:
    # "Cristiano Ronaldo" casa con "Cristiano Ronaldo dos Santos Aveiro"
    official_norm: set[str] = set()
    official_tokens: list[list[str]] = []   # lista de listas de palabras por jugador
    for players in squads.values():
        for pname in players:
            norm = _norm(pname)
            official_norm.add(norm)
            official_tokens.append(norm.split())

    log.info("Total jugadores convocados: %d", len(official_norm))

    from app.database import SessionLocal
    from app.models.football import Player

    import warnings
    warnings.filterwarnings("ignore")

    db = SessionLocal()
    try:
        all_players = db.query(Player).all()
        log.info("Jugadores en DB: %d", len(all_players))

        marked_in = marked_out = unmatched = 0
        unmatched_names: list[str] = []

        def _is_match(db_name: str) -> bool:
            norm = _norm(db_name)
            # Exact match
            if norm in official_norm:
                return True
            # Substring match: official "kylian mbappe" inside DB "kylian mbappe lottin"
            for tokens in official_tokens:
                if len(tokens) >= 2 and norm.startswith(" ".join(tokens)):
                    return True
            # Reverse: DB name subset of official (rare but possible)
            db_tokens = norm.split()
            if len(db_tokens) >= 2:
                joined = " ".join(db_tokens)
                for off_norm in official_norm:
                    if off_norm.startswith(joined):
                        return True
            return False

        for p in all_players:
            is_official = _is_match(p.name)

            if is_official:
                if not dry_run:
                    p.in_squad = True
                marked_in += 1
            else:
                if not dry_run:
                    p.in_squad = False
                marked_out += 1
                unmatched_names.append(p.name)

        if not dry_run:
            db.commit()
            log.info("Commit realizado.")

        # Mostrar algunos ejemplos de jugadores marcados fuera
        if unmatched_names:
            log.info("Ejemplos de jugadores marcados out (%d total):", marked_out)
            for name in sorted(unmatched_names)[:20]:
                log.info("  - %s", name)

        summary = {
            "in_squad_true": marked_in,
            "in_squad_false": marked_out,
            "dry_run": dry_run,
        }
        log.info("Resultado: %s", summary)
        return summary
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync official WC2026 squads")
    parser.add_argument("--dry-run", action="store_true",
                        help="No escribe en DB, solo muestra qué cambiaría")
    args = parser.parse_args()
    sync(dry_run=args.dry_run)
