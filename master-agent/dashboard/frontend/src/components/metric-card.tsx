import type { LucideIcon } from "lucide-react";
import { cn, numberFormat } from "@/lib/utils";

export function MetricCard({
  label,
  value,
  sub,
  icon: Icon,
  tone = "blue"
}: {
  label: string;
  value: number | string;
  sub?: string;
  icon?: LucideIcon;
  tone?: "blue" | "teal" | "red" | "amber" | "emerald" | "slate";
}) {
  const tones = {
    blue: "border-blue-200 bg-blue-50 text-blue-700",
    teal: "border-teal-200 bg-teal-50 text-teal-700",
    red: "border-red-200 bg-red-50 text-red-700",
    amber: "border-amber-200 bg-amber-50 text-amber-700",
    emerald: "border-emerald-200 bg-emerald-50 text-emerald-700",
    slate: "border-slate-200 bg-slate-50 text-slate-700"
  };
  const accentLines = {
    blue: "bg-sky-300",
    teal: "bg-cyan-300",
    red: "bg-red-400",
    amber: "bg-amber-400",
    emerald: "bg-emerald-300",
    slate: "bg-sky-200"
  };

  const display = typeof value === "number" ? numberFormat(value) : value;

  return (
    <div className="relative overflow-hidden rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className={cn("absolute bottom-4 left-0 top-4 w-1 rounded-r-full", accentLines[tone])} />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="mt-2 text-2xl font-semibold tabular-nums tracking-tight">{display}</p>
          {sub ? <p className="mt-1 text-xs text-muted-foreground">{sub}</p> : null}
        </div>
        {Icon ? (
          <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border", tones[tone])}>
            <Icon className="h-4 w-4" />
          </div>
        ) : null}
      </div>
    </div>
  );
}
