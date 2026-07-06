import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { useNavigate } from "react-router-dom";

import { api, apiErrorMessage } from "../api/client";
import type { Match, Simulation } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { useIsPreview } from "../auth/useIsPreview";
import { pct } from "../lib/format";
import { useModel } from "../model/ModelContext";

const KO_STAGE_LABEL: Record<string, string> = {
  R32: "Ronda de 32", R16: "Octavos", QF: "Cuartos", SF: "Semis", Final: "Final",
};

const DIAS_ES  = ["dom","lun","mar","mié","jue","vie","sáb"];
const MESES_ES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];

function toUTC(iso: string): Date {
  return new Date(/[Z+]/.test(iso) ? iso : iso + "Z");
}

// ── Partidos de hoy (máx 2) para plan Preview ────────────────────────────────
function TodayMatchesPreview({ model }: { model: string }) {
  const { data: matches } = useQuery({
    queryKey: ["matches", model],
    queryFn: async () => (await api.get<Match[]>("/matches", { params: { model } })).data,
    refetchInterval: 60_000,
  });

  if (!matches) return null;

  const todayStr = new Date().toDateString();
  const now = new Date();
  const dayLabel = `${DIAS_ES[now.getDay()]} ${now.getDate()} ${MESES_ES[now.getMonth()]}`;

  const todayMatches = matches
    .filter((m) => m.scheduled_at && toUTC(m.scheduled_at).toDateString() === todayStr)
    .sort((a, b) => {
      const maxA = a.prediction ? Math.max(a.prediction.p_home, a.prediction.p_draw, a.prediction.p_away) : 0;
      const maxB = b.prediction ? Math.max(b.prediction.p_home, b.prediction.p_draw, b.prediction.p_away) : 0;
      return maxB - maxA;
    })
    .slice(0, 2);

  if (todayMatches.length === 0) return null;

  return (
    <div className="space-y-2">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
        Partidos de hoy · {dayLabel}
      </h2>
      <div className="card overflow-hidden">
        <div className="divide-y divide-line/40">
          {todayMatches.map((m) => <MatchRow key={m.id} m={m} />)}
        </div>
      </div>
    </div>
  );
}

// ── Partidos del día ─────────────────────────────────────────────────────────
function TodayMatches({ model }: { model: string }) {
  const { data: matches } = useQuery({
    queryKey: ["matches", model],
    queryFn: async () => (await api.get<Match[]>("/matches", { params: { model } })).data,
    refetchInterval: 60_000,
  });

  if (!matches) return null;

  const todayStr = new Date().toDateString();

  const todayMatches = matches
    .filter((m) => m.scheduled_at && toUTC(m.scheduled_at).toDateString() === todayStr)
    .sort((a, b) => (a.scheduled_at ?? "").localeCompare(b.scheduled_at ?? ""));

  const tomorrow = matches
    .filter((m) => {
      if (!m.scheduled_at) return false;
      const d = toUTC(m.scheduled_at);
      const t = new Date();
      t.setDate(t.getDate() + 1);
      return d.toDateString() === t.toDateString();
    })
    .sort((a, b) => (a.scheduled_at ?? "").localeCompare(b.scheduled_at ?? ""));

  const now = new Date();
  const dayLabel = `${DIAS_ES[now.getDay()]} ${now.getDate()} ${MESES_ES[now.getMonth()]}`;

  if (todayMatches.length === 0 && tomorrow.length === 0) return null;

  return (
    <div className="space-y-2">
      {todayMatches.length > 0 && (
        <>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Partidos de hoy · {dayLabel}
          </h2>
          <div className="card overflow-hidden">
            <div className="divide-y divide-line/40">
              {todayMatches.map((m) => <MatchRow key={m.id} m={m} />)}
            </div>
          </div>
        </>
      )}

      {tomorrow.length > 0 && (
        <>
          <h2 className="mt-4 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Mañana
          </h2>
          <div className="card overflow-hidden">
            <div className="divide-y divide-line/40">
              {tomorrow.map((m) => <MatchRow key={m.id} m={m} />)}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function MatchRow({ m }: { m: Match }) {
  const stageLabel = m.stage === "group"
    ? `Grupo ${m.group_label}`
    : (KO_STAGE_LABEL[m.stage] ?? m.stage);
  const pred = m.prediction;
  const finished = m.status === "finished";

  const hora = m.scheduled_at
    ? `${toUTC(m.scheduled_at).getHours().toString().padStart(2,"0")}:${toUTC(m.scheduled_at).getMinutes().toString().padStart(2,"0")}`
    : "—";

  return (
    <div className="px-4 py-3">
      {/* Fila superior: hora + etapa + resultado */}
      <div className="mb-1.5 flex items-center gap-2 text-[10px] text-slate-500">
        <span className="tabular-nums">{hora}</span>
        <span>·</span>
        <span>{stageLabel}</span>
        {m.venue && <><span>·</span><span className="truncate">{m.venue}</span></>}
        {finished && (
          <span className="ml-auto rounded border border-pitch/40 px-1 text-pitch">Finalizado</span>
        )}
      </div>

      {/* Equipos y marcador */}
      <div className="flex items-center gap-2">
        <span className="flex-1 truncate font-semibold">{m.home_team?.display_name ?? "—"}</span>
        <span className="shrink-0 rounded-md bg-panel2 px-3 py-0.5 text-sm font-bold tabular-nums text-white">
          {finished ? `${m.home_score} – ${m.away_score}` : "vs"}
        </span>
        <span className="flex-1 truncate text-right font-semibold">{m.away_team?.display_name ?? "—"}</span>
      </div>

      {/* Goles esperados debajo de los equipos */}
      {pred && !finished && pred.exp_home_goals != null && (
        <div className="mt-1 text-center text-[11px] text-slate-400 tabular-nums">
          {pred.exp_home_goals.toFixed(1)} – {pred.exp_away_goals.toFixed(1)} goles esperados
          {pred.top_scoreline && (
            <span className="ml-2 text-slate-500">· más probable: {pred.top_scoreline}</span>
          )}
        </div>
      )}

      {/* Probabilidades 1X2 */}
      {pred && !finished && (
        <div className="mt-2 flex gap-1.5">
          <ProbPill label={m.home_team?.display_name?.split(" ").pop() ?? "L"} value={pred.p_home} color="text-sky-300" bg="bg-sky-900/40" />
          <ProbPill label="Empate" value={pred.p_draw} color="text-slate-200" bg="bg-slate-700/50" />
          <ProbPill label={m.away_team?.display_name?.split(" ").pop() ?? "V"} value={pred.p_away} color="text-amber-300" bg="bg-amber-900/40" />
        </div>
      )}
    </div>
  );
}

function ProbPill({ label, value, color, bg }: { label: string; value: number; color: string; bg: string }) {
  return (
    <div className={`flex flex-1 flex-col items-center rounded-lg px-2 py-1.5 ${bg}`}>
      <span className={`text-base font-bold tabular-nums leading-tight ${color}`}>{pct(value, 0)}</span>
      <span className="mt-0.5 max-w-full truncate text-center text-[10px] text-slate-400">{label}</span>
    </div>
  );
}

// ── Dashboard principal ───────────────────────────────────────────────────────
export default function Dashboard() {
  const { can } = useAuth();
  const isPreview = useIsPreview();
  const navigate = useNavigate();
  const { model, models } = useModel();
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["sim-latest", model],
    queryFn: async () =>
      (await api.get<Simulation>("/simulations/latest", { params: { model } })).data,
  });
  const modelLabel = models.find((m) => m.name === model)?.label ?? model;

  const resim = useMutation({
    mutationFn: async () =>
      (await api.post("/simulations/run", { runs: 10000, notes: "manual", model })).data,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sim-latest"] });
      qc.invalidateQueries({ queryKey: ["matches"] });
    },
  });

  if (isLoading) return <p className="text-slate-400">Cargando simulación…</p>;
  if (error || !data)
    return (
      <p className="text-slate-400">
        No hay simulación todavía. Ejecuta <code className="text-pitch">python -m ml.train</code>.
      </p>
    );

  const probs = data.probs;
  const top = probs.slice(0, 12);
  const chartData = top.map((p) => ({ name: p.display_name, value: +(p.p_winner * 100).toFixed(1) }));
  const favorite = probs[0];

  // ── Vista simplificada para plan Preview ─────────────────────────────────────
  if (isPreview) {
    const todayStr = new Date().toDateString();
    const previewMatches = (data as any)?._allMatches ?? [];
    // We reuse the simulation data we already have; matches come from TodayMatches' own query.
    const top8 = probs.slice(0, 8);
    const chartDataPreview = top8.map((p) => ({ name: p.display_name, value: +(p.p_winner * 100).toFixed(1) }));

    return (
      <div className="mx-auto max-w-lg space-y-5 px-2 py-4">
        {/* Banner Preview */}
        <div className="flex items-center justify-between rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3">
          <div>
            <span className="text-xs font-semibold text-amber-400">PLAN PREVIEW</span>
            <p className="text-xs text-slate-400 mt-0.5">Acceso gratuito · Upgrade para ver todo</p>
          </div>
          <button
            onClick={() => navigate("/upgrade")}
            className="rounded-lg bg-pitch px-3 py-1.5 text-xs font-semibold text-ink hover:bg-pitch/80 transition"
          >
            Plan Pro →
          </button>
        </div>

        {/* Gráfico real de posibles campeonas */}
        <div className="card p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-300">Top 8 — probabilidad de campeón</h2>
          <ResponsiveContainer width="100%" height={240}>
            <BarChart data={chartDataPreview} layout="vertical" margin={{ left: 8, right: 16, top: 2, bottom: 2 }}>
              <XAxis type="number" stroke="#334155" fontSize={10} unit="%" tick={{ fill: "#64748b" }} />
              <YAxis
                type="category"
                dataKey="name"
                width={86}
                tick={{ fill: "#94a3b8", fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                cursor={{ fill: "rgba(255,255,255,0.04)" }}
                contentStyle={{ background: "#111a2e", border: "1px solid #1f2c47", borderRadius: 8, color: "#e2e8f0" }}
                formatter={(v: number) => [`${v}%`, "Campeón"]}
                labelStyle={{ color: "#94a3b8", fontSize: 11 }}
                itemStyle={{ color: "#34d399", fontWeight: 700 }}
              />
              <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={18}>
                {chartDataPreview.map((_: unknown, i: number) => (
                  <Cell key={i} fill={i === 0 ? "#34d399" : i < 3 ? "#10b981" : "#059669"} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="mt-2 text-center text-[10px] text-slate-600">
            Simulación #{data.id} · {data.runs.toLocaleString()} torneos ·{" "}
            <button onClick={() => navigate("/upgrade")} className="text-pitch underline">Ver análisis completo →</button>
          </p>
        </div>

        {/* Hasta 2 partidos de hoy únicamente */}
        <TodayMatchesPreview model={model} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">WC Oracle 2026</h1>
          <p className="text-sm text-slate-400">
            Simulación #{data.id} · {data.runs.toLocaleString()} torneos · modelo {modelLabel}
          </p>
        </div>
        {can("run_simulation") && (
          <button className="btn-primary" disabled={resim.isPending} onClick={() => resim.mutate()}>
            {resim.isPending ? "Simulando…" : "Re-simular (10k)"}
          </button>
        )}
      </div>

      {resim.isError && (
        <div className="rounded-lg border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
          {apiErrorMessage(resim.error)}
        </div>
      )}

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard label="Favorito" value={favorite.display_name} sub={pct(favorite.p_winner)} />
        <StatCard label="Final (fav.)" value={pct(favorite.p_final)} sub={favorite.display_name} />
        <StatCard label="Equipos" value="48" sub="12 grupos · 104 partidos" className="col-span-2 sm:col-span-1" />
      </div>

      {/* Bar chart top 12 */}
      <div className="card p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-300">Top 12 — probabilidad de campeón</h2>
        <ResponsiveContainer width="100%" height={310}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 16, top: 2, bottom: 2 }}>
            <XAxis type="number" stroke="#334155" fontSize={10} unit="%" tick={{ fill: "#64748b" }} />
            <YAxis
              type="category"
              dataKey="name"
              width={90}
              tick={{ fill: "#94a3b8", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip
              cursor={{ fill: "rgba(255,255,255,0.04)" }}
              contentStyle={{ background: "#111a2e", border: "1px solid #1f2c47", borderRadius: 8, color: "#e2e8f0" }}
              formatter={(v: number) => [`${v}%`, "Campeón"]}
              labelStyle={{ color: "#94a3b8", fontSize: 11 }}
              itemStyle={{ color: "#34d399", fontWeight: 700 }}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={20}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={i === 0 ? "#34d399" : i < 3 ? "#10b981" : "#059669"} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Partidos del día */}
      <TodayMatches model={model} />
    </div>
  );
}

function StatCard({ label, value, sub, className = "" }: { label: string; value: string; sub: string; className?: string }) {
  return (
    <div className={`card p-3 sm:p-4 ${className}`}>
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 truncate text-lg font-bold text-pitch sm:text-xl">{value}</div>
      <div className="text-xs text-slate-400">{sub}</div>
    </div>
  );
}
