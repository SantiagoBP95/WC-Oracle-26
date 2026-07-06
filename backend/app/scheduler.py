"""Scheduler de sincronización en vivo (APScheduler).

Solo se activa si hay API_FOOTBALL_KEY. Sondea API-Football periódicamente y aplica
los resultados finalizados, recalculando las probabilidades cuando hay cambios.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .config import settings
from .database import SessionLocal
from .services.livesync import active_provider, sync_from_api

logger = logging.getLogger("wc2026.scheduler")
scheduler = BackgroundScheduler(daemon=True)


def _sync_job() -> None:
    db = SessionLocal()
    try:
        result = sync_from_api(db)
        if result["updated"]:
            logger.info("Sync en vivo: %s partidos actualizados.", result["updated"])
    except Exception as exc:  # noqa: BLE001 - el job nunca debe tumbar el scheduler
        logger.warning("Sync en vivo falló: %s", exc)
    finally:
        db.close()


def start_scheduler() -> bool:
    """Arranca el job periódico si hay una fuente configurada. True si quedó activo."""
    provider = active_provider()
    if provider is None:
        logger.info("Scheduler de sync desactivado (sin FOOTBALL_DATA_ORG_TOKEN ni API_FOOTBALL_KEY).")
        return False
    scheduler.add_job(
        _sync_job,
        "interval",
        minutes=settings.live_sync_interval_minutes,
        id="livesync",
        replace_existing=True,
        next_run_time=None,
    )
    if not scheduler.running:
        scheduler.start()
    logger.info("Scheduler de sync activo (%s, cada %s min).", provider, settings.live_sync_interval_minutes)
    return True


def stop_scheduler() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)
