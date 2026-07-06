import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { api, apiErrorMessage } from "../api/client";
import type { Simulation, TeamProb } from "../api/types";
import CredibleIntervals from "../components/CredibleIntervals";
import { pct } from "../lib/format";
import { useModel } from "../model/ModelContext";

type MetricKey = "p_winner" | "p_final" | "p_advance";

const METRICS: { key: MetricKey; label: string }[] = [
  { key: "p_winner", label: "Campeón" },
  { key: "p_final", label: "Finalista" },
  { key: "p_advance", label: "Clasifica" },
];

const MODEL_COLORS: Record<string, string> = {
  elo: "#10b981",
  xgboost: "#38bdf8",
  nn: "#a78bfa",
  bayesian: "#fbbf24",
};

export default function Comparador() {
  const { models } = useModel();
  const [metric, setMetric] = useState<MetricKey>("p_winner");
  const { data, isLoading, error } = useQuery({
    queryKey: ["compare"],
    queryFn: async () => (await api.get<Simulation[]>("/simulations/compare")).data,
  });

  if (isLoading) return <p className="text-slate-400">Cargando…</p>;
  if (error) return <p className="text-amber-300">{apiErrorMessage(error)}</p>;
  if (!data || data.length < 2)
    return (
      <p className="text-slate-400">
        Entrena al menos dos modelos para comparar:{" "}
        <code className="text-pitch">python -m ml.train --models</code>.
      </p>
    );

  const labelOf = (name: string) => models.find((m) => m.name === name)?.label ?? name;
  const modelNames = data.map((d) => d.model_name);

  const byModel: Record<string, Record<string, TeamProb>> = {};
  for (const sim of data) {
    byModel[sim.model_name] = {};
    for (const p of sim.probs) byModel[sim.model_name][p.team] = p;
  }

  const teams = data[0].probs.map((p) => p.team);
  const val = (model: string, team: string) =>
    (byModel[model]?.[team]?.[metric] as number) ?? 0;
  const avg = (team: string) =>
    modelNames.reduce((s, m) => s + val(m, team), 0) / modelNames.length;
  const display = (team: string) => byModel[data[0].model_name][team]?.display_name ?? team;

  const sortedTeams = [...teams].sort((a, b) => avg(b) - avg(a));

  const chartData = sortedTeams.slice(0, 10).map((team) => {
    const row: Record<string, number | string> = { name: display(team) };
    for (const m of modelNames) row[m] = +(val(m, team) * 100).toFixed(1);
    return row;
  });
  const metricLabel = METRICS.find((m) => m.key === metric)?.label;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Comparador de modelos</h1>
          <p className="text-sm text-slate-400">
            Probabilidades lado a lado de {modelNames.length} modelos ·{" "}
            {modelNames.map(labelOf).join(" · ")}
          </p>
        </div>
        <div className="flex gap-1">
          {METRICS.map((mt) => (
            <button
              key={mt.key}
              onClick={() => setMetric(mt.key)}
              className={
                metric === mt.key ? "btn-primary px-3 py-1.5 text-xs" : "btn-ghost px-3 py-1.5 text-xs"
              }
            >
              {mt.label}
            </button>
          ))}
        </div>
      </div>

      <div className="card p-5">
        <h2 className="mb-4 text-sm font-semibold text-slate-300">Top 10 — {metricLabel} (%)</h2>
        <ResponsiveContainer width="100%" height={380}>
          <BarChart data={chartData} margin={{ left: 8, right: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1f2c47" vertical={false} />
            <XAxis
              dataKey="name"
              stroke="#94a3b8"
              fontSize={11}
              angle={-25}
              textAnchor="end"
              height={64}
              interval={0}
            />
            <YAxis stroke="#64748b" fontSize={12} unit="%" />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              contentStyle={{ background: "#111a2e", border: "1px solid #1f2c47", borderRadius: 8 }}
            />
            <Legend />
            {modelNames.map((m) => (
              <Bar key={m} dataKey={m} name={labelOf(m)} fill={MODEL_COLORS[m] ?? "#64748b"} radius={[3, 3, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full min-w-[640px]">
          <thead className="border-b border-line bg-panel2/50">
            <tr>
              <th className="th">#</th>
              <th className="th">Equipo</th>
              {modelNames.map((m) => (
                <th key={m} className="th text-right">
                  {labelOf(m)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedTeams.slice(0, 24).map((team, i) => {
              const vals = modelNames.map((m) => val(m, team));
              const max = Math.max(...vals);
              return (
                <tr key={team} className="border-b border-line/50 hover:bg-panel2/30">
                  <td className="td text-slate-500">{i + 1}</td>
                  <td className="td font-medium">{display(team)}</td>
                  {modelNames.map((m, j) => (
                    <td
                      key={m}
                      className={`td text-right tabular-nums ${
                        vals[j] === max && max > 0 ? "font-bold text-pitch" : "text-slate-300"
                      }`}
                    >
                      {pct(vals[j], metric === "p_advance" ? 0 : 1)}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="px-3 py-2 text-xs text-slate-500">
          En verde, el modelo más optimista para cada equipo.
        </p>
      </div>

      <CredibleIntervals />
    </div>
  );
}
