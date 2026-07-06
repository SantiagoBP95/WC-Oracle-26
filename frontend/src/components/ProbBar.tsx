export default function ProbBar({
  value,
  color = "bg-pitch",
  label,
}: {
  value: number;
  color?: string;
  label?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-700/70">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${Math.min(100, Math.max(0, value * 100))}%` }}
        />
      </div>
      {label !== undefined && (
        <span className="w-12 text-right text-xs font-semibold tabular-nums text-white">
          {label}
        </span>
      )}
    </div>
  );
}
