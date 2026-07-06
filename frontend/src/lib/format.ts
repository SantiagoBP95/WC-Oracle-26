export const pct = (x: number, digits = 1): string => `${(x * 100).toFixed(digits)}%`;

export const CONF_COLORS: Record<string, string> = {
  UEFA: "bg-sky-500/20 text-sky-300",
  CONMEBOL: "bg-amber-500/20 text-amber-300",
  CONCACAF: "bg-rose-500/20 text-rose-300",
  CAF: "bg-emerald-500/20 text-emerald-300",
  AFC: "bg-violet-500/20 text-violet-300",
  OFC: "bg-teal-500/20 text-teal-300",
};

export function confChip(conf: string): string {
  return CONF_COLORS[conf] ?? "bg-slate-500/20 text-slate-300";
}
