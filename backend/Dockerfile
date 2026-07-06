# Imagen del backend (Servidor A). Contexto de build = raíz del repo.
FROM python:3.13-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY ml/ ml/
COPY data/seed/ data/seed/
RUN mkdir -p data/raw

EXPOSE 8000

# La inicialización de la BD (tablas, permisos, admin, equipos) ocurre en el arranque.
# El entrenamiento (Elo + simulación) se ejecuta una vez con:
#   docker compose -f deploy/docker-compose.backend.yml exec backend python -m ml.train
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
