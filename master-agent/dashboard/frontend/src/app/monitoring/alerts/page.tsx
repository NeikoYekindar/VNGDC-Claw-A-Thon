"use client";

import { useCallback, useEffect, useState } from "react";
import { Play, RefreshCw, Send, Wand2 } from "lucide-react";
import { api } from "@/lib/api";
import { JsonBlock } from "@/components/json-block";
import { shortText, statusBadgeClass } from "@/lib/utils";

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : [];
}

function asUnknownArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export default function MonitoringAlertsPage() {
  const [batches, setBatches] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [triggerResult, setTriggerResult] = useState<Record<string, unknown> | null>(null);
  const [manualResult, setManualResult] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [alertName, setAlertName] = useState("HighCPU");
  const [instance, setInstance] = useState("");
  const [severity, setSeverity] = useState("critical");
  const [service, setService] = useState("web");
  const [description, setDescription] = useState("CPU usage is above threshold.");

  const loadBatches = useCallback(async () => {
    setBatches(await api.monitoringBatches().catch((error) => ({ status: "error", message: String(error) })));
  }, []);

  useEffect(() => {
    loadBatches();
    const iv = setInterval(loadBatches, 20_000);
    return () => clearInterval(iv);
  }, [loadBatches]);

  const batchRows = asArray(batches.batches);
  const batchIds = asUnknownArray(result?.batch_ids).map(String);
  const fallbackBatch = String(asUnknownArray(result?.batch_ids)[0] ?? "");
  const batchId = batchIds[0] || fallbackBatch;
  const alerts = asArray(result?.alerts);

  const simulate = async () => {
    setBusy(true);
    setTriggerResult(null);
    try {
      setResult(await api.monitoringSimulate());
      await loadBatches();
    } catch (error) {
      setResult({ status: "error", message: String(error) });
    } finally {
      setBusy(false);
    }
  };

  const trigger = async () => {
    if (!batchId) return;
    setTriggering(true);
    try {
      setTriggerResult(await api.monitoringTriggerBatch(batchId));
      await loadBatches();
    } catch (error) {
      setTriggerResult({ status: "error", message: String(error) });
    } finally {
      setTriggering(false);
    }
  };

  const triggerBatch = async (targetBatchId: string) => {
    if (!targetBatchId || triggering) return;
    setTriggering(true);
    try {
      setTriggerResult(await api.monitoringTriggerBatch(targetBatchId));
      await loadBatches();
    } catch (error) {
      setTriggerResult({ status: "error", message: String(error) });
    } finally {
      setTriggering(false);
    }
  };

  const sendManualAlert = async () => {
    if (!alertName.trim() || !instance.trim() || busy) return;
    setBusy(true);
    try {
      const payload = {
        alert_name: alertName.trim(),
        instance: instance.trim(),
        severity,
        service: service.trim(),
        description: description.trim(),
        labels: {
          source: "master-dashboard",
          service: service.trim()
        },
        timestamp: new Date().toISOString()
      };
      setManualResult(await api.monitoringReceiveAlert(payload));
      await loadBatches();
    } catch (error) {
      setManualResult({ status: "error", message: String(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Monitoring</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Alert RCA workspace</h1>
          <p className="mt-1 text-sm text-muted-foreground">Generate a correlated alert scenario and trigger the monitoring RCA workflow.</p>
        </div>
        <button
          onClick={simulate}
          disabled={busy}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-wait disabled:opacity-60"
        >
          <Wand2 className="h-4 w-4" />
          {busy ? "Generating" : "Generate Scenario"}
        </button>
      </div>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold">Manual alert injection</h2>
            <p className="mt-1 text-xs text-muted-foreground">Send a single alert payload to the monitoring RCA batcher.</p>
          </div>
          <button
            onClick={loadBatches}
            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-border px-2.5 text-xs font-medium transition-colors hover:bg-secondary"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh batches
          </button>
        </div>
        <div className="grid gap-3 lg:grid-cols-[150px_minmax(0,1fr)_130px_150px]">
          <input
            value={alertName}
            onChange={(event) => setAlertName(event.target.value)}
            className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
            placeholder="Alert name"
          />
          <input
            value={instance}
            onChange={(event) => setInstance(event.target.value)}
            className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
            placeholder="Instance IP or hostname"
          />
          <select
            value={severity}
            onChange={(event) => setSeverity(event.target.value)}
            className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
          >
            <option value="critical">critical</option>
            <option value="warning">warning</option>
            <option value="info">info</option>
          </select>
          <input
            value={service}
            onChange={(event) => setService(event.target.value)}
            className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
            placeholder="service"
          />
        </div>
        <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_160px]">
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            rows={3}
            className="resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/20"
            placeholder="Alert description"
          />
          <button
            onClick={sendManualAlert}
            disabled={!alertName.trim() || !instance.trim() || busy}
            className="inline-flex h-10 items-center justify-center gap-2 self-start rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            {busy ? "Sending" : "Send alert"}
          </button>
        </div>
        {manualResult ? (
          <div className="mt-4">
            <JsonBlock value={manualResult} maxHeight="max-h-40" />
          </div>
        ) : null}
      </section>

      {result ? (
        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold">{shortText(result.scenario, "Scenario result")}</h2>
              <p className="mt-1 text-xs text-muted-foreground">{shortText(result.alerts_sent, "0")} alerts sent to batch {batchId || "-"}</p>
            </div>
            <button
              onClick={trigger}
              disabled={!batchId || triggering}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border px-3 text-sm font-medium transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              {triggering ? "Triggering" : "Run RCA now"}
            </button>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            {alerts.map((alert, index) => (
              <div key={`${shortText(alert.instance)}-${index}`} className="rounded-lg border border-border bg-slate-50 p-4">
                <p className="text-sm font-semibold">{shortText(alert.alert_name)}</p>
                <p className="mt-1 text-xs text-muted-foreground">{shortText(alert.hostname || alert.instance)}</p>
                <p className="mt-3 text-xs leading-5 text-slate-700">{shortText(alert.description)}</p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold">Current RCA batches</h2>
          <span className="text-xs text-muted-foreground">{batchRows.length} rows</span>
        </div>
        <div className="divide-y divide-border">
          {batchRows.map((batch, index) => {
            const id = shortText(batch.batch_id, "");
            const status = shortText(batch.status, "unknown");
            return (
              <div key={`${id}-${index}`} className="grid gap-3 px-5 py-3.5 lg:grid-cols-[minmax(0,1fr)_110px_120px_190px_120px] lg:items-center">
                <div className="min-w-0">
                  <p className="truncate font-mono text-sm font-medium">{id || "-"}</p>
                  <p className="mt-0.5 truncate text-xs text-muted-foreground">{shortText(batch.created_at)}</p>
                </div>
                <span className="text-xs text-muted-foreground">{shortText(batch.alert_count, "0")} alerts</span>
                <span className={statusBadgeClass(status)}>{status}</span>
                <span className="font-mono text-xs text-muted-foreground">{shortText(batch.window_closes_at)}</span>
                <button
                  onClick={() => triggerBatch(id)}
                  disabled={!id || status !== "pending" || triggering}
                  className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-border px-2 text-xs font-medium transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <Play className="h-3.5 w-3.5" />
                  Run
                </button>
              </div>
            );
          })}
          {batchRows.length === 0 ? <div className="px-5 py-12 text-center text-sm text-muted-foreground">No batches returned.</div> : null}
        </div>
      </section>

      {triggerResult ? (
        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold">Trigger result</h2>
          <JsonBlock value={triggerResult} />
        </section>
      ) : null}

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold">Raw scenario payload</h2>
        <JsonBlock value={result ?? { message: "No scenario generated yet." }} />
      </section>
    </div>
  );
}
