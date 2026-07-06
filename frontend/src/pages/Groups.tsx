import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { api } from "../api/client";
import type { Simulation, TeamProb } from "../api/types";
import ProbBar from "../components/ProbBar";
import { pct } from "../lib/format";
import { useModel } from "../model/ModelContext";

const LABELS = "ABCDEFGHIJKL".split("");

export default function Groups() {
  const { model } = useModel();
  const { data, isLoading } = useQuery({
    queryKey: ["sim-latest", model],
    queryFn: async () =>
      (await api.get<Simulation>("/simulations/latest", { params: { model } })).data,
  });

  if (isLoading || !data) return <p className="text-slate-400">Cargando…</p>;

  const byGroup: Record<string, TeamProb[]> = {};
  for (const p of data.probs) {
    if (!p.group_label) continue;
    (byGroup[p.group_label] ??= []).push(p);
  }
  for (const g of Object.keys(byGroup)) {
    byGroup[g].sort((a, b) => b.p_advance - a.p_advance);
  }

  // Los 8 mejores terceros: tomar el equipo en posición 2 (índice 2) de cada grupo,
  // ordenarlos por p_advance y quedarse con los 8 con mayor probabilidad.
  const thirdPlaced = LABELS
    .map((g) => byGroup[g]?.[2])
    .filter(Boolean) as TeamProb[];
  const top8ThirdSet = new Set(
    [...thirdPlaced].sort((a, b) => b.p_advance - a.p_advance).slice(0, 8).map((t) => t.team)
  );

  function barColor(i: number, team: string): string {
    if (i <= 1) return "bg-pitch";                        // 1° y 2° → verde
    if (i === 2 && top8ThirdSet.has(team)) return "bg-amber-500"; // mejor 3° → ámbar
    return "bg-slate-500";                                // eliminado → gris
  }

  function posLabel(i: number, team: string): ReactNode {
    if (i <= 1) return null;
    if (i === 2 && top8ThirdSet.has(team))
      return <span className="ml-1 text-[10px] text-amber-400">mejor 3°</span>;
    return null;
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Grupos</h1>
      <p className="text-sm text-slate-400">
        Probabilidad de clasificar a la Ronda de 32 · <span className="text-pitch">verde</span> = clasifica directo ·{" "}
        <span className="text-amber-400">ámbar</span> = mejor 3° (top 8 de 12)
      </p>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {LABELS.map((g) => (
          <div key={g} className="card p-4">
            <div className="mb-3 flex items-center gap-2">
              <span className="grid h-7 w-7 place-items-center rounded-md bg-pitch/20 text-sm font-bold text-pitch">
                {g}
              </span>
              <span className="text-sm font-semibold text-slate-300">Grupo {g}</span>
            </div>
            <div className="space-y-3">
              {(byGroup[g] ?? []).map((p, i) => (
                <div key={p.team}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="font-medium">
                      <span className="mr-1 text-xs text-slate-500">{i + 1}.</span>
                      {p.display_name}
                      {posLabel(i, p.team)}
                    </span>
                    <span className="text-xs text-slate-400">{pct(p.p_advance, 0)}</span>
                  </div>
                  <ProbBar value={p.p_advance} color={barColor(i, p.team)} />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
