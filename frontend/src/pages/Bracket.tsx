import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type CSSProperties } from "react";

import { api, apiErrorMessage } from "../api/client";
import type { Match, Simulation, TeamProb } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { pct } from "../lib/format";
import { useModel } from "../model/ModelContext";

// ── Constantes ───────────────────────────────────────────────────────────────

const KO_STAGE_ORDER = ["R32", "R16", "QF", "SF", "Final"];
const KO_STAGE_LABEL: Record<string, string> = {
  R32: "Ronda de 32", R16: "Octavos", QF: "Cuartos", SF: "Semis", Final: "Final",
};
const GROUPS = ["A","B","C","D","E","F","G","H","I","J","K","L"];
const DIAS_ES  = ["dom","lun","mar","mié","jue","vie","sáb"];
const MESES_ES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];

const COLS: { key: keyof TeamProb; label: string; short: string }[] = [
  { key: "p_advance", label: "R32",     short: "R32"   },
  { key: "p_r16",     label: "Octavos", short: "8vos"  },
  { key: "p_qf",      label: "Cuartos", short: "4tos"  },
  { key: "p_sf",      label: "Semis",   short: "SF"    },
  { key: "p_final",   label: "Final",   short: "Final" },
  { key: "p_winner",  label: "Campeón", short: "🏆"    },
];

// ── Utilidades ───────────────────────────────────────────────────────────────

function toUTC(iso: string): Date {
  return new Date(/[Z+]/.test(iso) ? iso : iso + "Z");
}

function dayLabel(dateStr: string): string {
  const d = new Date(dateStr);
  return `${DIAS_ES[d.getDay()]} ${d.getDate()} ${MESES_ES[d.getMonth()]}`;
}

function heat(v: number): CSSProperties {
  return { backgroundColor: `rgba(16,185,129,${0.06 + Math.min(1, v) * 0.6})` };
}

// ── Fila de partido completa ─────────────────────────────────────────────────

function MatchRow({ m, editable, onSaved }: { m: Match; editable: boolean; onSaved: () => void }) {
  const [home, setHome] = useState(m.home_score?.toString() ?? "");
  const [away, setAway] = useState(m.away_score?.toString() ?? "");
  const [winner, setWinner] = useState<"home" | "away" | "">(
    m.winner_team_id ? (m.winner_team_id === m.home_team?.id ? "home" : "away") : ""
  );

  const knockout = m.stage !== "group";
  const isDraw = home !== "" && away !== "" && Number(home) === Number(away);
  const needWinner = knockout && isDraw;

  const save = useMutation({
    mutationFn: async () =>
      (await api.post(`/matches/${m.id}/result`, {
        home_score: Number(home),
        away_score: Number(away),
        winner: needWinner ? winner : undefined,
      })).data,
    onSuccess: onSaved,
  });

  const pred = m.prediction;
  const finished = m.status === "finished";
  const disabled = save.isPending || home === "" || away === "" || (needWinner && winner === "");

  const hora = m.scheduled_at
    ? `${toUTC(m.scheduled_at).getHours().toString().padStart(2,"0")}:${toUTC(m.scheduled_at).getMinutes().toString().padStart(2,"0")}`
    : "—";

  const stageLabel = m.stage === "group"
    ? `Grupo ${m.group_label}`
    : (KO_STAGE_LABEL[m.stage] ?? m.stage);

  return (
    <div className="px-4 py-3">
      {/* Meta: hora · etapa · sede */}
      <div className="mb-2 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
        <span className="tabular-nums font-medium">{hora}</span>
        <span>·</span>
        <span>{stageLabel}</span>
        {m.venue && <><span>·</span><span className="truncate">{m.venue}</span></>}
        {finished && (
          <span className="ml-auto rounded border border-pitch/40 px-1.5 py-0.5 text-[10px] font-semibold text-pitch">
            Finalizado
          </span>
        )}
      </div>

      {/* Equipos + marcador */}
      <div className="flex items-center gap-3">
        <span className="flex-1 truncate font-semibold text-sm sm:text-base">
          {m.home_team?.display_name ?? "—"}
        </span>
        <span className="shrink-0 rounded-md bg-panel2 px-3 py-1 text-sm font-bold tabular-nums text-white">
          {finished ? `${m.home_score} – ${m.away_score}` : "vs"}
        </span>
        <span className="flex-1 truncate text-right font-semibold text-sm sm:text-base">
          {m.away_team?.display_name ?? "—"}
        </span>
      </div>

      {/* Probabilidades 1X2 + marcador esperado (solo si no terminó y hay predicción) */}
      {pred && !finished && (
        <div className="mt-2.5 space-y-1.5">
          {/* Pills de probabilidad */}
          <div className="flex gap-1.5">
            <ProbPill
              label={m.home_team?.display_name ?? "Local"}
              sublabel="1"
              value={pred.p_home}
              color="text-sky-400"
            />
            <ProbPill
              label="Empate"
              sublabel="X"
              value={pred.p_draw}
              color="text-slate-300"
            />
            <ProbPill
              label={m.away_team?.display_name ?? "Visitante"}
              sublabel="2"
              value={pred.p_away}
              color="text-amber-400"
            />
          </div>
          {/* Goles esperados + mejor marcador */}
          <div className="flex flex-wrap gap-3 text-[11px] text-slate-500">
            <span>
              Goles esperados:{" "}
              <span className="font-semibold text-slate-300 tabular-nums">
                {pred.exp_home_goals.toFixed(1)} – {pred.exp_away_goals.toFixed(1)}
              </span>
            </span>
            {pred.top_scoreline && (
              <span>
                Marcador más probable:{" "}
                <span className="font-semibold text-slate-300">{pred.top_scoreline}</span>
              </span>
            )}
          </div>
        </div>
      )}

      {/* Resultado final (mostramos predicción vs real) */}
      {pred && finished && (
        <div className="mt-1.5 flex flex-wrap gap-3 text-[11px] text-slate-500">
          <span>
            Predicción:{" "}
            <span className="tabular-nums text-slate-400">
              {pct(pred.p_home,0)} / {pct(pred.p_draw,0)} / {pct(pred.p_away,0)}
            </span>
          </span>
          <span>
            Esp.:{" "}
            <span className="tabular-nums text-slate-400">
              {pred.exp_home_goals.toFixed(1)}–{pred.exp_away_goals.toFixed(1)}
            </span>
          </span>
        </div>
      )}

      {/* Info penaltis */}
      {finished && m.winner_team_id && m.home_score === m.away_score && (
        <div className="mt-1 text-[11px] text-slate-500">
          Penaltis: avanza{" "}
          <span className="font-semibold text-white">
            {m.winner_team_id === m.home_team?.id ? m.home_team?.display_name : m.away_team?.display_name}
          </span>
        </div>
      )}

      {/* Admin: inputs de marcador */}
      {editable && m.home_team && m.away_team && (
        <div className="mt-2.5 flex items-center gap-2">
          <input
            className="input w-12 text-center"
            value={home}
            inputMode="numeric"
            placeholder="0"
            onChange={(e) => setHome(e.target.value)}
          />
          <span className="text-slate-500 text-xs">–</span>
          <input
            className="input w-12 text-center"
            value={away}
            inputMode="numeric"
            placeholder="0"
            onChange={(e) => setAway(e.target.value)}
          />
          <button
            className="btn-primary ml-1 flex-1 px-3 py-1.5 text-xs sm:flex-none"
            disabled={disabled}
            onClick={() => save.mutate()}
          >
            {save.isPending ? "…" : "Guardar"}
          </button>
        </div>
      )}

      {needWinner && editable && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-amber-300">Empate → avanza por penaltis:</span>
          {(["home", "away"] as const).map((side) => (
            <button
              key={side}
              onClick={() => setWinner(side)}
              className={`rounded-full border px-2 py-0.5 ${
                winner === side ? "border-pitch bg-pitch/20 text-pitch" : "border-line text-slate-300"
              }`}
            >
              {side === "home" ? m.home_team?.display_name : m.away_team?.display_name}
            </button>
          ))}
        </div>
      )}

      {save.isError && (
        <div className="mt-1 text-xs text-rose-300">{apiErrorMessage(save.error)}</div>
      )}
    </div>
  );
}

function ProbPill({ label, sublabel, value, color }: {
  label: string; sublabel: string; value: number; color: string;
}) {
  return (
    <div className="flex flex-1 flex-col items-center rounded-lg bg-panel2/80 px-2 py-1.5 gap-0.5">
      <div className="flex items-baseline gap-1">
        <span className="text-[10px] text-slate-600">{sublabel}</span>
        <span className={`text-base font-bold tabular-nums leading-none ${color}`}>
          {pct(value, 0)}
        </span>
      </div>
      <span className="max-w-full truncate text-[10px] text-slate-500 text-center">{label}</span>
    </div>
  );
}

// ── Página principal unificada ────────────────────────────────────────────────

export default function Bracket() {
  const { can } = useAuth();
  const { model } = useModel();
  const qc = useQueryClient();
  const editable = can("record_result");

  const [tab, setTab] = useState<"group" | "ko">("group");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [selectedGroup, setSelectedGroup] = useState<string | null>(null);

  // Datos de partidos (filtrados por modelo activo)
  const { data: matches, isLoading: loadingMatches } = useQuery({
    queryKey: ["matches", model],
    queryFn: async () => (await api.get<Match[]>("/matches", { params: { model } })).data,
    refetchInterval: 60_000,
  });

  // Datos de simulación (bracket)
  const { data: sim } = useQuery({
    queryKey: ["sim-latest", model],
    queryFn: async () =>
      (await api.get<Simulation>("/simulations/latest", { params: { model } })).data,
  });

  function onSaved() {
    qc.invalidateQueries({ queryKey: ["matches"] });
    qc.invalidateQueries({ queryKey: ["sim-latest"] });
  }

  const sync = useMutation({
    mutationFn: async () => (await api.post("/matches/sync")).data,
    onSuccess: onSaved,
  });

  // ── Listas derivadas ──
  const groupMatches = (matches ?? [])
    .filter((m) => m.stage === "group")
    .sort((a, b) => (a.scheduled_at ?? "").localeCompare(b.scheduled_at ?? ""));

  const koMatches = (matches ?? [])
    .filter((m) => m.stage !== "group")
    .sort((a, b) => {
      const si = KO_STAGE_ORDER.indexOf(a.stage);
      const sj = KO_STAGE_ORDER.indexOf(b.stage);
      if (si !== sj) return si - sj;
      return (a.scheduled_at ?? "").localeCompare(b.scheduled_at ?? "");
    });

  const active = tab === "group" ? groupMatches : koMatches;

  // Fechas únicas del tab activo
  const uniqueDates = Array.from(
    new Set(active.filter((m) => m.scheduled_at).map((m) => toUTC(m.scheduled_at!).toDateString()))
  );

  const todayStr = new Date().toDateString();
  // Solo pre-selecciona hoy si no hay grupo activo
  const effectiveDate = selectedDate ?? (selectedGroup ? null : (uniqueDates.includes(todayStr) ? todayStr : null));

  // Grupos disponibles en el tab de grupos
  const availableGroups = tab === "group"
    ? GROUPS.filter((g) => groupMatches.some((m) => m.group_label === g))
    : [];

  // Filtrado: fecha OR grupo (mutuamente excluyentes en práctica)
  const filtered = active.filter((m) => {
    if (selectedGroup && tab === "group") return m.group_label === selectedGroup;
    if (effectiveDate) return m.scheduled_at ? toUTC(m.scheduled_at).toDateString() === effectiveDate : false;
    return true;
  });

  // Agrupar resultado filtrado
  const groupedFiltered = tab === "group"
    ? (() => {
        const byG: Record<string, Match[]> = {};
        for (const m of filtered) (byG[m.group_label ?? "?"] ??= []).push(m);
        return byG;
      })()
    : (() => {
        const byS: Record<string, Match[]> = {};
        for (const m of filtered) (byS[m.stage] ??= []).push(m);
        return byS;
      })();

  const bracketRows = sim ? [...sim.probs].sort((a, b) => b.p_winner - a.p_winner) : [];

  if (loadingMatches) return <p className="text-slate-400">Cargando partidos…</p>;

  return (
    <div className="space-y-6">
      {/* ── Cabecera ── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Partidos</h1>
          <p className="text-sm text-slate-400">
            Predicciones del modelo · probabilidades y goles estimados por partido
          </p>
        </div>
        {editable && (
          <div className="text-right">
            <button className="btn-ghost" disabled={sync.isPending} onClick={() => sync.mutate()}>
              {sync.isPending ? "Sincronizando…" : "↻ Sincronizar (API)"}
            </button>
            {sync.isError && (
              <div className="mt-1 max-w-xs text-xs text-amber-300">{apiErrorMessage(sync.error)}</div>
            )}
            {sync.isSuccess && (
              <div className="mt-1 text-xs text-pitch">
                {(sync.data as { updated: number; fetched: number }).updated} actualizados
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Tabs ── */}
      <div className="flex gap-2">
        <button
          className={tab === "group" ? "btn-primary" : "btn-ghost"}
          onClick={() => { setTab("group"); setSelectedDate(null); setSelectedGroup(null); }}
        >
          Fase de grupos
        </button>
        <button
          className={tab === "ko" ? "btn-primary" : "btn-ghost"}
          onClick={() => { setTab("ko"); setSelectedDate(null); setSelectedGroup(null); }}
        >
          Eliminatorias{koMatches.length ? ` (${koMatches.length})` : ""}
        </button>
      </div>

      {/* ── Filtros ── */}
      <div className="space-y-2">
        {/* Fechas */}
        {uniqueDates.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            <span className="self-center text-[10px] uppercase tracking-wide text-slate-600 mr-1">Fecha</span>
            {uniqueDates.map((ds) => {
              const isActive = ds === effectiveDate;
              const isToday = ds === todayStr;
              return (
                <button
                  key={ds}
                  onClick={() => { setSelectedDate(isActive ? null : ds); setSelectedGroup(null); }}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    isActive
                      ? "bg-pitch text-white"
                      : "border border-line bg-panel2 text-slate-400 hover:text-white"
                  }`}
                >
                  {dayLabel(ds)}{isToday ? " · hoy" : ""}
                </button>
              );
            })}
          </div>
        )}

        {/* Grupos (solo en tab de grupos) */}
        {tab === "group" && availableGroups.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            <span className="self-center text-[10px] uppercase tracking-wide text-slate-600 mr-1">Grupo</span>
            {availableGroups.map((g) => {
              const isActive = g === selectedGroup;
              return (
                <button
                  key={g}
                  onClick={() => { setSelectedGroup(isActive ? null : g); setSelectedDate(null); }}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    isActive
                      ? "bg-sky-600 text-white"
                      : "border border-line bg-panel2 text-slate-400 hover:text-white"
                  }`}
                >
                  {g}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Listado de partidos ── */}
      {tab === "ko" && koMatches.length === 0 ? (
        <div className="card p-4 text-sm text-slate-400">
          Las eliminatorias se materializan al cerrar la fase de grupos.
        </div>
      ) : filtered.length === 0 ? (
        <div className="card p-4 text-sm text-slate-400">
          No hay partidos para los filtros seleccionados.
        </div>
      ) : tab === "group" ? (
        // Agrupar por grupo
        Object.keys(groupedFiltered).sort().map((g) => (
          <div key={g} className="card overflow-hidden">
            <div className="border-b border-line bg-panel2/50 px-4 py-2 text-sm font-semibold text-slate-300">
              Grupo {g}
            </div>
            <div className="divide-y divide-line/50">
              {groupedFiltered[g].map((m) => (
                <MatchRow key={m.id} m={m} editable={editable} onSaved={onSaved} />
              ))}
            </div>
          </div>
        ))
      ) : (
        // Agrupar por ronda KO
        KO_STAGE_ORDER.filter((s) => groupedFiltered[s]?.length).map((s) => (
          <div key={s} className="card overflow-hidden">
            <div className="border-b border-line bg-panel2/50 px-4 py-2 text-sm font-semibold text-slate-300">
              {KO_STAGE_LABEL[s]}
            </div>
            <div className="divide-y divide-line/50">
              {groupedFiltered[s].map((m) => (
                <MatchRow key={m.id} m={m} editable={editable} onSaved={onSaved} />
              ))}
            </div>
          </div>
        ))
      )}

      {/* ── Camino al título (bracket prob table) ── */}
      {bracketRows.length > 0 && (
        <div className="space-y-2">
          <h2 className="text-lg font-semibold">Camino al título</h2>
          <p className="text-xs text-slate-500">
            Probabilidades por ronda · Monte Carlo ({sim?.runs.toLocaleString()} torneos)
          </p>
          <div className="card overflow-x-auto">
            <table className="w-full min-w-[480px]">
              <thead className="border-b border-line bg-panel2/50">
                <tr>
                  <th className="th w-8">#</th>
                  <th className="th">Equipo</th>
                  {COLS.map((c) => (
                    <th key={c.key} className="th text-center">
                      <span className="hidden sm:inline">{c.label}</span>
                      <span className="sm:hidden">{c.short}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {bracketRows.map((p, i) => (
                  <tr key={p.team} className="border-b border-line/50">
                    <td className="td text-slate-500">{i + 1}</td>
                    <td className="td whitespace-nowrap font-medium">{p.display_name}</td>
                    {COLS.map((c) => (
                      <td
                        key={c.key}
                        className="td text-center tabular-nums text-xs sm:text-sm"
                        style={heat(p[c.key] as number)}
                      >
                        {pct(p[c.key] as number, 0)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
