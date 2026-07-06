import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import { api } from "../api/client";
import type { BetMarket, Match, MatchMarkets } from "../api/types";
import { pct } from "../lib/format";

// ── tipos extendidos ──────────────────────────────────────────────────────────
interface PlayerLine { line: number; prob: number; odds: number }
interface PlayerMarket extends BetMarket {
  player: string;
  sot_per_90: number;
  source: string;
  lines: PlayerLine[];
}

// ── fetch ─────────────────────────────────────────────────────────────────────
async function fetchMatches(): Promise<Match[]> {
  const { data } = await api.get<Match[]>("/matches");
  return data;
}
async function fetchMarkets(matchId: number): Promise<MatchMarkets> {
  const { data } = await api.get<MatchMarkets>(`/bets/matches/${matchId}`);
  return data;
}

// ── helpers de formato ────────────────────────────────────────────────────────
const DIAS_ES  = ["dom","lun","mar","mié","jue","vie","sáb"];
const MESES_ES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];

function toUTC(iso: string): Date {
  // El backend serializa datetimes UTC sin sufijo Z; forzamos interpretación UTC.
  return new Date(/[Z+]/.test(iso) ? iso : iso + "Z");
}

function fmtFecha(iso: string | null): string {
  if (!iso) return "";
  const d = toUTC(iso);
  const dia  = DIAS_ES[d.getDay()];
  const num  = d.getDate();
  const mes  = MESES_ES[d.getMonth()];
  const h    = d.getHours().toString().padStart(2,"0");
  const min  = d.getMinutes().toString().padStart(2,"0");
  return `${dia} ${num} ${mes}  ${h}:${min}`;
}

function fmtEtapa(m: Match): string {
  if (m.stage === "group") return m.group_label ? `Grupo ${m.group_label}` : "Grupos";
  const MAP: Record<string,string> = {
    R32: "Ronda de 32", R16: "Octavos", QF: "Cuartos", SF: "Semifinal", Final: "Final",
  };
  return MAP[m.stage] ?? m.stage;
}

// ── barra de probabilidad ─────────────────────────────────────────────────────
function ProbBar({ p }: { p: number }) {
  const color = p >= 0.65 ? "bg-pitch" : p >= 0.45 ? "bg-amber-500" : "bg-slate-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 rounded-full bg-slate-700">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.round(p*100)}%` }} />
      </div>
      <span className="tabular-nums text-xs text-slate-300">{Math.round(p*100)}%</span>
    </div>
  );
}

// ── checkbox visual ───────────────────────────────────────────────────────────
function Checkbox({ checked }: { checked: boolean }) {
  return (
    <div className={`mx-auto h-4 w-4 rounded border transition flex items-center justify-center ${
      checked ? "border-pitch bg-pitch" : "border-slate-600"
    }`}>
      {checked && (
        <svg viewBox="0 0 10 8" className="h-3 w-3 text-ink" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M1 4l3 3 5-6" />
        </svg>
      )}
    </div>
  );
}

// ── vista especial para tiros a puerta por jugador ────────────────────────────
function PlayerSOTView({
  markets,
  selected,
  toggle,
}: {
  markets: PlayerMarket[];
  selected: Map<string, BetMarket>;
  toggle: (m: BetMarket) => void;
}) {
  return (
    <div className="space-y-3">
      {markets.map((pm) => (
        <div key={pm.id} className="card overflow-hidden">
          {/* Cabecera jugador */}
          <div className="flex items-center justify-between border-b border-line bg-panel2/40 px-4 py-2.5">
            <div>
              <span className="font-semibold text-sm">{pm.player}</span>
              <span className="ml-2 text-[10px] text-slate-500">{pm.source}</span>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-400">T.a.P./90 histórico</span>
              <span className="ml-2 font-bold text-pitch">{pm.sot_per_90}</span>
            </div>
          </div>

          {/* Líneas escalonadas */}
          <div className="grid grid-cols-3 divide-x divide-line/40">
            {pm.lines.map((ln) => {
              const marketId = `${pm.id}_over_${ln.line}`;
              const market: BetMarket = {
                id: marketId,
                category: pm.category,
                label: `${pm.player}: más de ${ln.line} tiros a puerta`,
                prob: ln.prob,
                odds: ln.odds,
              };
              const isSelected = selected.has(marketId);
              return (
                <button
                  key={ln.line}
                  onClick={() => toggle(market)}
                  className={`flex flex-col items-center gap-1 px-3 py-3 transition hover:bg-panel2/60 ${
                    isSelected ? "bg-pitch/10" : ""
                  }`}
                >
                  <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
                    Más de {ln.line}
                  </span>
                  <span className={`text-lg font-bold tabular-nums ${
                    ln.prob >= 0.65 ? "text-pitch" : ln.prob >= 0.45 ? "text-amber-400" : "text-slate-300"
                  }`}>
                    {Math.round(ln.prob * 100)}%
                  </span>
                  <span className="text-xs font-semibold text-amber-300 tabular-nums">
                    {ln.odds.toFixed(2)}
                  </span>
                  <Checkbox checked={isSelected} />
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── detección de conflictos entre selecciones ────────────────────────────────
interface ParsedId {
  stat: string;
  dir: "over" | "under" | "outcome";
  line: number | null;
}

function parseId(id: string): ParsedId | null {
  const m = id.match(/^(.+)_(over|under)_([\d.]+)$/);
  if (m) return { stat: m[1], dir: m[2] as "over" | "under", line: parseFloat(m[3]) };
  if (id === "1x2_home" || id === "1x2_draw" || id === "1x2_away")
    return { stat: "1x2", dir: "outcome", line: null };
  if (id === "btts_yes" || id === "btts_no")
    return { stat: "btts", dir: "outcome", line: null };
  return null;
}

interface Conflict { type: "contained" | "exclusive"; labels: [string, string] }

function detectConflicts(markets: BetMarket[]): Conflict[] {
  const conflicts: Conflict[] = [];
  const items = markets.map(m => ({ m, p: parseId(m.id) })).filter(x => x.p);
  for (let i = 0; i < items.length; i++) {
    for (let j = i + 1; j < items.length; j++) {
      const a = items[i], b = items[j];
      if (!a.p || !b.p || a.p.stat !== b.p.stat) continue;
      const labels: [string, string] = [a.m.label, b.m.label];
      if (a.p.dir === "outcome" && b.p.dir === "outcome") {
        conflicts.push({ type: "exclusive", labels });
      } else if (a.p.dir === b.p.dir && a.p.dir !== "outcome" && a.p.line !== b.p.line) {
        conflicts.push({ type: "contained", labels });
      } else if (a.p.dir !== b.p.dir && a.p.dir !== "outcome" && b.p.dir !== "outcome") {
        const overLine = a.p.dir === "over" ? a.p.line! : b.p.line!;
        const underLine = a.p.dir === "under" ? a.p.line! : b.p.line!;
        if (overLine >= underLine) conflicts.push({ type: "exclusive", labels });
      }
    }
  }
  return conflicts;
}

// ── categorías estáticas en orden ─────────────────────────────────────────────
const STATIC_CATEGORIES = [
  "Resultado",
  "Goles",
  "Goles local",
  "Goles visitante",
  "Córners",
  "Tarjetas",
  "Disparos",
  "Disparos a puerta",
  "Tiros a puerta local",
  "Tiros a puerta visitante",
];

const isPlayerCat = (cat: string) => cat.startsWith("Tiros a puerta ·");

// ── componente principal ──────────────────────────────────────────────────────
export default function BetBuilder() {
  const [matchId, setMatchId]     = useState<number | null>(null);
  const [selected, setSelected]   = useState<Map<string, BetMarket>>(new Map());
  const [activeCat, setActiveCat] = useState<string>("Resultado");

  const { data: matches, isLoading: loadingMatches } = useQuery({
    queryKey: ["matches"],
    queryFn: fetchMatches,
  });

  const { data: markets, isLoading: loadingMarkets } = useQuery({
    queryKey: ["bet-markets", matchId],
    queryFn: () => fetchMarkets(matchId!),
    enabled: matchId !== null,
  });

  const selectedList = useMemo(() => Array.from(selected.values()), [selected]);
  const combinedProb = useMemo(
    () => selectedList.length ? selectedList.reduce((acc, m) => acc * m.prob, 1) : null,
    [selectedList]
  );
  const conflicts = useMemo(() => detectConflicts(selectedList), [selectedList]);

  function toggle(market: BetMarket) {
    setSelected(prev => {
      const next = new Map(prev);
      next.has(market.id) ? next.delete(market.id) : next.set(market.id, market);
      return next;
    });
  }

  function onMatchChange(id: number) {
    setMatchId(id);
    setSelected(new Map());
    setActiveCat("Resultado");
  }

  // Agrupar partidos por fecha para el selector
  const playableMatches = useMemo(
    () => (matches ?? []).filter(m => m.prediction).sort((a,b) =>
      (a.scheduled_at ?? "").localeCompare(b.scheduled_at ?? "")
    ),
    [matches]
  );

  const byCategory = useMemo(() => {
    if (!markets) return {} as Record<string, BetMarket[]>;
    const map: Record<string, BetMarket[]> = {};
    for (const m of markets.markets) (map[m.category] ??= []).push(m);
    return map;
  }, [markets]);

  const dynamicCategories = Object.keys(byCategory).filter(c => !STATIC_CATEGORIES.includes(c));
  const presentCategories = [
    ...STATIC_CATEGORIES.filter(c => byCategory[c]?.length),
    ...dynamicCategories,
  ];

  const activeMarkets = byCategory[activeCat] ?? [];
  const isPlayerView  = isPlayerCat(activeCat);

  // Selecciones en categoría activa (para badge del tab)
  function countSelected(cat: string): number {
    if (isPlayerCat(cat)) {
      return (byCategory[cat] ?? []).filter(pm =>
        (pm as PlayerMarket).lines?.some(ln => selected.has(`${pm.id}_over_${ln.line}`))
      ).length;
    }
    return (byCategory[cat] ?? []).filter(m => selected.has(m.id)).length;
  }

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Constructor de apuestas</h1>
        <p className="text-sm text-slate-400">
          Selecciona mercados de un partido para construir una apuesta combinada.
        </p>
      </div>

      {/* ── Selector de partido ── */}
      <div className="card p-4">
        <label className="block text-xs font-semibold uppercase tracking-wide text-slate-400 mb-2">
          Partido
        </label>
        {loadingMatches ? (
          <p className="text-slate-400 text-sm">Cargando…</p>
        ) : (
          <select
            className="input w-full max-w-lg"
            value={matchId ?? ""}
            onChange={e => onMatchChange(Number(e.target.value))}
          >
            <option value="">— elige un partido —</option>
            {playableMatches.map(m => (
              <option key={m.id} value={m.id}>
                {fmtFecha(m.scheduled_at)}{"  "}
                {m.home_team?.display_name ?? "?"} vs {m.away_team?.display_name ?? "?"}
                {"  "}· {fmtEtapa(m)}
                {m.status === "finished" ? "  ✓" : ""}
              </option>
            ))}
          </select>
        )}
      </div>

      {matchId && (
        <>
          {loadingMarkets ? (
            <p className="text-slate-400">Calculando mercados…</p>
          ) : markets ? (
            <div className="grid gap-5 lg:grid-cols-[1fr_320px]">

              {/* ── Panel de mercados ── */}
              <div className="space-y-4">

                {/* Resumen del partido */}
                <div className="card p-4 space-y-1 text-sm">
                  <div className="font-semibold">
                    {markets.home}
                    <span className="mx-2 text-slate-500 font-normal">vs</span>
                    {markets.away}
                    {markets.status === "finished" && (
                      <span className="ml-2 text-[10px] text-pitch border border-pitch/40 rounded px-1 py-0.5">Finalizado</span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-4 text-xs text-slate-400">
                    <span>Goles esperados <b className="text-white">{markets.exp_goals_home} – {markets.exp_goals_away}</b></span>
                    <span>Total <b className="text-white">{(markets.exp_goals_home + markets.exp_goals_away).toFixed(2)}</b></span>
                    <span>
                      Tiros a puerta esp.{" "}
                      <b className="text-white">
                        {(markets.exp_goals_home / 0.30).toFixed(1)} – {(markets.exp_goals_away / 0.30).toFixed(1)}
                      </b>
                      <span className="text-slate-600 ml-1">(conv. 30 %)</span>
                    </span>
                  </div>
                </div>

                {/* Tabs de categoría */}
                <div className="flex flex-wrap gap-1.5">
                  {presentCategories.map(cat => {
                    const n = countSelected(cat);
                    return (
                      <button
                        key={cat}
                        onClick={() => setActiveCat(cat)}
                        className={activeCat === cat ? "btn-primary px-3 py-1.5 text-xs" : "btn-ghost px-3 py-1.5 text-xs"}
                      >
                        {cat}
                        {n > 0 && (
                          <span className="ml-1.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-pitch text-[10px] text-ink font-bold">
                            {n}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>

                {/* Vista de jugadores o tabla estándar */}
                {isPlayerView ? (
                  <PlayerSOTView
                    markets={activeMarkets as PlayerMarket[]}
                    selected={selected}
                    toggle={toggle}
                  />
                ) : (
                  <div className="card overflow-hidden">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-line bg-panel2/50">
                          <th className="w-8 px-4 py-2" />
                          <th className="px-4 py-2 text-left text-xs font-semibold text-slate-400">Mercado</th>
                          <th className="px-4 py-2 text-left text-xs font-semibold text-slate-400">Probabilidad</th>
                          <th className="px-4 py-2 text-right text-xs font-semibold text-slate-400">Cuota</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-line/40">
                        {activeMarkets.map(market => {
                          const isSelected = selected.has(market.id);
                          return (
                            <tr
                              key={market.id}
                              onClick={() => toggle(market)}
                              className={`cursor-pointer transition hover:bg-panel2/60 ${isSelected ? "bg-pitch/10" : ""}`}
                            >
                              <td className="px-4 py-2.5 text-center">
                                <Checkbox checked={isSelected} />
                              </td>
                              <td className="px-4 py-2.5 font-medium">{market.label}</td>
                              <td className="px-4 py-2.5"><ProbBar p={market.prob} /></td>
                              <td className="px-4 py-2.5 text-right tabular-nums font-semibold text-amber-300">
                                {market.odds.toFixed(2)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              {/* ── Panel combinado ── */}
              <div className="space-y-4">
                <div className="card p-4 lg:sticky lg:top-6">
                  <div className="mb-3 flex items-center justify-between">
                    <h2 className="font-semibold text-sm">Apuesta combinada</h2>
                    {selected.size > 0 && (
                      <button className="text-xs text-slate-500 hover:text-rose-400" onClick={() => setSelected(new Map())}>
                        Limpiar
                      </button>
                    )}
                  </div>

                  {selectedList.length === 0 ? (
                    <p className="text-slate-500 text-xs">
                      Selecciona mercados de la tabla o las tarjetas de jugadores para armar tu combinada.
                    </p>
                  ) : (
                    <>
                      <ul className="space-y-2 mb-4">
                        {selectedList.map(m => (
                          <li key={m.id} className="flex items-start justify-between gap-2 rounded-lg border border-line bg-ink/30 px-3 py-2 text-xs">
                            <div>
                              <div className="font-medium text-slate-200">{m.label}</div>
                              <div className="text-slate-500">{m.category}</div>
                            </div>
                            <div className="flex items-center gap-2 shrink-0">
                              <span className="text-amber-300 font-semibold">{m.odds.toFixed(2)}</span>
                              <button onClick={e => { e.stopPropagation(); toggle(m); }} className="text-slate-600 hover:text-rose-400">✕</button>
                            </div>
                          </li>
                        ))}
                      </ul>

                      {conflicts.length > 0 && (
                        <div className="mb-3 rounded-lg border border-rose-700/40 bg-rose-900/15 px-3 py-2.5 text-[11px] text-rose-300 leading-snug space-y-1.5">
                          <div className="font-semibold text-rose-200">⚠️ Selecciones no independientes</div>
                          {conflicts.map((c, idx) => (
                            <div key={idx}>
                              {c.type === "exclusive" ? (
                                <>
                                  <span className="font-medium">Incompatibles:</span>{" "}
                                  <span className="text-slate-300">«{c.labels[0]}»</span> y{" "}
                                  <span className="text-slate-300">«{c.labels[1]}»</span>{" "}
                                  no pueden ocurrir simultáneamente. La cuota real es <b>0</b>.
                                </>
                              ) : (
                                <>
                                  <span className="font-medium">Contenidas:</span>{" "}
                                  <span className="text-slate-300">«{c.labels[0]}»</span> implica{" "}
                                  <span className="text-slate-300">«{c.labels[1]}»</span>{" "}
                                  (o viceversa) — no son independientes. La cuota está{" "}
                                  <b>subestimada</b>.
                                </>
                              )}
                            </div>
                          ))}
                        </div>
                      )}

                      {combinedProb !== null && (
                        <div className="rounded-xl border border-pitch/30 bg-pitch/10 p-4 text-center">
                          <div className="text-xs text-slate-400 mb-1">Probabilidad combinada</div>
                          <div className="text-3xl font-bold text-pitch">{pct(combinedProb, 1)}</div>
                          <div className="mt-1 text-xs text-slate-400">
                            Cuota equivalente{" "}
                            <span className="font-bold text-amber-300 text-base">{(1/combinedProb).toFixed(2)}</span>
                          </div>
                          <div className="mt-2 text-[10px] text-slate-600">
                            Asume selecciones independientes. Las correlaciones pueden variar.
                          </div>
                        </div>
                      )}

                      <div className="mt-3 rounded-lg bg-amber-900/20 border border-amber-700/30 p-3 text-[11px] text-amber-200/70 leading-snug">
                        ⚠️ Estimaciones del modelo Elo + Poisson. No representan consejo de apuesta. Juega con responsabilidad.
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </>
      )}

      {!matchId && (
        <div className="card p-8 text-center text-slate-500">
          <div className="text-4xl mb-2">🎯</div>
          <p>Selecciona un partido para ver los mercados disponibles.</p>
        </div>
      )}
    </div>
  );
}
