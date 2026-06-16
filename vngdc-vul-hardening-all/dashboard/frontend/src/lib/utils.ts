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

export type HardeningStatus = "hardened" | "partial" | "none" | "error" | null;

export function statusLabel(status: HardeningStatus): string {
  switch (status) {
    case "hardened": return "Hardened";
    case "partial":  return "Partial";
    case "none":     return "Not Hardened";
    case "error":    return "Error";
    default:         return "Unchecked";
  }
}

export function statusColor(status: HardeningStatus): string {
  switch (status) {
    case "hardened": return "text-emerald-700";
    case "partial":  return "text-amber-700";
    case "none":     return "text-red-700";
    case "error":    return "text-red-700";
    default:         return "text-slate-600";
  }
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
