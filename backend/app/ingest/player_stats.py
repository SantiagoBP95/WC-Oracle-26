"""Ingesta de estadísticas de disparos a puerta por jugador.

Fuentes (Fase 1 - internacional):
  1. StatsBomb Open Data — eventos reales de:
       • WC 2018         (43, 3)    peso 0.30
       • WC 2022         (43, 106)  peso 0.70
       • UEFA Euro 2020  (55, 43)   peso 0.50
       • UEFA Euro 2024  (55, 282)  peso 1.00  ← nuevo
       • Copa América 24 (223, 282) peso 1.00  ← nuevo
       • AFCON 2023      (1267,107) peso 0.90  ← nuevo
     Calcula SOT/90 y Shots/90 desde eventos de disparo reales.

  2. FBref vía soccerdata — estadísticas de torneos recientes:
       • UEFA Euro 2024, Copa América 2024, FIFA WC 2022
     Solo delanteros y mediocampistas (FW/MF).

Flujo:
  - Por jugador y torneo se calcula SOT/90 ponderado por recencia.
  - Se combina StatsBomb (60%) + FBref (40%) cuando hay ambas fuentes.
  - Solo se guardan jugadores cuyo equipo exista en la tabla `teams` (WC2026).
  - Upsert en la tabla `players`.
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict

import pandas as pd
from sqlalchemy.orm import Session

from ..models.football import Player, Team

logger = logging.getLogger("wc2026.ingest.players")

# ── Pesos por recencia de cada torneo ─────────────────────────────────────────
# Cuanto más reciente y competitivo, mayor peso.
_SB_TOURNAMENTS: list[tuple[str, int, int, float]] = [
    # (label,        competition_id, season_id, recency_weight)
    ("WC2018",       43,   3,   0.30),
    ("Euro2020",     55,  43,   0.50),
    ("WC2022",       43, 106,   0.70),
    ("AFCON2023",  1267, 107,   0.90),
    ("Euro2024",     55, 282,   1.00),
    # CopaAm2024 (223, 282) disabled: statsbombpy hangs on a match download
    # Re-enable once the open-data repo is cloned locally
]

# ── Torneos FBref recientes ───────────────────────────────────────────────────
_FBREF_RECENT: list[tuple[str, int]] = [
    ("INT-World Cup",            2022),
    ("INT-European Championship", 2024),
]

# ── Resultados de disparo que cuentan como SOT ───────────────────────────────
_SOT_OUTCOMES = {"Goal", "Saved"}

# ── Posiciones que incluimos ──────────────────────────────────────────────────
_POSITIONS_KEEP = {"FW", "MF", "FW,MF", "MF,FW", "FW,DF", "AM"}

# ── Mapeo: nombre de equipo en StatsBomb/FBref → nombre en nuestra BD ─────────
_COUNTRY_MAP: dict[str, str] = {
    "Argentina": "Argentina", "France": "France", "England": "England",
    "Spain": "Spain", "Brazil": "Brazil", "Germany": "Germany",
    "Portugal": "Portugal", "Netherlands": "Netherlands",
    "Belgium": "Belgium", "Croatia": "Croatia", "Morocco": "Morocco",
    "Senegal": "Senegal", "Japan": "Japan", "South Korea": "South Korea",
    "Australia": "Australia", "Mexico": "Mexico",
    "United States": "United States", "USA": "United States",
    "Canada": "Canada", "Colombia": "Colombia", "Uruguay": "Uruguay",
    "Ecuador": "Ecuador", "Chile": "Chile", "Peru": "Peru",
    "Venezuela": "Venezuela", "Bolivia": "Bolivia",
    "Paraguay": "Paraguay", "Panama": "Panama", "Costa Rica": "Costa Rica",
    "Honduras": "Honduras", "Jamaica": "Jamaica",
    "Nigeria": "Nigeria", "Cameroon": "Cameroon", "Ghana": "Ghana",
    "Ivory Coast": "Ivory Coast", "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Egypt": "Egypt", "Tunisia": "Tunisia", "Algeria": "Algeria",
    "South Africa": "South Africa", "Mali": "Mali",
    "DR Congo": "DR Congo", "Cape Verde": "Cape Verde",
    "Saudi Arabia": "Saudi Arabia",
    "Iran": "IR Iran", "IR Iran": "IR Iran", "Qatar": "Qatar",
    "Japan": "Japan", "Iraq": "Iraq", "Jordan": "Jordan",
    "Uzbekistan": "Uzbekistan", "South Korea": "South Korea",
    "Korea Republic": "South Korea",
    "New Zealand": "New Zealand", "Switzerland": "Switzerland",
    "Austria": "Austria", "Sweden": "Sweden", "Norway": "Norway",
    "Czech Republic": "Czech Republic", "Czechia": "Czech Republic",
    "Scotland": "Scotland", "Turkey": "Turkey", "Türkiye": "Turkey",
    "Serbia": "Serbia", "Poland": "Poland", "Denmark": "Denmark",
    "Ukraine": "Ukraine", "Slovakia": "Slovakia",
    "Slovenia": "Slovenia", "Hungary": "Hungary",
    "Romania": "Romania", "Greece": "Greece", "Albania": "Albania",
    "Iceland": "Iceland", "Finland": "Finland", "Georgia": "Georgia",
    "Bosnia and Herzegovina": "Bosnia-Herzegovina",
    "Bosnia-Herzegovina": "Bosnia-Herzegovina",
    "North Macedonia": "North Macedonia",
    "Republic of Ireland": "Republic of Ireland",
    "Northern Ireland": "Northern Ireland",
    "Haiti": "Haiti", "Curacao": "Curacao", "Curaçao": "Curacao",
}


# ─────────────────────────────────────────────────────────────────────────────
#  StatsBomb
# ─────────────────────────────────────────────────────────────────────────────

def _parse_sb_time(val, default: float) -> float:
    """Parse a StatsBomb position time field (dict, str 'MM:SS', int, or None)."""
    if val is None:
        return default
    if isinstance(val, dict):
        return float(val.get("minute", default))
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        parts = val.split(":")
        try:
            return float(parts[0]) + (float(parts[1]) / 60 if len(parts) > 1 else 0)
        except (ValueError, IndexError):
            return default
    return default


def _ingest_statsbomb() -> pd.DataFrame:
    """
    Extrae SOT/90 por jugador de todos los torneos configurados.
    Devuelve DataFrame con columnas:
        [name, nationality, sot_per_90, shots_per_90, minutes, source]
    Los torneos más recientes tienen mayor peso en el promedio ponderado.
    """
    try:
        from statsbombpy import sb
        # Override statsbombpy's temp cache with a persistent one so re-runs skip HTTP
        try:
            from requests_cache import install_cache
            import pathlib
            _cache_dir = pathlib.Path.home() / ".wc2026_statsbomb_cache"
            _cache_dir.mkdir(exist_ok=True)
            install_cache(str(_cache_dir / "sb_events"), backend="sqlite", expire_after=86400 * 30)
            logger.info("StatsBomb: usando caché persistente en %s", _cache_dir)
        except Exception:
            pass
        # Patch at adapter level so timeout works even through requests_cache sessions
        try:
            import socket
            socket.setdefaulttimeout(30)
        except Exception:
            pass
    except ImportError:
        logger.warning("statsbombpy no instalado, omitiendo StatsBomb")
        return pd.DataFrame()

    # {player_name: {weight_sum, weighted_sot, weighted_shots, team, total_mins}}
    player_agg: dict[str, dict] = defaultdict(lambda: {
        "weight_sum": 0.0, "w_sot": 0.0, "w_shots": 0.0,
        "team": "", "total_mins": 0,
    })

    for label, comp_id, season_id, weight in _SB_TOURNAMENTS:
        logger.info("StatsBomb: cargando %s (comp=%d season=%d w=%.2f)…",
                    label, comp_id, season_id, weight)
        try:
            matches = sb.matches(
                competition_id=comp_id, season_id=season_id,
                creds={"user": "", "passwd": ""},
            )
        except Exception as e:
            logger.warning("StatsBomb %s: error al obtener partidos: %s", label, e)
            continue

        logger.info("  %s: %d partidos", label, len(matches))

        # Acumuladores por partido → jugador: {sot, shots, minutes}
        tourney_acc: dict[str, dict] = defaultdict(
            lambda: {"team": "", "sot": 0, "shots": 0, "minutes": 0.0}
        )

        for match_id in matches["match_id"]:
            try:
                events = sb.events(match_id=match_id, fmt="dataframe")
            except Exception:
                continue

            # Minutos jugados (desde lineups)
            try:
                lineups = sb.lineups(match_id=match_id)
                for team_name, lineup_df in lineups.items():
                    for _, player_row in lineup_df.iterrows():
                        p_name = player_row["player_name"]
                        positions = player_row.get("positions") or []
                        mins = 0.0
                        for pos_entry in positions:
                            if not isinstance(pos_entry, dict):
                                continue
                            fm = _parse_sb_time(pos_entry.get("from"), default=0.0)
                            tm = _parse_sb_time(pos_entry.get("to"), default=90.0)
                            mins += max(0.0, tm - fm)
                        if mins <= 0:
                            mins = 90.0  # fallback
                        tourney_acc[p_name]["team"] = team_name
                        tourney_acc[p_name]["minutes"] += mins
            except Exception:
                pass

            # Eventos de disparo
            if "type" not in events.columns:
                continue
            shots = events[events["type"] == "Shot"]
            for _, shot in shots.iterrows():
                p_name = shot.get("player", "")
                if not p_name or not isinstance(p_name, str):
                    continue
                team = shot.get("team", "")
                outcome = ""
                shot_outcome = shot.get("shot_outcome", {})
                if isinstance(shot_outcome, dict):
                    outcome = shot_outcome.get("name", "")
                elif isinstance(shot_outcome, str):
                    outcome = shot_outcome
                tourney_acc[p_name]["team"] = team
                tourney_acc[p_name]["shots"] += 1
                if outcome in _SOT_OUTCOMES:
                    tourney_acc[p_name]["sot"] += 1

        # Agregar al acumulador global con el peso del torneo
        for p_name, acc in tourney_acc.items():
            mins = max(acc["minutes"], 1.0)
            sot_90 = acc["sot"] / mins * 90.0
            shots_90 = acc["shots"] / mins * 90.0
            g = player_agg[p_name]
            g["weight_sum"] += weight
            g["w_sot"] += weight * sot_90
            g["w_shots"] += weight * shots_90
            g["team"] = acc["team"] or g["team"]
            g["total_mins"] += int(mins)

    if not player_agg:
        return pd.DataFrame()

    rows = []
    for p_name, g in player_agg.items():
        ws = g["weight_sum"]
        if ws <= 0:
            continue
        rows.append({
            "name": p_name,
            "nationality": _COUNTRY_MAP.get(g["team"], g["team"]),
            "sot_per_90": round(g["w_sot"] / ws, 3),
            "shots_per_90": round(g["w_shots"] / ws, 3),
            "minutes": g["total_mins"],
            "source": "statsbomb",
        })

    df = pd.DataFrame(rows)
    logger.info("StatsBomb: %d jugadores extraídos en total", len(df))
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  FBref vía soccerdata
# ─────────────────────────────────────────────────────────────────────────────

def _ingest_fbref() -> pd.DataFrame:
    try:
        import soccerdata as sd
    except ImportError:
        logger.warning("soccerdata no instalado, omitiendo FBref")
        return pd.DataFrame()

    frames: list[dict] = []

    for league, season in _FBREF_RECENT:
        logger.info("FBref: cargando %s %s…", league, season)
        try:
            fbref = sd.FBref(leagues=[league], seasons=[season])
            shooting = fbref.read_player_season_stats(stat_type="shooting")
        except Exception as e:
            logger.warning("FBref %s %s error: %s", league, season, e)
            continue

        if shooting is None or shooting.empty:
            logger.warning("FBref %s %s: sin datos", league, season)
            continue

        shooting = shooting.reset_index()

        # Flatten MultiIndex/tuple columns (FBref returns ('Standard','SoT') style)
        def _flat(c) -> str:
            if isinstance(c, tuple):
                return "_".join(str(p) for p in c if str(p)).lower()
            return str(c).lower()
        shooting.columns = [_flat(c) for c in shooting.columns]

        def gcol(*candidates: str) -> str | None:
            for c in candidates:
                if c in shooting.columns:
                    return c
            return None

        c_player = gcol("player")
        c_nation = gcol("nation", "nationality", "country", "team")
        c_pos    = gcol("pos", "position")
        c_90s    = gcol("90s", "mins_per_90", "playing_time_90s")
        c_sh     = gcol("standard_sh", "sh", "shots", "shots_total")
        c_sot    = gcol("standard_sot", "sot", "shots_on_target")

        if not all([c_player, c_90s, c_sh, c_sot]):
            logger.warning("FBref %s %s: columnas no encontradas. Disponibles: %s",
                           league, season, list(shooting.columns[:20]))
            continue

        for _, row in shooting.iterrows():
            name = str(row[c_player]) if c_player else ""
            if name in ("nan", "", "Players"):
                continue
            nation = str(row[c_nation]) if c_nation else ""
            pos = str(row[c_pos]) if c_pos else "FW"
            try:
                nineties = float(row[c_90s] or 0)
                shots    = float(row[c_sh] or 0)
                sot      = float(row[c_sot] or 0)
            except (ValueError, TypeError):
                continue

            if nineties < 0.5:
                continue
            pos_upper = pos.upper()
            if not any(p in pos_upper for p in ("FW", "MF")):
                continue

            nationality = _COUNTRY_MAP.get(nation, nation)
            frames.append({
                "name": name,
                "nationality": nationality,
                "position": pos_upper[:5],
                "sot_per_90": round(sot / nineties, 3),
                "shots_per_90": round(shots / nineties, 3),
                "minutes": int(nineties * 90),
                "source": "fbref",
            })

    if not frames:
        logger.warning("FBref: sin datos en ningún torneo")
        return pd.DataFrame()

    df = pd.DataFrame(frames)
    # Si un jugador aparece en varios torneos, promedio simple (todos son recientes)
    df = (
        df.groupby("name")
        .agg(
            nationality=("nationality", "first"),
            position=("position", "first"),
            sot_per_90=("sot_per_90", "mean"),
            shots_per_90=("shots_per_90", "mean"),
            minutes=("minutes", "sum"),
            source=("source", "first"),
        )
        .reset_index()
    )
    logger.info("FBref: %d jugadores extraídos", len(df))
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  Merge: StatsBomb (60%) + FBref (40%)
# ─────────────────────────────────────────────────────────────────────────────

def _merge(sb_df: pd.DataFrame, fb_df: pd.DataFrame) -> pd.DataFrame:
    if sb_df.empty and fb_df.empty:
        return pd.DataFrame()
    if sb_df.empty:
        return fb_df.assign(source="fbref")
    if fb_df.empty:
        return sb_df.assign(source="statsbomb")

    merged = pd.merge(sb_df, fb_df, on="name", how="outer", suffixes=("_sb", "_fb"))
    rows = []
    for _, r in merged.iterrows():
        sb_sot = r.get("sot_per_90_sb", float("nan"))
        fb_sot = r.get("sot_per_90_fb", float("nan"))
        sb_sh  = r.get("shots_per_90_sb", float("nan"))
        fb_sh  = r.get("shots_per_90_fb", float("nan"))

        def _f(v):
            return 0.0 if (v is None or (isinstance(v, float) and math.isnan(v))) else float(v)

        sb_miss = math.isnan(sb_sot) if isinstance(sb_sot, float) else sb_sot is None
        fb_miss = math.isnan(fb_sot) if isinstance(fb_sot, float) else fb_sot is None

        if sb_miss and fb_miss:
            continue
        elif sb_miss:
            sot, sh, source = _f(fb_sot), _f(fb_sh), "fbref"
        elif fb_miss:
            sot, sh, source = _f(sb_sot), _f(sb_sh), "statsbomb"
        else:
            sot    = 0.60 * _f(sb_sot) + 0.40 * _f(fb_sot)
            sh     = 0.60 * _f(sb_sh)  + 0.40 * _f(fb_sh)
            source = "merged"

        def _s(v) -> str:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return ""
            return str(v)

        nationality = _s(r.get("nationality_fb")) or _s(r.get("nationality_sb")) or ""
        position    = _s(r.get("position_fb"))    or _s(r.get("position_sb"))    or "FW"
        minutes     = int(_f(r.get("minutes_sb")) + _f(r.get("minutes_fb")))

        rows.append({
            "name":         r["name"],
            "nationality":  str(nationality),
            "position":     str(position)[:5],
            "sot_per_90":   round(sot, 3),
            "shots_per_90": round(sh, 3),
            "minutes":      minutes,
            "source":       source,
        })

    return pd.DataFrame(rows)


# ─────────────────────────────────────────────────────────────────────────────
#  Punto de entrada
# ─────────────────────────────────────────────────────────────────────────────

def run_ingestion(db: Session) -> dict:
    """Ingestar jugadores y hacer upsert en la DB. Devuelve resumen."""
    logger.info("Iniciando ingesta de jugadores (StatsBomb multi-torneo + FBref)…")

    # Mapa de equipos WC2026: name / display_name → team_id
    teams = db.query(Team).all()
    team_map: dict[str, int] = {}
    for t in teams:
        team_map[t.name] = t.id
        if t.display_name:
            team_map[t.display_name] = t.id

    sb_df  = _ingest_statsbomb()
    fb_df  = _ingest_fbref()
    merged = _merge(sb_df, fb_df)

    if merged.empty:
        logger.warning("Ingesta vacía: sin datos")
        return {"inserted": 0, "updated": 0, "skipped": 0}

    # Filtro mínimo
    merged = merged[merged["minutes"] >= 45].copy()

    existing: dict[tuple[str, int | None], Player] = {
        (p.name, p.team_id): p for p in db.query(Player).all()
    }
    inserted = updated = skipped = 0

    for _, row in merged.iterrows():
        nat = row["nationality"]
        team_id = team_map.get(nat)
        if team_id is None:
            skipped += 1
            continue

        key = (row["name"], team_id)
        if key in existing:
            p = existing[key]
            p.sot_per_90    = row["sot_per_90"]
            p.shots_per_90  = row["shots_per_90"]
            p.minutes_played = row["minutes"]
            p.source         = row["source"]
            updated += 1
        else:
            db.add(Player(
                name=row["name"],
                nationality=nat,
                team_id=team_id,
                position=row.get("position", "FW"),
                sot_per_90=row["sot_per_90"],
                shots_per_90=row["shots_per_90"],
                minutes_played=row["minutes"],
                source=row["source"],
                in_squad=True,
            ))
            inserted += 1

    db.commit()
    summary = {"inserted": inserted, "updated": updated, "skipped": skipped}
    logger.info("Ingesta completada: %s", summary)
    return summary
