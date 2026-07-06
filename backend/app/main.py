"""Aplicación FastAPI: inicialización, CORS, rate limiting y routers."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from .api import admin, auth, bets, matches, metrics, simulations, teams
from .config import settings
from .core.ratelimit import limiter
from .database import SessionLocal
from .scheduler import start_scheduler, stop_scheduler
from .services.seed import initialize_database

logger = logging.getLogger("wc2026")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        initialize_database(db)
        logger.info("Base de datos inicializada (permisos, perfiles, admin, equipos, partidos).")
    finally:
        db.close()
    start_scheduler()  # sync en vivo (solo si hay API key)
    yield
    stop_scheduler()


_prod = settings.environment == "production"
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    # En producción ocultamos la documentación interactiva y el esquema OpenAPI.
    docs_url=None if _prod else "/docs",
    redoc_url=None if _prod else "/redoc",
    openapi_url=None if _prod else "/openapi.json",
)

# Rate limiting global.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS (solo necesario en topología de hosts separados).
if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _rate_limited():
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=429, content={"detail": "Demasiadas peticiones, intenta luego."})


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(teams.router)
app.include_router(matches.router)
app.include_router(simulations.router)
app.include_router(bets.router)
app.include_router(metrics.router)

# ---- Servir el frontend (SPA) desde el mismo backend (despliegue en un solo equipo) ----
# Si existe frontend/dist (build de producción), se sirve la web en el mismo puerto 8000,
# de modo que los dispositivos de la LAN abren http://<IP>:8000 y obtienen la app completa.
from pathlib import Path as _Path  # noqa: E402

from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

_DIST = _Path("frontend/dist")
if (_DIST / "index.html").exists():
    if (_DIST / "assets").exists():
        app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _spa(full_path: str):
        if full_path.startswith("api"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        candidate = _DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_DIST / "index.html"))
