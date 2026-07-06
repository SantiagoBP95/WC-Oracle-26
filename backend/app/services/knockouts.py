"""Materialización de las eliminatorias a partir de resultados reales.

Cuando la fase de grupos está completa, deriva la Ronda de 32 del bracket oficial y la
crea como partidos concretos (filas Match). A medida que se registran los resultados de
cada ronda, materializa la siguiente (Octavos → Cuartos → Semis → Final). Idempotente.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ml.simulation.bracket import ROUND_TEMPLATES, resolve_r32

from ..models.football import Match, Team

GROUP_MATCH_COUNT = 72
R32_SLOTS = [f"M{73 + i}" for i in range(16)]


def _winner_id(m: Match | None) -> int | None:
    """Equipo que avanza: el de mayor marcador, o el de penaltis (winner_team_id)."""
    if m is None or m.status != "finished" or m.home_score is None or m.away_score is None:
        return None
    if m.home_score > m.away_score:
        return m.home_team_id
    if m.away_score > m.home_score:
        return m.away_team_id
    return m.winner_team_id  # empate en 90' -> penaltis


def _upsert_round(db: Session, stage: str, slots: list[str], pairs: list[tuple]) -> None:
    existing = {m.slot: m for m in db.query(Match).filter(Match.stage == stage).all()}
    for slot, (home_id, away_id) in zip(slots, pairs):
        m = existing.get(slot)
        if m is None:
            db.add(
                Match(
                    stage=stage,
                    slot=slot,
                    is_neutral=True,
                    status="scheduled",
                    home_team_id=home_id,
                    away_team_id=away_id,
                )
            )
        elif m.status != "finished":  # no pisar un partido ya jugado
            m.home_team_id, m.away_team_id = home_id, away_id
    db.flush()


def materialize_knockouts(db: Session) -> dict:
    """Crea/actualiza las rondas de eliminatorias según los resultados disponibles."""
    group_matches = db.query(Match).filter(Match.stage == "group").all()
    finished = [m for m in group_matches if m.status == "finished" and m.home_score is not None]
    if not group_matches or len(finished) < len(group_matches):
        return {
            "status": "group_stage_incomplete",
            "finished": len(finished),
            "total": len(group_matches),
        }

    name_by_id = {t.id: t.name for t in db.query(Team).all()}
    id_by_name = {v: k for k, v in name_by_id.items()}

    group_results: dict[str, list] = {}
    for m in finished:
        group_results.setdefault(m.group_label, []).append(
            (name_by_id[m.home_team_id], name_by_id[m.away_team_id], m.home_score, m.away_score)
        )

    r32 = resolve_r32(group_results)
    _upsert_round(db, "R32", R32_SLOTS, [(id_by_name[h], id_by_name[a]) for h, a in r32])

    created = {"R32": 16}
    prev_slots = R32_SLOTS
    for stage, src, pairs in ROUND_TEMPLATES:
        prev = {m.slot: m for m in db.query(Match).filter(Match.stage == src).all()}
        winners = [_winner_id(prev.get(slot)) for slot in prev_slots]
        if any(w is None for w in winners):
            break  # la ronda previa aún no está decidida
        round_pairs = [(winners[i], winners[j]) for i, j in pairs]
        new_slots = [f"{stage}_{k + 1}" for k in range(len(pairs))]
        _upsert_round(db, stage, new_slots, round_pairs)
        created[stage] = len(pairs)
        prev_slots = new_slots

    db.commit()
    return {"status": "ok", "created": created}
