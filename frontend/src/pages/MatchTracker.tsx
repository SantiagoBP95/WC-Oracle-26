import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api, apiErrorMessage } from "../api/client";
import type { Match } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { pct } from "../lib/format";

const KO_STAGES = [
  { key: "R32", label: "Ronda de 32" },
  { key: "R16", label: "Octavos de final" },
  { key: "QF", label: "Cuartos de final" },
  { key: "SF", label: "Semifinales" },
  { key: "Final", label: "Final" },
];

async function fetchMatches(): Promise<Match[]> {
  const { data } = await api.get<Match[]>("/matches");
  return data;
}

export default function MatchTracker() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const editable = can("record_result");
  const [tab, setTab] = useState<"group" | "ko">("group");
  const { data, isLoading } = useQuery({ queryKey: ["matches"], queryFn: fetchMatches });

  function onSaved() {
    qc.invalidateQueries({ queryKey: ["matches"] });
    qc.invalidateQueries({ queryKey: ["sim-latest"] });
  }

  const sync = useMutation({
    mutationFn: async () => (await api.post("/matches/sync")).data,
    onSuccess: onSaved,
  });

  if (isLoading || !data) return <p className="text-slate-400">Cargando partidos…</p>;

  const groupMatches = data.filter((m) => m.stage === "group");
  const koMatches = data.filter((m) => m.stage !== "group");

  const byGroup: Record<string, Match[]> = {};
  for (const m of groupMatches) (byGroup[m.group_label ?? "?"] ??= []).push(m);
  const byStage: Record<string, Match[]> = {};
  for (const m of koMatches) (byStage[m.stage] ??= []).push(m);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Partidos</h1>
          <p className="text-sm text-slate-400">
            {editable
              ? "Registra los marcadores; las probabilidades y el bracket se actualizan solos."
              : "Predicciones del modelo (solo lectura)."}
          </p>
        </div>
        {editable && (
          <div className="text-right">
            <button className="btn-ghost" disabled={sync.isPending} onClick={() => sync.mutate()}>
              {sync.isPending ? "Sincronizando…" : "↻ Sincronizar (API-Football)"}
            </button>
            {sync.isError && (
              <div className="mt-1 max-w-xs text-xs text-amber-300">{apiErrorMessage(sync.error)}</div>
            )}
            {sync.isSuccess && (
              <div className="mt-1 text-xs text-pitch">
                {sync.data.updated} actualizados de {sync.data.fetched}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="flex gap-2">
        <button className={tab === "group" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("group")}>
          Fase de grupos
        </button>
        <button className={tab === "ko" ? "btn-primary" : "btn-ghost"} onClick={() => setTab("ko")}>
          Eliminatorias{koMatches.length ? ` (${koMatches.length})` : ""}
        </button>
      </div>

      {tab === "group" &&
        Object.keys(byGroup)
          .sort()
          .map((g) => (
            <div key={g} className="card overflow-hidden">
              <div className="border-b border-line bg-panel2/50 px-4 py-2 text-sm font-semibold text-slate-300">
                Grupo {g}
              </div>
              <div className="divide-y divide-line/50">
                {byGroup[g].map((m) => (
                  <MatchRow key={m.id} m={m} editable={editable} onSaved={onSaved} />
                ))}
              </div>
            </div>
          ))}

      {tab === "ko" && koMatches.length === 0 && (
        <p className="text-slate-400">
          Las eliminatorias se materializan automáticamente al cerrar la fase de grupos (los 72 partidos).
        </p>
      )}

      {tab === "ko" &&
        KO_STAGES.filter((s) => byStage[s.key]?.length).map((s) => (
          <div key={s.key} className="card overflow-hidden">
            <div className="border-b border-line bg-panel2/50 px-4 py-2 text-sm font-semibold text-slate-300">
              {s.label}
            </div>
            <div className="divide-y divide-line/50">
              {byStage[s.key].map((m) => (
                <MatchRow key={m.id} m={m} editable={editable} onSaved={onSaved} />
              ))}
            </div>
          </div>
        ))}
    </div>
  );
}

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
  const disabled = save.isPending || home === "" || away === "" || (needWinner && winner === "");

  const DIAS_ES  = ["dom","lun","mar","mié","jue","vie","sáb"];
  const MESES_ES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
  function fmtFecha(iso: string | null | undefined): string {
    if (!iso) return "";
    const d = new Date(/[Z+]/.test(iso) ? iso : iso + "Z");
    return `${DIAS_ES[d.getDay()]} ${d.getDate()} ${MESES_ES[d.getMonth()]}  ${d.getHours().toString().padStart(2,"0")}:${d.getMinutes().toString().padStart(2,"0")}`;
  }
  const fecha = fmtFecha(m.scheduled_at);

  return (
    <div className="px-3 py-3 sm:px-4">
      {/* Fecha */}
      {fecha && (
        <div className="mb-1.5 text-[11px] text-slate-500">{fecha}</div>
      )}
      {/* Equipos: siempre en fila */}
      <div className="flex items-center justify-between gap-2">
        <span className="flex-1 truncate font-medium text-sm">{m.home_team?.display_name ?? "—"}</span>
        {/* Marcador (si terminó) o score actual en el centro */}
        <span className="mx-1 text-xs font-semibold tabular-nums text-slate-300 whitespace-nowrap">
          {m.status === "finished"
            ? `${m.home_score} - ${m.away_score}`
            : <span className="text-slate-500 text-xs">vs</span>}
        </span>
        <span className="flex-1 truncate text-right font-medium text-sm">{m.away_team?.display_name ?? "—"}</span>
      </div>

      {/* Predicciones */}
      {pred && (
        <div className="mt-1.5 flex flex-wrap items-center gap-1 text-xs text-slate-400">
          <span className="chip">1 {pct(pred.p_home, 0)}</span>
          <span className="chip">X {pct(pred.p_draw, 0)}</span>
          <span className="chip">2 {pct(pred.p_away, 0)}</span>
          <span className="ml-1 text-slate-500">~{pred.exp_home_goals.toFixed(1)}-{pred.exp_away_goals.toFixed(1)}</span>
          {m.status === "finished" && <span className="chip bg-pitch/20 text-pitch">final</span>}
        </div>
      )}

      {/* Controles de registro */}
      {editable && m.home_team && m.away_team && (
        <div className="mt-2 flex items-center gap-2">
          <input
            className="input w-12 text-center"
            value={home}
            inputMode="numeric"
            onChange={(e) => setHome(e.target.value)}
          />
          <span className="text-slate-500 text-xs">-</span>
          <input
            className="input w-12 text-center"
            value={away}
            inputMode="numeric"
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

      {m.status === "finished" && m.winner_team_id && m.home_score === m.away_score && (
        <div className="mt-1 text-xs text-slate-400">
          Penaltis: avanza{" "}
          {m.winner_team_id === m.home_team?.id ? m.home_team?.display_name : m.away_team?.display_name}
        </div>
      )}

      {save.isError && <div className="mt-1 text-xs text-rose-300">{apiErrorMessage(save.error)}</div>}
    </div>
  );
}
