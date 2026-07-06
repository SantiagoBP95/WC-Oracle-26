import { useQuery } from "@tanstack/react-query";

import { api } from "../api/client";
import { useModel } from "../model/ModelContext";

interface MatchResult {
  match_id: number;
  home: string;
  away: string;
  home_score: number;
  away_score: number;
  stage: string;
  predicted: "home" | "draw" | "away";
  actual: "home" | "draw" | "away";
  correct: boolean;
  top_scoreline: string;
  scoreline_correct: boolean;
  p_correct: number;
  p_home: number;
  p_draw: number;
  p_away: number;
  exp_home: number;
  exp_away: number;
  brier: number;
}

interface Metrics {
  total: number;
  correct: number;
  accuracy: number | null;
  scoreline_correct: number;
  scoreline_accuracy: number | null;
  avg_brier: number | null;
  avg_p_correct: number | null;
  matches: MatchResult[];
}

const OUTCOME_ES: Record<string, string> = { home: "Local", draw: "Empate", away: "Visitante" };

function pct(v: number) { return `${Math.round(v * 100)}%`; }

function brierColor(b: number) {
  if (b < 0.15) return "text-pitch";
  if (b < 0.25) return "text-amber-400";
  return "text-rose-400";
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card p-4 text-center">
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs text-slate-400 mt-0.5">{label}</div>
      {sub && <div className="text-[10px] text-slate-600 mt-1">{sub}</div>}
    </div>
  );
}

export default function Rendimiento() {
  const { model } = useModel();
  const { data, isLoading } = useQuery({
    queryKey: ["metrics", model],
    queryFn: async () => (await api.get<Metrics>("/metrics", { params: { model } })).data,
  });

  if (isLoading) return <p className="text-slate-400">Calculando métricas…</p>;
  if (!data) return null;

  const { total, correct, accuracy, scoreline_correct, scoreline_accuracy, avg_brier, avg_p_correct, matches } = data;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Rendimiento del modelo</h1>
        <p className="text-sm text-slate-400">
          Comparación de predicciones 1X2 vs resultados reales · partidos finalizados.
        </p>
      </div>

      {total === 0 ? (
        <div className="card p-8 text-center text-slate-500">
          <div className="text-3xl mb-2">⏳</div>
          <p>Aún no hay partidos finalizados con predicción registrada.</p>
        </div>
      ) : (
        <>
          {/* Resumen */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard label="Partidos analizados" value={String(total)} />
            <StatCard
              label="1X2 correcto"
              value={accuracy !== null ? pct(accuracy) : "—"}
              sub={`${correct} de ${total}`}
            />
            <StatCard
              label="Marcador exacto"
              value={scoreline_accuracy !== null ? pct(scoreline_accuracy) : "—"}
              sub={`${scoreline_correct} de ${total}`}
            />
            <StatCard
              label="Brier score promedio"
              value={avg_brier !== null ? avg_brier.toFixed(3) : "—"}
              sub="0 = perfecto · ≥ 0.33 = azar"
            />
            <StatCard
              label="Confianza media en el acierto"
              value={avg_p_correct !== null ? pct(avg_p_correct) : "—"}
              sub="prob. asignada al resultado real"
            />
          </div>

          {/* Tabla de partidos */}
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[600px] text-sm">
              <thead className="border-b border-line bg-panel2/50">
                <tr>
                  <th className="th text-left">Partido</th>
                  <th className="th text-center">Resultado</th>
                  <th className="th text-center">1X2 predicho</th>
                  <th className="th text-center hidden sm:table-cell">Marcador pred.</th>
                  <th className="th text-center">Real</th>
                  <th className="th text-center">Prob. real</th>
                  <th className="th text-center hidden sm:table-cell">Goles esp.</th>
                  <th className="th text-center">Brier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/40">
                {matches.map((m) => (
                  <tr key={m.match_id} className={m.correct ? "bg-pitch/5" : ""}>
                    <td className="td">
                      <div className="font-medium whitespace-nowrap">{m.home} vs {m.away}</div>
                    </td>
                    <td className="td text-center font-bold tabular-nums">
                      {m.home_score} – {m.away_score}
                    </td>
                    <td className="td text-center">
                      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                        m.correct ? "bg-pitch/20 text-pitch" : "bg-rose-900/30 text-rose-300"
                      }`}>
                        {m.correct ? "✓" : "✗"} {OUTCOME_ES[m.predicted]}
                      </span>
                    </td>
                    <td className="td text-center hidden sm:table-cell">
                      <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                        m.scoreline_correct ? "bg-pitch/20 text-pitch" : "text-slate-500"
                      }`}>
                        {m.scoreline_correct ? "✓" : ""} {m.top_scoreline}
                      </span>
                    </td>
                    <td className="td text-center text-xs text-slate-300">
                      {OUTCOME_ES[m.actual]}
                    </td>
                    <td className="td text-center tabular-nums">
                      <div className="flex flex-col items-center gap-0.5">
                        <span className="text-sm font-semibold">{pct(m.p_correct)}</span>
                        <div className="flex gap-1 text-[10px] text-slate-500">
                          <span title="Local">{pct(m.p_home)}</span>
                          <span>·</span>
                          <span title="Empate">{pct(m.p_draw)}</span>
                          <span>·</span>
                          <span title="Visitante">{pct(m.p_away)}</span>
                        </div>
                      </div>
                    </td>
                    <td className="td text-center tabular-nums text-xs text-slate-400 hidden sm:table-cell">
                      {m.exp_home}–{m.exp_away}
                    </td>
                    <td className={`td text-center tabular-nums text-xs font-semibold ${brierColor(m.brier)}`}>
                      {m.brier.toFixed(3)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Leyenda Brier */}
          <div className="text-[11px] text-slate-600 flex flex-wrap gap-4">
            <span><span className="text-pitch font-semibold">Verde</span> Brier &lt; 0.15 — buena predicción</span>
            <span><span className="text-amber-400 font-semibold">Ámbar</span> 0.15–0.25 — predicción aceptable</span>
            <span><span className="text-rose-400 font-semibold">Rojo</span> &gt; 0.25 — predicción débil</span>
          </div>
        </>
      )}
    </div>
  );
}
