import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import type { BayesStrength } from "../api/types";

/**
 * Forest plot de la fuerza por equipo (ataque + defensa) con su intervalo de
 * credibilidad 95% según el modelo bayesiano. Si el bayesiano no está entrenado,
 * no renderiza nada.
 */
export default function CredibleIntervals() {
  const { data, isError } = useQuery({
    queryKey: ["bayes-strength"],
    queryFn: async () => (await api.get<BayesStrength[]>("/simulations/bayesian-strength")).data,
    retry: false,
  });

  if (isError || !data || data.length === 0) return null;

  const lo = Math.min(...data.map((d) => d.overall_lo));
  const hi = Math.max(...data.map((d) => d.overall_hi));
  const span = hi - lo || 1;
  const x = (v: number) => ((v - lo) / span) * 100;

  return (
    <div className="card overflow-hidden">
      <div className="border-b border-line bg-panel2/50 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-300">
          Fuerza por equipo — intervalo de credibilidad 95% (Bayesiano)
        </h2>
        <p className="text-xs text-slate-500">
          Punto = media posterior · barra = rango creíble. Fuerza = ataque + defensa.
          Barras anchas = más incertidumbre.
        </p>
      </div>
      <div className="space-y-1.5 p-4">
        {data.slice(0, 24).map((d) => (
          <div key={d.team} className="flex items-center gap-3">
            <div className="w-28 shrink-0 truncate text-sm font-medium" title={d.display_name}>
              {d.display_name}
            </div>
            <div className="relative h-5 flex-1">
              <div className="absolute top-1/2 h-px w-full -translate-y-1/2 bg-line" />
              <div
                className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-amber-500/40"
                style={{ left: `${x(d.overall_lo)}%`, width: `${x(d.overall_hi) - x(d.overall_lo)}%` }}
              />
              <div
                className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-amber-400 ring-2 ring-ink"
                style={{ left: `${x(d.overall)}%` }}
                title={`ataque ${d.att.toFixed(2)} · defensa ${d.defense.toFixed(2)}`}
              />
            </div>
            <div className="w-24 shrink-0 text-right text-xs tabular-nums text-slate-400">
              {d.overall.toFixed(2)}{" "}
              <span className="text-slate-600">±{((d.overall_hi - d.overall_lo) / 2).toFixed(2)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
