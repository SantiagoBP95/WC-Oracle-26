# Novedades en el Predictor WC2026 — Bet Builder
**Para:** usuarios de la aplicación  
**Fecha:** 14 junio 2026

---

## ¿Qué ha cambiado hoy?

### BetBuilder muestra solo jugadores convocados al Mundial

Anteriormente podían aparecer en el BetBuilder jugadores que **ya no están en la selección** (retirados, lesionados o no convocados) como Benzema, Kimpembe, Neymar "histórico" o Vertonghen. Esto podía llevar a apuestas sobre jugadores que no van a disputar el torneo.

**A partir de hoy** el BetBuilder solo muestra a los **26 jugadores oficialmente inscritos por cada selección** ante la FIFA, según las listas cerradas el 1 de junio de 2026.

---

## ¿Cómo funciona el BetBuilder?

El BetBuilder te da probabilidades de que un jugador meta **1 o más tiros a puerta** en un partido. Para cada equipo elige a los **3 delanteros o medios con más disparos a puerta por 90 minutos** (SOT/90) entre los convocados con datos históricos.

Esas probabilidades se calculan con un modelo de Poisson ajustado a la intensidad del partido (cuántos goles espera el modelo para ese partido).

---

## Valores SOT/90 corregidos

Los valores de tiros a puerta también se han recalculado correctamente. Antes, un bug en el procesamiento de tiempos de juego inflaba artificialmente el SOT/90 de algunos jugadores.

Ejemplos de valores ahora correctos:

| Jugador | SOT/90 antes (erróneo) | SOT/90 ahora (correcto) |
|---------|------------------------|-------------------------|
| Mohamed Salah | 68.0 | **0.66** |
| Kylian Mbappé | 6.5 | **1.93** |
| Bruno Fernandes | 51.2 | **1.08** |
| Osorio / Buchanan | 31.8 | **0.00** *(no han marcado SOT en torneos cubiertos)* |

---

## ¿Qué equipos tienen datos de jugadores?

De los 48 equipos del Mundial, **36 tienen al menos un jugador con datos** en el BetBuilder. Los 12 que aún no tienen jugadores disponibles son selecciones de Asia, Oceanía y algunas de CONCACAF/CONMEBOL que no participaron en los torneos analizados (Eurocopas, Mundiales 2018/2022, AFCON 2023).

Para esos partidos el BetBuilder mostrará solo las apuestas de resultado (1X2, marcador) sin la sección de tiros a puerta.

---

## ¿Qué pasa si un jugador sufre una lesión y es baja del torneo?

Desde el panel de **Administración → Sync Squads** el admin puede actualizar las listas en cualquier momento para reflejar cambios oficiales (bajas y reemplazos que FIFA autorice durante el torneo).

---

## Cobertura actual

| Sección | Estado |
|---------|--------|
| Probabilidades 1X2 | ✅ Todos los partidos |
| Marcador esperado | ✅ Todos los partidos |
| Avance por fase / título | ✅ 48 equipos |
| Bet Builder (tiros a puerta) | ✅ 36/48 equipos |
| Registro de resultados en vivo | ✅ Disponible para admin |
| Recálculo automático de probabilidades | ✅ Tras cada resultado |
