import { cn } from "@/lib/utils";

export function StatusPill({
  connected,
  label,
  compact = false
}: {
  connected: boolean | null | undefined;
  label?: string;
  compact?: boolean;
}) {
  const tone =
    connected === undefined || connected === null
      ? "border-slate-200 bg-slate-50 text-slate-600"
      : connected
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : "border-red-200 bg-red-50 text-red-700";
  const dot =
    connected === undefined || connected === null
      ? "bg-slate-300"
      : connected
        ? "bg-emerald-500"
        : "bg-red-500";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border font-medium",
        compact ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs",
        tone
      )}
    >
      <span className={cn("h-2 w-2 rounded-full", dot)} />
      {label ?? (connected ? "Active" : connected === false ? "Offline" : "Checking")}
    </span>
  );
}
