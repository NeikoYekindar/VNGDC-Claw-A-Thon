"use client";

import { cn } from "@/lib/utils";
import type { HardeningStatus } from "@/lib/utils";

interface Props {
  status: HardeningStatus;
  size?: "sm" | "md";
}

const cfg: Record<string, { dot: string; badge: string; label: string }> = {
  hardened: { dot: "bg-emerald-500", badge: "border-emerald-200 bg-emerald-50 text-emerald-700", label: "Hardened" },
  partial: { dot: "bg-amber-500", badge: "border-amber-200 bg-amber-50 text-amber-700", label: "Partial" },
  none: { dot: "bg-red-500", badge: "border-red-200 bg-red-50 text-red-700", label: "Not Hardened" },
  error: { dot: "bg-red-600", badge: "border-red-200 bg-red-50 text-red-700", label: "Error" },
  default: { dot: "bg-slate-400", badge: "border-slate-200 bg-slate-50 text-slate-600", label: "Unchecked" },
};

export function StatusBadge({ status, size = "md" }: Props) {
  const c = cfg[status ?? "default"] ?? cfg.default;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs",
        c.badge,
      )}
    >
      <span className={cn("shrink-0 rounded-full", size === "sm" ? "h-1.5 w-1.5" : "h-2 w-2", c.dot)} />
      {c.label}
    </span>
  );
}

export function CheckLevelIcon({ level }: { level: string }) {
  switch (level) {
    case "pass":
      return (
        <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
        </svg>
      );
    case "fail":
      return (
        <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M6 18L18 6M6 6l12 12" />
        </svg>
      );
    case "warn":
      return (
        <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 8v5m0 4h.01" />
        </svg>
      );
    default:
      return (
        <svg className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M12 8h.01M11 12h1v4h1" />
        </svg>
      );
  }
}
