# WC Oracle 2026 — Documentación General

> **Aviso legal:** Aplicación independiente de análisis estadístico. No afiliada ni patrocinada por la FIFA, CONMEBOL, UEFA ni ninguna organización deportiva. Solo uso educativo y de referencia.

---

## 1. Qué es WC Oracle 2026

WC Oracle 2026 es una plataforma web de predicción estadística y seguimiento en tiempo real del FIFA World Cup 2026 (48 equipos, 104 partidos, 11 jun – 19 jul 2026). Combina modelos estadísticos clásicos, aprendizaje automático (ML) y simulación de Monte Carlo para generar probabilidades de resultado en cada partido y en el torneo completo.

La aplicación está diseñada para uso privado en red local (LAN) con control de acceso multiusuario (RBAC), sin dependencia de servidores en la nube.

---

## 2. Funcionalidades principales

| Módulo | Descripción |
|--------|-------------|
| **Dashboard** | Probabilidades de título y avance por equipo; tabla ordenable por ronda; barras de credibilidad bayesiana |
| **Grupos** | Simulación de la fase de grupos: prob. de 1°, 2°, mejor tercero, eliminación |
| **Bracket** | Bracket interactivo de eliminatorias con probabilidades por ronda actualizadas tras cada resultado |
| **Partidos** | Los 104 partidos con predicción 1X2 + marcador esperado vs resultado real; registro de scores por el admin; sincronización automática con football-data.org |
| **Bet Builder** | Asistente estadístico de apuestas: mercados Poisson por partido (goles, córners, tarjetas, disparos, tiros a puerta totales y por jugador); combinador de probabilidades independientes con cuota equivalente |
| **Comparador** | Comparación de modelos (Elo + Dixon-Coles vs XGBoost vs Bayesiano) con métricas de calibración RPS, Brier, log-loss |
| **Admin (RBAC)** | Gestión de usuarios, perfiles, permisos granulares y cupos; log de auditoría; ingesta de datos de jugadores |

---

## 3. Arquitectura del sistema

```
[Dispositivos cliente]  ──HTTPS──►  [Servidor B — Linux + Docker]
                                      Caddy (solo reverse proxy TLS)
                                        └── /* ──HTTP/LAN──► [Servidor A — este equipo :8000]
                                                              FastAPI + Uvicorn
                                                                ├── /api/*   API REST
                                                                ├── /assets  React SPA (dist estático)
                                                                ├── /*       SPA fallback → index.html
                                                                ├── Auth JWT + RBAC
                                                                ├── SQLite (app.db)
                                                                ├── Modelos ML (.joblib / .pt)
                                                                └── APScheduler (sync + recálculo)
```

- **Servidor A** (Windows, puerto 8000): sirve **todo** — frontend estático (`frontend/dist`) + API REST + modelos + DB. El backend monta `frontend/dist` y hace fallback a `index.html` para el routing de la SPA.
- **Servidor B** (Linux con Docker): **solo HTTPS/TLS**. Caddy recibe en 443 y reenvía todo a `http://192.168.1.50:8000`. No necesita el repo ni hacer build.
- Para actualizar el frontend basta con hacer `npm run build` en Server A — los nuevos archivos en `frontend/dist` quedan disponibles de inmediato sin tocar Server B.

---

## 4. Stack tecnológico

### Backend
| Capa | Tecnología |
|------|-----------|
| API | **FastAPI** + Uvicorn |
| ORM / DB | **SQLAlchemy 2** + **SQLite** |
| Auth | **JWT** (PyJWT) + **bcrypt** + OAuth2 password flow |
| RBAC | Modelo propio `User / Profile / Permission` con cupos por perfil |
| Rate limiting | **slowapi** |
| Scheduler | **APScheduler** (sync en vivo + recálculo automático tras cada resultado) |
| Stats/ML | **scipy**, **numpy**, **pandas**, **scikit-learn**, **XGBoost**, **PyMC** |
| Datos jugadores | **statsbombpy** (WC 2018/2022), **soccerdata / FBref** (torneos recientes) |

### Frontend
| Capa | Tecnología |
|------|-----------|
| Framework | **React 18 + TypeScript + Vite** |
| Estilos | **Tailwind CSS** |
| Datos | **TanStack Query** + **axios** |
| Gráficos | **Recharts** |

---

## 5. Fuentes de datos

### 5.1 Datos históricos de partidos
| Fuente | Contenido | Uso |
|--------|-----------|-----|
| **Kaggle `martj42/international_results`** | ~50 000 partidos internacionales desde 1872: fecha, equipos, marcador, torneo, sede, neutralidad | Base de entrenamiento de todos los modelos. Calcula el Elo propio, λ ataque/defensa, forma, head-to-head |
| **football-data.org (gratis)** | Fixtures y resultados del WC 2026 en tiempo real | Sincronización automática de marcadores durante el torneo |
| **API-Football (free tier, 100 req/día)** | Fixtures, eventos, lineups | Respaldo y datos de eventos; protegido con caché en SQLite |

### 5.2 Datos de jugadores
| Fuente | Contenido | Uso |
|--------|-----------|-----|
| **StatsBomb Open Data** | Eventos completos de WC 2018 y WC 2022: cada disparo, pase, gol por jugador | Calcula **SOT/90** (tiros a puerta por 90 min) histórico en el Mundial para cada jugador |
| **FBref vía soccerdata** | Estadísticas de shooting de Euro 2024, Copa América 2024 | Proxy de **forma reciente** (peso 60%) combinado con el histórico WC (peso 40%) |

### 5.3 Datos del torneo
| Fuente | Contenido |
|--------|-----------|
| `data/seed/wc2026.json` | Grupos A–L confirmados, 48 equipos, 104 fixtures, sedes — versionado en el repo para funcionar offline desde el día 1 |

**Política de cuotas:** con solo 100 req/día de API-Football, el scheduler hace polling solo en ventanas de partido; el resto del tiempo el sistema lee de la caché SQLite. Como respaldo completo existe ingreso manual de marcadores por el admin.

---

## 6. Modelos estadísticos y de ML

### 6.1 Elo propio
Calculado desde el dataset Kaggle (sin depender de eloratings.net). Cada partido actualiza los ratings con un factor K ajustado por:
- Importancia del torneo (Mundial > amistoso)
- Margen de victoria (gol diferencia)
- Ventaja de localía / sede neutral

### 6.2 Dixon-Coles (modelo principal)
Poisson bivariado con corrección Dixon-Coles para el sub-conteo estadístico de resultados 0-0 y 1-1. Para cada partido produce:
- **λ_home** y **λ_away** (goles esperados)
- Matriz completa de probabilidades de marcador exacto (hasta 7-7)
- **1X2**, over/under goles, BTTS (ambos marcan)

### 6.3 Monte Carlo (simulación del torneo)
10 000 simulaciones completas del torneo vectorizadas en NumPy:
- Resuelve los 72 partidos de grupos con la regla de los 8 mejores terceros de la FIFA
- Aplica criterios de desempate FIFA (puntos → diferencia de goles → goles a favor → sorteo)
- Genera el bracket de eliminatorias con prórroga y penaltis modelados
- Salida: probabilidad de título, final, semifinal, cuartos, octavos y Ronda de 32 por equipo

Se recalcula automáticamente tras cada resultado registrado.

### 6.4 XGBoost 1X2 (Fase 2)
Clasificador sobre las features del partido (Elo, forma, head-to-head, distancia de viaje, días de descanso, importancia). Calibrado con isotónica/Platt para que las probabilidades sean válidas. Backtesting sobre WC 2010–2022.

### 6.5 Bayesiano (PyMC — Fase 3)
Modelo jerárquico de fuerza de ataque y defensa por equipo con **intervalos de credibilidad**. Permite cuantificar incertidumbre: "Argentina tiene un 38% de prob. de título con rango [29%–47%]".

### 6.6 Ensemble
Promedio ponderado de los modelos disponibles, seleccionado por RPS (Ranked Probability Score) en backtesting.

### 6.7 Bet Builder — modelo Poisson por mercado
Para cada partido del Bet Builder, los mercados se calculan en tiempo real usando las lambdas de Dixon-Coles más medias históricas del WC:

| Mercado | Modelo |
|---------|--------|
| Goles Over/Under, BTTS | Poisson(λ_home + λ_away) |
| Resultado 1X2 | Directo de Dixon-Coles |
| Córners | Poisson(9.8 × escala_goles × factor_Elo) |
| Tarjetas | Poisson(3.6 × (1 + 0.18 × diff_Elo/400)) |
| Disparos totales | Poisson(23.5 × escala_goles) |
| Tiros a puerta (total y por equipo) | Poisson(λ_goles / 0.30) — tasa conversión WC histórica |
| Tiros a puerta por jugador | Poisson(sot_per_90_jugador × escala_intensidad) |

Las probabilidades de eventos independientes se multiplican directamente para la cuota combinada: **P(A ∩ B) = P(A) × P(B)**.

---

## 7. Base de datos (SQLite)

Todas las tablas en un único archivo `data/app.db`. Migración idempotente sin Alembic (compatible con BD existentes).

```
teams               — 48 selecciones: Elo, ataque/defensa, grupo, confederación
matches             — 104 partidos: stage, equipos, fecha, sede, status, scores
predictions         — Predicción 1X2 + lambdas + mejor marcador por partido y modelo
simulation_runs     — Historial de simulaciones Monte Carlo
team_advance_probs  — Probabilidades por ronda para cada equipo y simulación
rating_snapshots    — Serie temporal de Elo (habilita gráfica de evolución)
players             — Jugadores con sot_per_90 / shots_per_90 (StatsBomb + FBref)

users               — Credenciales bcrypt + perfil + estado
profiles            — Nombre, descripción, max_users (cupo)
permissions         — Catálogo de capacidades granulares
profile_permissions — Relación M:N perfil↔permiso
user_sessions       — Control de sesión única por usuario (jti → evicción)
audit_log           — Quién hizo qué y cuándo
```

---

## 8. Control de acceso (RBAC)

| Perfil | Permisos clave |
|--------|----------------|
| **admin** | Todo: gestionar usuarios, registrar resultados, correr simulaciones |
| **analyst** | Ver todo + correr simulaciones + ver modelos; sin gestión de usuarios |
| **viewer** | Ver dashboard, grupos, bracket, partidos, comparador, Bet Builder; sin escribir |

Reglas de seguridad:
- Cada usuario pertenece a un perfil; los permisos efectivos son los del perfil.
- **Sesión única** por usuario (jti en DB); un segundo login expulsa la sesión anterior.
- **Cupo por perfil**: el sistema rechaza con HTTP 409 si se supera `Profile.max_users`.
- Tokens JWT: access (30 min) + refresh (7 días); rotación en cada refresh.
- Contraseñas bcrypt; bloqueo de cuenta desactivable por admin.

---

## 9. Factor diferencial vs 365 / RushBet / Betway

Las casas de apuestas tradicionales calculan sus cuotas con modelos propietarios opacos y aplican un **margen de sobreprecio** (overround) del 5–10% sobre las probabilidades reales para garantizar su ganancia independientemente del resultado. WC Oracle opera de forma fundamentalmente distinta:

### 9.1 Transparencia del modelo
| Aspecto | Casas de apuestas | WC Oracle |
|---------|-------------------|-----------|
| Metodología | Opaca / propietaria | Abierta: Elo + Dixon-Coles + Monte Carlo documentado |
| Overround | 5–10% siempre a favor del operador | Sin margen: la cuota es `1 / probabilidad_real` |
| Calibración | Desconocida (solo buscan márgenes) | Medida con RPS, Brier, calibración en WC pasados |
| Actualización | Tiempo real con movimiento de dinero | Tras cada resultado registrado (recalculate) |

### 9.2 Predicciones de largo alcance
Las casas solo publican cuotas a corto plazo (próximo partido). WC Oracle genera probabilidades de **título, final, semifinal, cuartos y octavos** para los 48 equipos desde el día 1, actualizadas tras cada partido — algo que solo ofrecen plataformas de análisis como FiveThirtyEight (desactivada) o Opta.

### 9.3 Bet Builder estadístico
RushBet y Betway ofrecen Bet Builder, pero sus probabilidades derivan del movimiento de apuestas y márgenes comerciales. WC Oracle calcula cada mercado desde el modelo Poisson con los parámetros exactos del partido:
- Las cuotas que muestra son **probabilidades matemáticas reales**, no precios de mercado.
- El combinador usa multiplicación directa de independientes, sin margen oculto.
- El usuario ve qué tan probable es realmente cada evento, no cuánto le paga la casa.

### 9.4 Tiros a puerta por jugador
Ninguna casa latinoamericana (365, RushBet, Betplay) ofrece mercados de SOT por jugador en partidos de selecciones del Mundial en tiempo real. WC Oracle los genera automáticamente desde datos de StatsBomb Open Data y FBref para los top-3 delanteros de cada equipo.

### 9.5 Privacidad y control
La aplicación corre 100% en servidores privados de la LAN. No recopila datos de usuarios en servidores externos, no comparte información con terceros, no requiere cuenta en plataformas de apuestas.

### 9.6 Evolución temporal
WC Oracle guarda el historial completo de simulaciones, permitiendo ver **cómo cambiaron las probabilidades** de cada equipo a lo largo del torneo — una vista que ninguna casa de apuestas expone públicamente.

---

## 10. Limitaciones y disclaimers

1. **Datos de jugadores incompletos:** los mercados de tiros a puerta por jugador dependen de StatsBomb Open Data (WC 2018/2022) y FBref (Euro 2024, Copa América 2024). Equipos con poca participación histórica en estos torneos o debutantes en el Mundial 2026 pueden no tener datos individuales disponibles. En esos casos la categoría de jugadores no aparece en el Bet Builder.

2. **No es consejo de apuestas:** las probabilidades son estimaciones matemáticas basadas en datos históricos. El fútbol tiene alta varianza — eventos como expulsiones, lesiones o condiciones climáticas no están modelados. Ningún modelo predice el fútbol con certeza.

3. **No afiliación:** aplicación independiente de análisis estadístico. No afiliada, patrocinada ni aprobada por la FIFA, CONMEBOL, UEFA ni ninguna otra organización deportiva o de apuestas.

4. **Margen de conversión SOT → goles:** la tasa histórica WC es ~30%. Esta tasa varía según el equipo y el rival; es un promedio, no un dato exacto por partido.

5. **Cuota de API gratuita:** la sincronización automática de resultados (football-data.org) está sujeta a disponibilidad del servicio. Como respaldo, el admin puede registrar marcadores manualmente.

---

## 11. Cómo actualizar los datos de jugadores

La ingesta de jugadores (StatsBomb + FBref) se puede relanzar desde el panel de administración o via API:

```bash
# Vía curl (reemplazar TOKEN con un token admin válido)
curl -X POST http://localhost:8000/api/admin/ingest/players \
  -H "Authorization: Bearer TOKEN"
```

O desde el panel Admin → botón "Reingestar jugadores" (próxima versión).

La ingesta tarda ~3–8 minutos la primera vez (descarga ~130 archivos de eventos StatsBomb). Las siguientes ejecuciones son más rápidas gracias al caché local de soccerdata.

---

*Generado el 11 de junio de 2026 · WC Oracle 2026 v0.1*
