"use client";

import { useCallback, useEffect, useState } from "react";
import { Radar, ShieldAlert } from "lucide-react";
import { api } from "@/lib/api";
import { MetricCard } from "@/components/metric-card";
import { JsonBlock } from "@/components/json-block";
import { cn, shortText, statusBadgeClass } from "@/lib/utils";

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : [];
}

function fold(value: unknown) {
  return shortText(value, "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function relationChipClass(value: unknown) {
  const key = fold(value);
  if (key.includes("direct") || key.includes("truc tiep")) return "border-red-200 bg-red-50 text-red-700 ring-1 ring-red-100";
  if (key.includes("co kha nang") || key.includes("likely") || key.includes("possible") || key.includes("lien quan")) {
    return "border-amber-300 bg-amber-50 text-amber-800 ring-1 ring-amber-100";
  }
  if (key.includes("context") || key.includes("ngu canh") || key.includes("correlat")) {
    return "border-sky-200 bg-sky-50 text-sky-700 ring-1 ring-sky-100";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function riskChipClass(value: unknown) {
  const key = fold(value);
  if (key.includes("critical")) return "border-red-200 bg-red-50 text-red-700 ring-1 ring-red-100";
  if (key.includes("high")) return "border-orange-200 bg-orange-50 text-orange-700 ring-1 ring-orange-100";
  if (key.includes("medium")) return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-blue-200 bg-blue-50 text-blue-700";
}

function radarChipClass(type: "relation" | "risk" | "epss", value: unknown) {
  if (type === "relation") return relationChipClass(value);
  if (type === "risk") return riskChipClass(value);
  return "border-teal-200 bg-teal-50 text-teal-700";
}

function RadarChip({ type, label, value }: { type: "relation" | "risk" | "epss"; label: string; value: unknown }) {
  return (
    <span className={cn("rounded-full border px-2.5 py-1 text-xs font-semibold", radarChipClass(type, value))}>
      <span className="font-medium opacity-75">{label}: </span>
      {shortText(value)}
    </span>
  );
}

export default function SecurityRadarPage() {
  const [data, setData] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setData(await api.securityEmerging(12, 14).catch((error) => ({ error: String(error) })));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const items = asArray(data.items);
  const direct = items.filter((item) => item.relation === "direct").length;
  const kev = items.filter((item) => Boolean(item.known_exploited)).length;

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Security</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Emerging CVE radar</h1>
          <p className="mt-1 text-sm text-muted-foreground">Recent CVEs correlated with local vulnerability inventory when available.</p>
        </div>
        <button onClick={load} className="inline-flex h-10 items-center justify-center rounded-lg border border-border px-4 text-sm font-medium hover:bg-secondary">
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard label="Radar Items" value={items.length} sub={`${shortText(data.days, "14")} day window`} icon={Radar} tone="blue" />
        <MetricCard label="Direct Matches" value={direct} sub="Seen in current Wazuh scan" icon={ShieldAlert} tone={direct > 0 ? "red" : "emerald"} />
        <MetricCard label="Known Exploited" value={kev} sub="CISA KEV flagged" icon={ShieldAlert} tone={kev > 0 ? "red" : "slate"} />
      </div>

      <section className="grid gap-4 xl:grid-cols-2">
        {items.map((item, index) => (
          <div key={`${shortText(item.cve)}-${index}`} className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="font-mono text-sm font-semibold text-primary">{shortText(item.cve)}</p>
                <p className="mt-1 text-sm font-medium">{shortText(item.title, "Untitled vulnerability")}</p>
              </div>
              <span className={statusBadgeClass(item.severity)}>
                {shortText(item.severity)}
              </span>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-700">{shortText(item.analysis ?? item.recommendation ?? item.description)}</p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs">
              <RadarChip type="relation" label="relation" value={item.relation_label ?? item.relation} />
              <RadarChip type="risk" label="risk" value={item.risk_label ?? item.risk_score} />
              <RadarChip type="epss" label="epss" value={item.epss} />
            </div>
          </div>
        ))}
      </section>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold">Raw CVE radar payload</h2>
        <JsonBlock value={data} />
      </section>
    </div>
  );
}
