"""Ingesta del histórico de partidos internacionales (dataset martj42).

Fuente primaria: GitHub raw (sin autenticación). Alternativa: descargar el CSV a mano
a data/raw/results.csv. ~50k partidos desde 1872.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd

RAW_DIR = Path("data/raw")
RESULTS_CSV = RAW_DIR / "results.csv"

DEFAULT_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"

REQUIRED_COLUMNS = [
    "date", "home_team", "away_team", "home_score", "away_score", "tournament", "neutral",
]


def download_results(url: str = DEFAULT_URL, dest: Path = RESULTS_CSV, force: bool = False) -> Path:
    """Descarga results.csv si no existe (o si force=True)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not force:
        return dest
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    return dest


def load_results(path: Path = RESULTS_CSV) -> pd.DataFrame:
    """Carga y limpia el histórico: parsea fechas, descarta filas sin marcador."""
    df = pd.read_csv(path)
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Faltan columnas en el dataset: {missing}")

    df = df[REQUIRED_COLUMNS].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "home_score", "away_score"])
    df["home_score"] = df["home_score"].astype(int)
    df["away_score"] = df["away_score"].astype(int)
    df["neutral"] = df["neutral"].astype(bool)
    df = df.sort_values("date").reset_index(drop=True)
    return df


def get_results(url: str = DEFAULT_URL, force: bool = False) -> pd.DataFrame:
    """Conveniencia: descarga (si hace falta) y carga el histórico limpio."""
    path = download_results(url=url, force=force)
    return load_results(path)
