"use client";

import { Check, Info, X, AlertTriangle } from "lucide-react";
import { cn, type HardeningStatus } from "@/lib/utils";

interface Props {
  status: HardeningStatus;
  size?: "sm" | "md";
}

const cfg: Record<string, { dot: string; badge: string; label: string }> = {
  hardened: { dot: "bg-emerald-500", badge: "border-emerald-200 bg-emerald-50 text-emerald-700", label: "Hardened" },
  active: { dot: "bg-emerald-500", badge: "border-emerald-200 bg-emerald-50 text-emerald-700", label: "Active" },
  completed: { dot: "bg-emerald-500", badge: "border-emerald-200 bg-emerald-50 text-emerald-700", label: "Completed" },
  partial: { dot: "bg-amber-500", badge: "border-amber-200 bg-amber-50 text-amber-700", label: "Partial" },
  pending: { dot: "bg-amber-500", badge: "border-amber-200 bg-amber-50 text-amber-700", label: "Pending" },
  running: { dot: "bg-blue-500", badge: "border-blue-200 bg-blue-50 text-blue-700", label: "Running" },
  none: { dot: "bg-red-500", badge: "border-red-200 bg-red-50 text-red-700", label: "Not Hardened" },
  critical: { dot: "bg-red-600", badge: "border-red-200 bg-red-50 text-red-700", label: "Critical" },
  high: { dot: "bg-orange-500", badge: "border-orange-200 bg-orange-50 text-orange-700", label: "High" },
  medium: { dot: "bg-amber-500", badge: "border-amber-200 bg-amber-50 text-amber-700", label: "Medium" },
  low: { dot: "bg-cyan-500", badge: "border-cyan-200 bg-cyan-50 text-cyan-700", label: "Low" },
  error: { dot: "bg-red-600", badge: "border-red-200 bg-red-50 text-red-700", label: "Error" },
  pass: { dot: "bg-emerald-500", badge: "border-emerald-200 bg-emerald-50 text-emerald-700", label: "Passed" },
  fail: { dot: "bg-red-500", badge: "border-red-200 bg-red-50 text-red-700", label: "Failed" },
  failed: { dot: "bg-red-500", badge: "border-red-200 bg-red-50 text-red-700", label: "Failed" },
  warn: { dot: "bg-amber-500", badge: "border-amber-200 bg-amber-50 text-amber-700", label: "Warning" },
  info: { dot: "bg-blue-500", badge: "border-blue-200 bg-blue-50 text-blue-700", label: "Info" },
  default: { dot: "bg-slate-400", badge: "border-slate-200 bg-slate-50 text-slate-600", label: "Unchecked" }
};

export function StatusBadge({ status, size = "md" }: Props) {
  const c = cfg[String(status ?? "default")] ?? cfg.default;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs",
        c.badge
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
      return <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />;
    case "fail":
      return <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-600" />;
    case "warn":
      return <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />;
    default:
      return <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-500" />;
  }
}
