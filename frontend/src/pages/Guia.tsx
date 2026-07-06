import { useState } from "react";

interface Section {
  icon: string;
  title: string;
  body: React.ReactNode;
}

function Card({ icon, title, body }: Section) {
  const [open, setOpen] = useState(false);
  return (
    <div className="card overflow-hidden">
      <button
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-panel2/60 transition"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-3">
          <span className="text-xl">{icon}</span>
          <span className="font-semibold text-sm">{title}</span>
        </div>
        <span className="text-slate-500 text-sm">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="border-t border-line/50 px-4 py-3 text-sm text-slate-300 leading-relaxed space-y-2">
          {body}
        </div>
      )}
    </div>
  );
}

const SECTIONS: Section[] = [
  {
    icon: "📊",
    title: "Dashboard — Probabilidades de título",
    body: (
      <>
        <p>
          Muestra la probabilidad de cada equipo de ganar el Mundial, llegar a la Final, las Semis,
          Cuartos, Octavos y la Ronda de 32. Se calcula con <b>10 000 simulaciones Monte Carlo</b>{" "}
          del torneo completo.
        </p>
        <p className="text-slate-400">
          Las barras de credibilidad (en el modelo Bayesiano) muestran el rango de incertidumbre:
          un equipo con barra ancha tiene probabilidades menos definidas que uno con barra estrecha.
        </p>
      </>
    ),
  },
  {
    icon: "🏟️",
    title: "Grupos — Fase de grupos simulada",
    body: (
      <>
        <p>
          12 grupos de 4 equipos. Para cada grupo se muestran las probabilidades de terminar 1°, 2°,
          clasificar como <b>mejor tercero</b> (solo los 8 mejores de los 12 terceros avanzan) o
          eliminarse.
        </p>
        <p className="text-slate-400">
          Verde = clasifica directo · Ámbar = posible mejor 3° · Gris = eliminado.
        </p>
      </>
    ),
  },
  {
    icon: "🏆",
    title: "Bracket — Calendario y camino al título",
    body: (
      <>
        <p>
          Dos vistas: el <b>calendario</b> con todos los partidos ordenados por fecha y hora real
          (incluye predicciones 1X2 para los no jugados), y la <b>tabla de probabilidades</b> por
          ronda para los 48 equipos, ordenada por probabilidad de ser campeón.
        </p>
      </>
    ),
  },
  {
    icon: "⚽",
    title: "Partidos — Seguimiento de resultados",
    body: (
      <>
        <p>
          Lista los 104 partidos con la predicción del modelo (1X2 + marcador esperado). El admin
          puede registrar resultados; el sistema recalcula automáticamente las probabilidades de todo
          el torneo. También hay un botón de sincronización con la API de football-data.org.
        </p>
      </>
    ),
  },
  {
    icon: "🎯",
    title: "Apuestas — Constructor de apuestas",
    body: (
      <>
        <p>
          Selecciona un partido y explora más de 80 mercados estadísticos calculados con el{" "}
          <b>modelo Poisson</b>: resultado 1X2, goles, córners, tarjetas, disparos, tiros a puerta
          por equipo y por jugador.
        </p>
        <p>
          Las cuotas mostradas son <b>probabilidades matemáticas reales</b> sin margen de casa.
          El combinador multiplica probabilidades independientes para dar la cuota equivalente.
          Si combinas eventos no independientes (ej. más de 2 y más de 3 córners), el sistema
          te avisa con una advertencia.
        </p>
        <p className="text-slate-400">
          Los tiros a puerta por jugador usan datos de StatsBomb (WC 2018/2022) y FBref
          (Euro 2024, Copa América 2024). Solo aparecen equipos con cobertura histórica.
        </p>
      </>
    ),
  },
  {
    icon: "⚖️",
    title: "Comparar — Rendimiento de modelos",
    body: (
      <>
        <p>
          Compara los distintos modelos disponibles (Elo + Dixon-Coles, XGBoost, Bayesiano) usando
          métricas de calibración sobre los partidos ya jugados. Útil para entender cuál modelo
          predice mejor.
        </p>
      </>
    ),
  },
  {
    icon: "📈",
    title: "Rendimiento — Precisión del modelo en vivo",
    body: (
      <>
        <p>
          Muestra partido a partido si el modelo acertó el resultado (1X2), la probabilidad que
          asignó al resultado correcto y el Brier score. El <b>Brier score</b> mide la calidad
          probabilística: 0 = perfecto, 0.33 = sin información, por encima de 0.33 = peor que
          el azar.
        </p>
      </>
    ),
  },
  {
    icon: "🤖",
    title: "Los modelos explicados",
    body: (
      <>
        <p>
          <b>Elo propio:</b> calcula la fuerza relativa de cada selección desde ~50 000 partidos
          históricos (1872–2026). Se ajusta por importancia del torneo, margen de goles y sede.
        </p>
        <p>
          <b>Dixon-Coles:</b> modelo Poisson bivariado que predice λ_local y λ_visitante (goles
          esperados por equipo). Incluye una corrección para el sub-conteo estadístico de empates
          0-0 y 1-1. Produce la probabilidad exacta de cada marcador posible.
        </p>
        <p>
          <b>Monte Carlo:</b> simula 10 000 torneos completos vectorizados en NumPy: resuelve los
          72 partidos de grupos con la regla de los 8 mejores terceros, aplica desempates FIFA y
          genera el bracket de eliminatorias con prórroga y penaltis.
        </p>
        <p>
          <b>XGBoost / Bayesiano:</b> modelos alternativos comparables en la pestaña Comparar.
        </p>
      </>
    ),
  },
  {
    icon: "🗄️",
    title: "Fuentes de datos",
    body: (
      <>
        <p>
          <b>Partidos históricos:</b> dataset Kaggle martj42 (~50 000 partidos desde 1872).
          Base de entrenamiento de todos los modelos.
        </p>
        <p>
          <b>Resultados en vivo:</b> football-data.org (sync automático cada 15 min durante
          partidos) + ingreso manual por el admin como respaldo.
        </p>
        <p>
          <b>Jugadores:</b> StatsBomb Open Data (WC 2018/2022) y FBref vía soccerdata
          (Euro 2024, Copa América 2024). Se combinan con peso 60% forma reciente / 40% historial WC.
        </p>
        <p className="text-slate-500 text-xs mt-2">
          Aplicación independiente · no afiliada a la FIFA, CONMEBOL, UEFA ni organizaciones
          deportivas · solo uso educativo y de referencia.
        </p>
      </>
    ),
  },
];

export default function Guia() {
  return (
    <div className="space-y-4 max-w-2xl">
      <div>
        <h1 className="text-2xl font-bold">Guía rápida</h1>
        <p className="text-sm text-slate-400">Toca cada sección para ver la explicación.</p>
      </div>
      <div className="space-y-2">
        {SECTIONS.map((s) => (
          <Card key={s.title} {...s} />
        ))}
      </div>
    </div>
  );
}
