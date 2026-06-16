"use client";

import { useCallback, useEffect, useState } from "react";
import { Pause, Play, RefreshCw, Save } from "lucide-react";
import { api } from "@/lib/api";
import { JsonBlock } from "@/components/json-block";
import { shortText } from "@/lib/utils";

const controls = [
  { key: "telegram_alerts", label: "Telegram alerts" },
  { key: "email_reports", label: "Gmail reports" },
  { key: "log_generation", label: "Log generator" },
  { key: "incident_generation", label: "Incident generator" }
];

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

export default function LoggingRuntimePage() {
  const [status, setStatus] = useState<Record<string, unknown>>({});
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [demoInterval, setDemoInterval] = useState("");
  const [incidentInterval, setIncidentInterval] = useState("");
  const [reportTime, setReportTime] = useState("");
  const [scanInterval, setScanInterval] = useState("");

  const refresh = useCallback(async () => {
    setStatus(await api.loggingStatus().catch((error) => ({ error: String(error) })));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runtimeControls = asRecord(status.runtime_controls);
  const pauses = asRecord(runtimeControls.pauses);
  const values = asRecord(runtimeControls.values);
  const config = asRecord(status.config);

  useEffect(() => {
    setDemoInterval(shortText(values.demo_log_interval_seconds ?? config.demo_log_interval_seconds, ""));
    setIncidentInterval(shortText(values.incident_log_interval_seconds ?? config.incident_log_interval_seconds, ""));
    setReportTime(shortText(values.report_time ?? config.report_time, ""));
    setScanInterval(shortText(values.scan_interval_seconds ?? config.scan_interval_seconds, ""));
  }, [config.demo_log_interval_seconds, config.incident_log_interval_seconds, config.report_time, config.scan_interval_seconds, values.demo_log_interval_seconds, values.incident_log_interval_seconds, values.report_time, values.scan_interval_seconds]);

  const toggle = async (control: string, enabled: boolean) => {
    setBusyKey(`${control}-${enabled}`);
    try {
      const response = await api.loggingRuntimeControl({ control, enabled });
      setResult(response);
      await refresh();
    } catch (error) {
      setResult({ status: "error", message: String(error) });
    } finally {
      setBusyKey(null);
    }
  };

  const saveSetting = async (setting: string, payload: Record<string, unknown>) => {
    setBusyKey(setting);
    try {
      const response = await api.loggingRuntimeControl({ setting, ...payload });
      setResult(response);
      await refresh();
    } catch (error) {
      setResult({ status: "error", message: String(error) });
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Logging</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Runtime controls</h1>
          <p className="mt-1 text-sm text-muted-foreground">Pause or resume log sentinel delivery and demo generation workflows.</p>
        </div>
        <button onClick={refresh} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border px-4 text-sm font-medium hover:bg-secondary">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      <section className="grid gap-4 lg:grid-cols-4">
        {controls.map((control) => {
          const state = asRecord(pauses[control.key]);
          const paused = Boolean(state.paused);
          return (
            <div key={control.key} className="rounded-lg border border-border bg-card p-5 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold">{control.label}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{paused ? "Paused" : "Enabled"}</p>
                </div>
                <span className={`h-2.5 w-2.5 rounded-full ${paused ? "bg-amber-500" : "bg-emerald-500"}`} />
              </div>
              <p className="mt-3 min-h-10 text-xs leading-5 text-muted-foreground">{shortText(state.paused_until, "No pause window")}</p>
              <div className="mt-4 flex gap-2">
                <button
                  onClick={() => toggle(control.key, true)}
                  disabled={busyKey !== null}
                  className="inline-flex h-8 flex-1 items-center justify-center gap-1 rounded-lg border border-border text-xs font-medium hover:bg-secondary disabled:opacity-50"
                >
                  <Play className="h-3.5 w-3.5" />
                  Enable
                </button>
                <button
                  onClick={() => toggle(control.key, false)}
                  disabled={busyKey !== null}
                  className="inline-flex h-8 flex-1 items-center justify-center gap-1 rounded-lg border border-border text-xs font-medium hover:bg-secondary disabled:opacity-50"
                >
                  <Pause className="h-3.5 w-3.5" />
                  Disable
                </button>
              </div>
            </div>
          );
        })}
      </section>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold">Runtime values</h2>
        <div className="grid gap-3 md:grid-cols-4">
          {Object.entries(values).map(([key, value]) => (
            <div key={key} className="rounded-lg border border-border bg-slate-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{key.replace(/_/g, " ")}</p>
              <p className="mt-2 text-sm font-medium">{shortText(value, "default")}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="mb-4">
          <h2 className="text-sm font-semibold">Runtime settings</h2>
          <p className="mt-1 text-xs text-muted-foreground">Same live settings exposed by the logging child dashboard.</p>
        </div>
        <div className="grid gap-3 xl:grid-cols-4">
          <SettingInput
            label="Demo log interval"
            suffix="seconds"
            value={demoInterval}
            onChange={setDemoInterval}
            disabled={busyKey !== null}
            onSave={() => saveSetting("demo_log_interval_seconds", { seconds: Number(demoInterval) })}
          />
          <SettingInput
            label="Incident interval"
            suffix="seconds"
            value={incidentInterval}
            onChange={setIncidentInterval}
            disabled={busyKey !== null}
            onSave={() => saveSetting("incident_log_interval_seconds", { seconds: Number(incidentInterval) })}
          />
          <SettingInput
            label="Daily report time"
            suffix="HH:MM"
            value={reportTime}
            onChange={setReportTime}
            disabled={busyKey !== null}
            onSave={() => saveSetting("report_time", { value: reportTime })}
          />
          <SettingInput
            label="Scan interval"
            suffix="seconds"
            value={scanInterval}
            onChange={setScanInterval}
            disabled={busyKey !== null}
            onSave={() => saveSetting("scan_interval_seconds", { seconds: Number(scanInterval) })}
          />
        </div>
      </section>

      {result ? (
        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h2 className="mb-4 text-sm font-semibold">Last update response</h2>
          <JsonBlock value={result} />
        </section>
      ) : null}

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold">Raw runtime status</h2>
        <JsonBlock value={status} />
      </section>
    </div>
  );
}

function SettingInput({
  label,
  suffix,
  value,
  onChange,
  onSave,
  disabled
}: {
  label: string;
  suffix: string;
  value: string;
  onChange: (value: string) => void;
  onSave: () => void;
  disabled: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-slate-50 p-4">
      <label className="grid gap-1.5">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          disabled={disabled}
          className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-60"
          placeholder={suffix}
        />
      </label>
      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="text-xs text-muted-foreground">{suffix}</span>
        <button
          onClick={onSave}
          disabled={disabled || !value.trim()}
          className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-border px-2.5 text-xs font-medium transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Save className="h-3.5 w-3.5" />
          Save
        </button>
      </div>
    </div>
  );
}
