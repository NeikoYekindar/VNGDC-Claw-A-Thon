"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, AlertTriangle, Info, OctagonAlert, ScrollText, Server } from "lucide-react";
import { api } from "@/lib/api";
import { MetricCard } from "@/components/metric-card";
import { JsonBlock } from "@/components/json-block";
import { shortText, statusBadgeClass } from "@/lib/utils";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : [];
}

export default function LoggingPage() {
  const [status, setStatus] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setStatus(await api.loggingStatus());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 20_000);
    return () => clearInterval(iv);
  }, [refresh]);

  const severity = asRecord(status.severity_counts);
  const domains = asRecord(status.domain_counts);
  const topAlerts = asArray(status.top_alerts);
  const workers = asRecord(status.workers);

  const criticalCount = Number(severity.critical ?? 0);
  const errorCount = Number(severity.error ?? 0);
  const warningCount = Number(severity.warning ?? 0);
  const infoCount = Number(severity.info ?? 0);
  const domainEntries = useMemo(() => Object.entries(domains).sort((a, b) => Number(b[1]) - Number(a[1])), [domains]);
  const domainMax = Math.max(1, ...domainEntries.map(([, value]) => Number(value) || 0));

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
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Logging</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Log sentinel console</h1>
          <p className="mt-1 text-sm text-muted-foreground">Runtime status, severity posture, top alerts, and workers.</p>
        </div>
        <button onClick={refresh} className="inline-flex h-10 items-center justify-center rounded-lg border border-border px-4 text-sm font-medium hover:bg-secondary">
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Events" value={Number(status.report_window_events ?? 0)} sub="Current report window" icon={ScrollText} tone="blue" />
        <MetricCard label="Critical" value={criticalCount} sub="Immediate attention" icon={OctagonAlert} tone={criticalCount > 0 ? "red" : "emerald"} />
        <MetricCard label="Error" value={errorCount} sub="Failed operations" icon={AlertCircle} tone={errorCount > 0 ? "red" : "emerald"} />
        <MetricCard label="Warning" value={warningCount} sub="Needs review" icon={AlertTriangle} tone={warningCount > 0 ? "amber" : "emerald"} />
        <MetricCard label="Info" value={infoCount} sub="Informational events" icon={Info} tone="teal" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <section className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h2 className="text-sm font-semibold">Top alerts</h2>
            <span className="text-xs text-muted-foreground">{topAlerts.length} rows</span>
          </div>
          <div className="divide-y divide-border">
            {topAlerts.map((alert, index) => (
              <div key={`${shortText(alert.timestamp)}-${index}`} className="grid gap-3 px-5 py-3.5 lg:grid-cols-[110px_minmax(0,1fr)_150px] lg:items-start">
                <span className={statusBadgeClass(alert.severity)}>
                  {shortText(alert.severity)}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium">{shortText(alert.message)}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{shortText(alert.probable_cause)}</p>
                </div>
                <div className="text-xs text-muted-foreground">
                  <p>{shortText(alert.domain)}</p>
                  <p>{shortText(alert.source)}</p>
                </div>
              </div>
            ))}
            {topAlerts.length === 0 ? (
              <div className="px-5 py-12 text-center text-sm text-muted-foreground">No top alerts returned in the current log window.</div>
            ) : null}
          </div>
        </section>

        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Domain distribution</h2>
            <Server className="h-4 w-4 text-muted-foreground" />
          </div>
          <div className="space-y-3">
            {domainEntries.map(([name, value]) => {
              const width = Math.max(4, Math.round((Number(value) / domainMax) * 100));
              return (
                <div key={name}>
                  <div className="mb-1 flex items-center justify-between gap-3 text-xs">
                    <span className="font-medium">{name}</span>
                    <span className="text-muted-foreground">{String(value)}</span>
                  </div>
                  <div className="h-2 rounded-full bg-secondary">
                    <div className="h-2 rounded-full bg-primary" style={{ width: `${width}%` }} />
                  </div>
                </div>
              );
            })}
            {domainEntries.length === 0 ? <p className="text-sm text-muted-foreground">No domain counts returned.</p> : null}
          </div>
        </section>
      </div>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold">Worker status</h2>
        <div className="grid gap-3 lg:grid-cols-4">
          {Object.entries(workers).map(([name, worker]) => {
            const data = asRecord(worker);
            return (
              <div key={name} className="rounded-lg border border-border bg-slate-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <p className="text-sm font-semibold">{name.replace(/_/g, " ")}</p>
                  <span className={statusBadgeClass(data.state)}>{shortText(data.state)}</span>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-700">{shortText(data.detail, "No detail")}</p>
              </div>
            );
          })}
          {Object.keys(workers).length === 0 ? <p className="text-sm text-muted-foreground">No worker data returned.</p> : null}
        </div>
      </section>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold">Raw logging status</h2>
        <JsonBlock value={status} />
      </section>
    </div>
  );
}
