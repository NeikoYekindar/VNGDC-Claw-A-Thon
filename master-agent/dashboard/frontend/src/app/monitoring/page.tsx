"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowRight, BellRing, BookOpen, Boxes, Gauge, Server, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { MetricCard } from "@/components/metric-card";
import { JsonBlock } from "@/components/json-block";
import { StatusPill } from "@/components/status-pill";
import { shortText, statusBadgeClass } from "@/lib/utils";

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : [];
}

export default function MonitoringPage() {
  const [status, setStatus] = useState<boolean | null>(null);
  const [inventory, setInventory] = useState<Record<string, unknown>>({});
  const [batches, setBatches] = useState<Record<string, unknown>>({});
  const [suppressions, setSuppressions] = useState<Record<string, unknown>>({});
  const [knowledge, setKnowledge] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [agents, inv, batchRows, suppressionRows, knowledgeRows] = await Promise.all([
        api.agentsStatus(),
        api.monitoringInventory().catch((error) => ({ error: String(error) })),
        api.monitoringBatches().catch((error) => ({ error: String(error) })),
        api.monitoringSuppressions().catch((error) => ({ error: String(error) })),
        api.monitoringKnowledge().catch((error) => ({ error: String(error) }))
      ]);
      setStatus(Boolean(agents.find((agent) => agent.key === "monitoring")?.connected));
      setInventory(inv);
      setBatches(batchRows);
      setSuppressions(suppressionRows);
      setKnowledge(knowledgeRows);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 30_000);
    return () => clearInterval(iv);
  }, [refresh]);

  const inventoryRows = asArray(inventory.inventory);
  const batchRows = asArray(batches.batches);
  const suppressionRows = asArray(suppressions.suppressions);
  const knowledgeRows = asArray(knowledge.files);

  const byType = useMemo(() => {
    const servers = inventoryRows.filter((row) => row.type !== "network").length;
    const network = inventoryRows.filter((row) => row.type === "network").length;
    return { servers, network };
  }, [inventoryRows]);

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
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Monitoring</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Monitoring command center</h1>
          <p className="mt-1 text-sm text-muted-foreground">Runtime health, server inventory, alert batches, and maintenance windows.</p>
        </div>
        <StatusPill connected={status} />
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Inventory" value={inventoryRows.length} sub="Total monitored assets" icon={Server} tone="blue" />
        <MetricCard label="Servers" value={byType.servers} sub="Compute targets" icon={Gauge} tone="emerald" />
        <MetricCard label="Network" value={byType.network} sub="Network devices" icon={Boxes} tone="teal" />
        <MetricCard label="Active suppressions" value={suppressionRows.length} sub="Maintenance windows" icon={Wrench} tone="amber" />
        <MetricCard label="Knowledge" value={knowledgeRows.length} sub="RCA runbooks" icon={BookOpen} tone="blue" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(360px,0.9fr)]">
        <section className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h2 className="text-sm font-semibold">Alert RCA batches</h2>
            <Link href="/monitoring/alerts" className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
              Open RCA
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="divide-y divide-border">
            {batchRows.slice(0, 8).map((row, index) => (
              <div key={shortText(row.batch_id, String(index))} className="grid gap-3 px-5 py-3.5 sm:grid-cols-[minmax(0,1fr)_100px_130px] sm:items-center">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{shortText(row.batch_id, "Batch")}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{shortText(row.created_at, "No timestamp")}</p>
                </div>
                <span className="text-xs text-muted-foreground">{shortText(row.alert_count, "0")} alerts</span>
                <span className={statusBadgeClass(row.status)}>
                  {shortText(row.status, "unknown")}
                </span>
              </div>
            ))}
            {batchRows.length === 0 ? (
              <div className="px-5 py-12 text-center text-sm text-muted-foreground">No alert batches returned by the monitoring agent.</div>
            ) : null}
          </div>
        </section>

        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Quick actions</h2>
            <BellRing className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="grid gap-3">
            <Link href="/monitoring/alerts" className="rounded-lg border border-border bg-slate-50 p-4 transition-colors hover:border-orange-200 hover:bg-orange-50/60">
              <p className="text-sm font-semibold">Generate correlated alert scenario</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">Use the monitoring child agent to create and trigger a demo RCA batch.</p>
            </Link>
            <Link href="/monitoring/inventory" className="rounded-lg border border-border bg-slate-50 p-4 transition-colors hover:border-orange-200 hover:bg-orange-50/60">
              <p className="text-sm font-semibold">Review monitored assets</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">Inspect server and network inventory imported into the monitoring agent.</p>
            </Link>
            <Link href="/monitoring/maintenance" className="rounded-lg border border-border bg-slate-50 p-4 transition-colors hover:border-orange-200 hover:bg-orange-50/60">
              <p className="text-sm font-semibold">Maintenance windows</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">Suppress alert ingestion for servers under maintenance.</p>
            </Link>
            <Link href="/monitoring/knowledge" className="rounded-lg border border-border bg-slate-50 p-4 transition-colors hover:border-orange-200 hover:bg-orange-50/60">
              <p className="text-sm font-semibold">Knowledge base</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">Upload or remove Markdown runbooks used by RCA analysis.</p>
            </Link>
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold">Raw monitoring snapshot</h2>
        <JsonBlock value={{ inventory, batches, suppressions, knowledge }} />
      </section>
    </div>
  );
}
