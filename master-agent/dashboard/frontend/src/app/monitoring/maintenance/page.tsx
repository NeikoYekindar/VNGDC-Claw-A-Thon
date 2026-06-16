"use client";

import { useCallback, useEffect, useState } from "react";
import { Clock, Trash2, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { JsonBlock } from "@/components/json-block";
import { MetricCard } from "@/components/metric-card";
import { shortText } from "@/lib/utils";

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : [];
}

export default function MonitoringMaintenancePage() {
  const [data, setData] = useState<Record<string, unknown>>({});
  const [instance, setInstance] = useState("");
  const [hours, setHours] = useState(2);
  const [reason, setReason] = useState("Maintenance");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setData(await api.monitoringSuppressions());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const rows = asArray(data.suppressions);

  const createSuppression = async () => {
    if (!instance.trim() || busy) return;
    setBusy(true);
    try {
      const response = await api.monitoringCreateSuppression({
        instance: instance.trim(),
        hours,
        reason: reason.trim() || "Maintenance"
      });
      setResult(response);
      setInstance("");
      await refresh();
    } catch (error) {
      setResult({ status: "error", message: String(error) });
    } finally {
      setBusy(false);
    }
  };

  const removeSuppression = async (target: string) => {
    if (!target || busy) return;
    setBusy(true);
    try {
      const response = await api.monitoringRemoveSuppression(target);
      setResult(response);
      await refresh();
    } catch (error) {
      setResult({ status: "error", message: String(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Monitoring</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Maintenance windows</h1>
          <p className="mt-1 text-sm text-muted-foreground">Suppress alert ingestion for servers while maintenance is active.</p>
        </div>
        <button
          onClick={refresh}
          className="inline-flex h-10 items-center justify-center rounded-lg border border-border px-4 text-sm font-medium transition-colors hover:bg-secondary"
        >
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard label="Active windows" value={rows.length} sub="Current suppressions" icon={Wrench} tone="amber" />
        <MetricCard label="Window cap" value="168h" sub="Maximum allowed duration" icon={Clock} tone="blue" />
        <MetricCard label="Backend action" value="suppress" sub="ai-agent-monitoring" icon={Wrench} tone="teal" />
      </div>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="mb-4">
          <h2 className="text-sm font-semibold">Create maintenance window</h2>
        </div>
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_120px_minmax(0,1fr)_160px]">
          <input
            value={instance}
            onChange={(event) => setInstance(event.target.value)}
            placeholder="10.0.0.10 or web-01"
            className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
          />
          <input
            type="number"
            min={0.25}
            max={168}
            step={0.25}
            value={hours}
            onChange={(event) => setHours(Number(event.target.value))}
            className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
          />
          <input
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Reason"
            className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
          />
          <button
            onClick={createSuppression}
            disabled={!instance.trim() || busy}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Wrench className="h-4 w-4" />
            {busy ? "Saving" : "Suppress"}
          </button>
        </div>
        {result ? (
          <div className="mt-4">
            <JsonBlock value={result} maxHeight="max-h-40" />
          </div>
        ) : null}
      </section>

      <section className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold">Active suppressions</h2>
          <span className="text-xs text-muted-foreground">{loading ? "Loading" : `${rows.length} rows`}</span>
        </div>
        <div className="divide-y divide-border">
          {rows.map((row, index) => {
            const target = shortText(row.instance, "");
            return (
              <div key={`${target}-${index}`} className="grid gap-3 px-5 py-3.5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_180px_90px] lg:items-center">
                <div className="min-w-0">
                  <p className="truncate font-mono text-sm font-medium">{shortText(row.instance)}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{shortText(row.created_at, "No created timestamp")}</p>
                </div>
                <p className="truncate text-sm text-muted-foreground">{shortText(row.reason, "Maintenance")}</p>
                <p className="font-mono text-xs text-muted-foreground">{shortText(row.until)}</p>
                <button
                  onClick={() => removeSuppression(target)}
                  disabled={!target || busy}
                  className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-border px-2 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Remove
                </button>
              </div>
            );
          })}
          {rows.length === 0 ? (
            <div className="px-5 py-12 text-center text-sm text-muted-foreground">No active maintenance windows.</div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
