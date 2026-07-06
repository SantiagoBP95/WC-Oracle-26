# Actualización técnica — Predictor WC2026
**Fecha:** 13-14 junio 2026 | **Sesión:** ingestión de jugadores y squads oficiales

---

## Resumen ejecutivo

Se completó el pipeline de ingesta de estadísticas de jugadores, corrigiendo cuatro bugs críticos en la fuente StatsBomb y el módulo de merge, y se integró la sincronización de convocatorias oficiales del Mundial 2026 desde football-data.org. El resultado: **BetBuilder mostrando solo jugadores convocados con valores de SOT/90 correctos**.

---

## 1. Bugs corregidos en `backend/app/ingest/player_stats.py`

### 1.1 Outcomes de tiro incorrectos
**Síntoma:** todos los tiros contaban 0 SOT (shots on target).  
**Causa:** `_SOT_OUTCOMES = {"Saved Shot", "Saved Off Target"}` — cadenas que StatsBomb no usa.  
**Fix:** `_SOT_OUTCOMES = {"Goal", "Saved"}` (valores reales de la API de StatsBomb).

### 1.2 `pos_entry` no-dict en lista de posiciones
**Síntoma:** algunos partidos perdían los minutos de todos sus jugadores → SOT/90 inflado (ej. Mbappé 6.5, Salah 68).  
**Causa:** `player_row.get("positions")` puede devolver una lista con elementos `None`. `None.get("from")` → `AttributeError` capturado por el `except` del bloque de lineup, borrando los minutos del partido entero.  
**Fix:** añadir `if not isinstance(pos_entry, dict): continue` dentro del bucle de posiciones.

### 1.3 `positions` devolviendo `None` en pandas
**Síntoma:** mismo efecto que 1.2 para filas con campo `positions` nulo en el DataFrame.  
**Causa:** `player_row.get("positions", [])` en pandas devuelve `None` (no el default `[]`) cuando el valor es null. `for pe in None` → `TypeError`.  
**Fix:** `positions = player_row.get("positions") or []`.

### 1.4 Nationalidad `nan` en el merge StatsBomb ↔ FBref
**Síntoma:** jugadores como Salah (solo fuente StatsBomb) tenían `nationality="nan"` tras el merge → no encontraban equipo en `team_map` → eran descartados (`skipped`) → su valor erróneo previo persistía en DB.  
**Causa:** `r.get("nationality_fb") or r.get("nationality_sb")` — en Python `float('nan')` es *truthy*, por lo que `nan or fallback` devuelve `nan` en lugar del fallback.  
**Fix:** helper `_s(v)` que convierte `None`/`NaN` a `""` antes del `or`.

### 1.5 Filtro `sot_per_90 > 0` excluía actualizaciones a 0
**Síntoma:** jugadores como Osorio y Buchanan (Canadá) con SOT=0 en el cálculo correcto no eran actualizados → persistía su valor incorrecto previo (31.765).  
**Causa:** el filtro `merged = merged[(merged["minutes"] >= 45) & (merged["sot_per_90"] > 0)]` excluía a jugadores con SOT legítimamente 0.  
**Fix:** eliminar la condición `sot_per_90 > 0`; solo se mantiene `minutes >= 45`.

---

## 2. Sincronización de convocatorias oficiales

### Nuevo script: `scripts/sync_squads.py`
Consulta `GET /v4/competitions/WC/teams` en football-data.org (token existente en `.env`) y actualiza el campo `in_squad` de cada jugador en la tabla `players`:

- **Matching de nombres:** normalización NFKD (sin diacríticos, minúsculas) + coincidencia exacta + prefijo (para capturar nombres largos de StatsBomb: "Kylian Mbappé Lottin" → casa con "Kylian Mbappé").
- **Resultado:** 433 jugadores marcados `in_squad=True`, 1164 `in_squad=False`.
- **Casos correctos verificados:**
  - Benzema, Kimpembe, Vertonghen, Neymar (da Silva Santos Junior) → `False`
  - Salah, Mbappé, Messi, Kane, Yamal, Vinicius, Bruno Fernandes → `True`

### Nuevo endpoint: `POST /api/admin/sync/squads`
Permiso requerido: `manage_users`. Vuelve a ejecutar el sync de convocados desde la API. Útil al inicio de cada jornada o cuando FIFA actualiza bajas/altas por lesión.

### Filtro en BetBuilder (`backend/app/api/bets.py`)
Añadida condición `Player.in_squad.is_(True)` al query de jugadores por equipo. Solo aparecen jugadores convocados con SOT/90 > 0 e `in_squad=True`.

---

## 3. Estado de cobertura tras la actualización

| Métrica | Valor |
|---------|-------|
| Jugadores totales en DB | 1.597 |
| Jugadores convocados WC2026 (`in_squad=True`) | 433 |
| Convocados con SOT/90 > 0 | **232** |
| Equipos con al menos un jugador activo | **36/48** |
| Equipos sin datos (0 jugadores activos) | 12 |

**Equipos sin cobertura (12):** Bosnia y Herzegovina, Haiti, Paraguay, Curazao, Iran, Nueva Zelanda, Cabo Verde, Noruega, Irak, Jordania, Uzbekistan, RD Congo.

**Causa:** ninguno de estos países aparece en los torneos ingestados (WC2018, Euro2020, WC2022, AFCON2023, Euro2024). La principal fuente que los cubriría es Copa América 2024 (StatsBomb), actualmente desactivada por un hang en una descarga de partido.

---

## 4. Fuentes de datos por torneo

| Torneo | ID StatsBomb | Peso recencia | Estado |
|--------|-------------|--------------|--------|
| WC2018 | (43, 3) | 0.30 | ✅ activo |
| Euro 2020 | (55, 43) | 0.50 | ✅ activo |
| WC2022 | (43, 106) | 0.70 | ✅ activo |
| AFCON 2023 | (1267, 107) | 0.90 | ✅ activo |
| Euro 2024 | (55, 282) | 1.00 | ✅ activo |
| Copa América 2024 | (223, 282) | 1.00 | ⚠️ desactivado (hang HTTP en un partido) |

FBref (soccerdata): WC2022 + Euro2024 — columnas MultiIndex aplanadas, league names correctos (`INT-World Cup`, `INT-European Championship`).

---

## 5. Próximos pasos opcionales

1. **Cobertura de los 12 equipos sin datos:** clonar localmente el repo `statsbombpy/open-data` e ingesta offline de Copa América 2024 (evita el hang HTTP).
2. **Stats de club 2024-25 (Big 5):** añadir FBref Big 5 (Premier League, La Liga, Bundesliga, Serie A, Ligue 1) como fuente adicional — mayor muestra de minutos para atacantes activos en Europa.
3. **Re-sync de squads por lesión:** el endpoint `/admin/sync/squads` puede ejecutarse manualmente o programarse en el scheduler si hay `FOOTBALL_DATA_ORG_TOKEN`.
4. **Despliegue Servidor B:** pendiente de acceso físico al equipo. Ver `deploy/PROMPT-SERVIDOR-B.md`.
