# Arquitectura y despliegue

## Visión general

```
                         LAN
[Dispositivos cliente] --HTTPS 443--> [SERVIDOR B: Caddy + SPA React]
   (usuario+contraseña)                   │  sirve / (SPA)
                                          └─ /api/* --proxy--> [SERVIDOR A (este equipo)]
                                                                 FastAPI + ML + SQLite + scheduler
```

- **Servidor A (este equipo):** ejecuta el backend, los modelos (Elo → Dixon-Coles → Monte Carlo), la base SQLite y el scheduler. **Todo el cómputo ocurre aquí.**
- **Servidor B (otro Linux con Docker):** sirve la página (build estático) y reenvía las llamadas `/api/*` al Servidor A. Es el único punto que tocan los clientes.

Beneficio: mismo origen para el cliente (sin CORS ni *mixed content*), un solo certificado, y separación clara entre entrega (B) y cómputo (A).

## Capas del backend (Servidor A)

| Módulo | Rol |
|--------|-----|
| `backend/app/main.py` | App FastAPI, CORS, rate limiting, init en startup |
| `backend/app/models/` | ORM: RBAC (`User/Profile/Permission`) y dominio (`Team/Match/Prediction/SimulationRun/...`) |
| `backend/app/core/` | `security` (JWT/bcrypt), `deps` (usuario actual), `rbac` (permisos + cupos), `ratelimit` |
| `backend/app/api/` | Routers: `auth`, `admin`, `teams`, `matches`, `simulations` |
| `backend/app/services/` | `seed` (init idempotente), `modeling` (Elo→predicciones→simulación), `audit` |
| `ml/` | Núcleo: `ingest`, `models/elo`, `models/dixon_coles`, `simulation/monte_carlo`, `train` |

## Modelo de predicción

1. **Elo propio** calculado desde ~50k partidos internacionales (`ml/models/elo.py`).
2. **Dixon-Coles** (Poisson bivariado) convierte la diferencia de Elo en goles esperados y en una matriz de marcadores → 1X2, marcador más probable (`ml/models/dixon_coles.py`).
3. **Monte Carlo** simula el torneo 10.000 veces sobre el **bracket oficial** (R32 partidos 73-88 → Final), asignando los 8 mejores terceros a sus huecos por emparejamiento bipartito que respeta los conjuntos de grupos elegibles del **Anexo C de FIFA** (sin revanchas; las 495 combinaciones validadas). Condiciona por los partidos ya jugados → probabilidad de avance y título (`ml/simulation/monte_carlo.py`).

## Modelos ML/DL/bayesiano y selección en la UI

Todos los modelos predicen **goles esperados (λ)** y comparten la máquina Dixon-Coles para
derivar 1X2, así se comparan de forma justa y **alimentan el mismo Monte Carlo** vía
`goal_model` (matriz λ de los 48 equipos, `ml/models/grid.py`):

- **Elo + Dixon-Coles** (baseline).
- **XGBoost** (`ml/models/xgboost_model.py`): dos regresores Poisson de goles sobre features pre-partido.
- **Red neuronal** (`ml/models/neural_net.py`, PyTorch): embeddings de equipos + MLP Poisson; *device-aware* (DirectML/CUDA/CPU).
- **Bayesiano** (`ml/models/bayesian.py`, PyMC/ADVI): jerárquico att/def por equipo con intervalos de credibilidad.

Features pre-partido sin fuga de datos (`ml/features/build_features.py`): Elo variable en el tiempo, forma reciente, sede neutral e importancia. Evaluación con `ml/evaluate.py` (RPS, log-loss, Brier, accuracy) y split temporal.

**Selección de modelo:** el header de la UI tiene un selector (Elo/XGBoost/NN/Bayesiano); Dashboard, Grupos y Camino al título consultan `/api/simulations/latest?model=…`. Se entrena y simula por modelo; cada `SimulationRun` lleva su `model_name`. Registrar un resultado o sincronizar recalcula **todos** los modelos (`recalc_all`).

**Comparador lado a lado:** la página *Comparador* (permiso `view_models`) muestra los 4 modelos juntos —gráfico de barras agrupado + tabla con métrica seleccionable (campeón/finalista/clasifica)— vía `GET /api/simulations/compare` (última simulación de cada modelo).

**Intervalos de credibilidad (bayesiano):** al final del *Comparador*, un *forest plot* muestra la fuerza (ataque+defensa) de cada equipo con su intervalo creíble 95%, vía `GET /api/simulations/bayesian-strength` (medias y desviaciones posteriores de ADVI; `CredibleIntervals.tsx`).

**Eliminatorias materializadas:** al cerrar la fase de grupos, `materialize_knockouts` (`backend/app/services/knockouts.py`) deriva la Ronda de 32 del **bracket oficial** (`ml/simulation/bracket.py`, reusando la estructura del Monte Carlo) y la crea como partidos concretos; las rondas siguientes se materializan al completarse la previa. Los empates en eliminatorias requieren el ganador por penaltis (`winner_team_id`). El tracker (UI) tiene pestañas Grupos/Eliminatorias.

```powershell
python -m ml.train --models      # entrena XGBoost + NN y simula cada uno
python -m ml.train --bayes       # añade el bayesiano (PyMC, ~1-2 min)
python -m ml.backtest            # compara los 4 modelos (corte 2022-06-01)
```
Backtest (test ~4.2k, competitivos): **XGBoost 0.169** < Elo 0.171 < NN 0.171 < Bayesiano 0.189 (RPS, menor = mejor). XGBoost lidera; el bayesiano rinde peor en precisión pero aporta incertidumbre/interpretabilidad.

## Sincronización en vivo (opcional)

El scheduler (`backend/app/scheduler.py`, APScheduler) sondea la fuente activa cada `LIVE_SYNC_INTERVAL_MINUTES`, aplica los resultados **finalizados** de la fase de grupos (casando nombres por plegado/alias, en cualquier orientación), **materializa eliminatorias** y recalcula si hubo cambios. También se dispara a mano (botón "Sincronizar" o `POST /api/matches/sync`, permiso `record_result`). Servicio: `backend/app/services/livesync.py`.

**Fuentes (selección automática en `active_provider()`):**
- **football-data.org** (RECOMENDADA, gratis): su tier libre **cubre el Mundial 2026**. Token gratis en football-data.org → `FOOTBALL_DATA_ORG_TOKEN`. Tiene prioridad.
- **API-Football** (api-sports.io): integrada y validada, pero su plan **Free NO cubre la temporada 2026** (solo 2022–2024); requiere plan de pago. `API_FOOTBALL_KEY`.

Sin ninguna fuente, el tracking manual sigue funcionando y el endpoint responde 400 con un mensaje claro. Verificadores: `scripts/check_footballdata.py` y `scripts/check_apifootball.py`.

## Control de acceso (RBAC)

- Perfiles configurables con permisos granulares y **cupo máximo de usuarios por perfil** (HTTP 409 al superar).
- Permisos: `view_dashboard`, `view_models`, `run_simulation`, `record_result`, `manage_users`, `manage_profiles`.
- Perfiles semilla: `admin` (todos, protegido), `analyst`, `viewer`. El sistema nunca se queda sin administradores.

## Puesta en marcha — desarrollo (Servidor A)

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
copy .env.example .env            # edita SECRET_KEY y ADMIN_PASSWORD
python -m ml.train                # histórico -> Elo -> predicciones -> simulación
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
# Docs: http://localhost:8000/docs
```

## Despliegue distribuido (Docker)

**Servidor A (este equipo):**
```bash
docker compose -f deploy/docker-compose.backend.yml up -d --build
docker compose -f deploy/docker-compose.backend.yml exec backend python -m ml.train
```

**Servidor B (otro Linux):** edita `.env` con `SERVIDOR_A_IP=<IP LAN del Servidor A>`, luego:
```bash
docker compose -f deploy/docker-compose.frontend.yml up -d --build
```

**Certificado en la LAN:** Caddy usa su CA interna (`tls internal`). Exporta su raíz e instálala en los dispositivos cliente para que el HTTPS sea de confianza:
```bash
docker compose -f deploy/docker-compose.frontend.yml exec frontend \
  cat /data/caddy/pki/authorities/local/root.crt > caddy-root.crt
# Instala caddy-root.crt como CA de confianza en cada dispositivo.
```

**Firewall:** el Servidor A debería aceptar el puerto 8000 únicamente desde la IP del Servidor B; el Servidor B expone solo el 443.

## Verificación

```powershell
# Núcleo ML (sin BD): Elo, Dixon-Coles, Monte Carlo (bracket oficial)
python -m ml.verify_core
# Sync en vivo (sin red): parseo, mapeo de nombres/alias, manejo sin API key
python scripts/smoke_livesync.py
# API end-to-end (con el servidor corriendo): auth, RBAC, cupos, tracking, recálculo, sync
python scripts/smoke_api.py
# Frontend + proxy (con backend :8000 y `npm run dev`): SPA, login, simulación
python scripts/smoke_frontend.py
```
