import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import { formatDistanceToNow } from "date-fns";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function timeAgo(date: string | null | undefined): string {
  if (!date) return "Never";
  try {
    return formatDistanceToNow(new Date(date), { addSuffix: true });
  } catch {
    return "Unknown";
  }
}

export function numberFormat(value: number | null | undefined): string {
  return new Intl.NumberFormat("en-US").format(value ?? 0);
}

export function shortText(value: unknown, fallback = "-"): string {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text || fallback;
}

export type HardeningStatus = "hardened" | "partial" | "none" | "error" | null | string;

const statusToneMap: Record<string, string> = {
  active: "border-emerald-200 bg-emerald-50 text-emerald-700",
  completed: "border-emerald-200 bg-emerald-50 text-emerald-700",
  confirmed: "border-emerald-200 bg-emerald-50 text-emerald-700",
  healthy: "border-emerald-200 bg-emerald-50 text-emerald-700",
  ok: "border-emerald-200 bg-emerald-50 text-emerald-700",
  online: "border-emerald-200 bg-emerald-50 text-emerald-700",
  pass: "border-emerald-200 bg-emerald-50 text-emerald-700",
  passed: "border-emerald-200 bg-emerald-50 text-emerald-700",
  success: "border-emerald-200 bg-emerald-50 text-emerald-700",

  running: "border-blue-200 bg-blue-50 text-blue-700",
  info: "border-blue-200 bg-blue-50 text-blue-700",
  informational: "border-blue-200 bg-blue-50 text-blue-700",

  high: "border-orange-200 bg-orange-50 text-orange-700",

  medium: "border-amber-200 bg-amber-50 text-amber-700",
  partial: "border-amber-200 bg-amber-50 text-amber-700",
  pending: "border-amber-200 bg-amber-50 text-amber-700",
  queued: "border-amber-200 bg-amber-50 text-amber-700",
  warn: "border-amber-200 bg-amber-50 text-amber-700",
  warning: "border-amber-200 bg-amber-50 text-amber-700",

  critical: "border-red-200 bg-red-50 text-red-700",
  down: "border-red-200 bg-red-50 text-red-700",
  error: "border-red-200 bg-red-50 text-red-700",
  fail: "border-red-200 bg-red-50 text-red-700",
  failed: "border-red-200 bg-red-50 text-red-700",
  none: "border-red-200 bg-red-50 text-red-700",
  offline: "border-red-200 bg-red-50 text-red-700",
  unreachable: "border-red-200 bg-red-50 text-red-700",

  low: "border-cyan-200 bg-cyan-50 text-cyan-700",
  unknown: "border-slate-200 bg-slate-50 text-slate-700",
  unchecked: "border-slate-200 bg-slate-50 text-slate-700"
};

export function statusToneClass(value: unknown): string {
  const normalized = shortText(value, "unknown").toLowerCase().replace(/[\s_]+/g, "-");
  return statusToneMap[normalized] ?? statusToneMap.unknown;
}

export function statusBadgeClass(value: unknown): string {
  return cn("rounded-full border px-2 py-1 text-center text-xs font-medium", statusToneClass(value));
}

export function osTypeLabel(osType: string | null | undefined): string {
  switch (osType) {
    case "ubuntu":
      return "Ubuntu 24.04";
    case "windows":
      return "Windows Server 2022";
    case "junos":
      return "Juniper Junos Switch";
    default:
      return osType || "Unknown OS";
  }
}
