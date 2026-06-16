"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, CircleHelp, ClipboardList, Download, RefreshCw, Server, Settings, ShieldAlert, X } from "lucide-react";
import {
  api,
  type SecurityServer,
  type SecurityStats,
  type VulnerabilityItem,
  type VulnerabilitySchedule,
  type VulnerabilitySummary
} from "@/lib/api";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge } from "@/components/status-badge";
import { cn, osTypeLabel, timeAgo } from "@/lib/utils";

const defaultSchedule: VulnerabilitySchedule = {
  enabled: false,
  interval_seconds: 900,
  include_analysis: true,
  send_report: false,
  agent_name: "",
  last_run_at: null,
  next_run_at: null,
  last_status: null,
  last_error: null,
  updated_at: null
};

function itemMatchesServer(item: VulnerabilityItem, server: SecurityServer) {
  const serverName = server.name.toLowerCase();
  const serverHost = server.host.toLowerCase();
  const candidates = [item.agent, item.agent_id].map((value) => String(value ?? "").toLowerCase()).filter(Boolean);
  return candidates.some(
    (candidate) =>
      candidate === serverName ||
      candidate === serverHost ||
      candidate.startsWith(`${serverName}.`) ||
      serverName.startsWith(`${candidate}.`)
  );
}

function assetSignal(server: SecurityServer, items: VulnerabilityItem[]) {
  const matched = items.filter((item) => itemMatchesServer(item, server));
  if (!matched.length) return { findings: 0, risk: 0, exploit: "Unknown", sla: "N/A" };

  const risk = Math.max(...matched.map((item) => Number(item.risk_score ?? 0)));
  const exploitOrder: Record<string, number> = {
    "Known exploited": 4,
    High: 3,
    Medium: 2,
    Low: 1,
    Unknown: 0
  };
  const exploit = matched
    .map((item) => item.exploit_likelihood ?? "Unknown")
    .sort((a, b) => (exploitOrder[b] ?? 0) - (exploitOrder[a] ?? 0))[0];
  const sla =
    matched
      .filter((item) => item.patch_sla_hours)
      .sort((a, b) => Number(a.patch_sla_hours ?? 99999) - Number(b.patch_sla_hours ?? 99999))[0]?.patch_sla ?? "N/A";
  return { findings: matched.length, risk, exploit, sla };
}

function exploitLabel(value?: string) {
  switch (String(value ?? "").toLowerCase()) {
    case "known exploited":
      return "Known exploited";
    case "high":
      return "High";
    case "medium":
      return "Medium";
    case "low":
      return "Low";
    default:
      return "Unknown";
  }
}

function exposureFor(server: SecurityServer) {
  switch (server.last_status) {
    case "hardened":
      return { label: "Baseline ok", color: "text-emerald-700", dot: "bg-emerald-500" };
    case "partial":
      return { label: "Needs review", color: "text-amber-700", dot: "bg-amber-500" };
    case "none":
    case "error":
      return { label: "Elevated", color: "text-red-700", dot: "bg-red-500" };
    default:
      return { label: "Unknown", color: "text-slate-600", dot: "bg-slate-400" };
  }
}

export default function SecurityVulnerabilitiesPage() {
  const router = useRouter();
  const [servers, setServers] = useState<SecurityServer[]>([]);
  const [stats, setStats] = useState<SecurityStats | null>(null);
  const [agentStatus, setAgentStatus] = useState<Record<string, unknown> | null>(null);
  const [summary, setSummary] = useState<VulnerabilitySummary | null>(null);
  const [schedule, setSchedule] = useState<VulnerabilitySchedule | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [scheduleError, setScheduleError] = useState("");

  const load = useCallback(async () => {
    try {
      const [serverRows, statRows, agent, vulnSummary, vulnSchedule] = await Promise.all([
        api.securityServers(),
        api.securityStats().catch(() => null),
        api.securityAgentStatus().catch(() => null),
        api.securityVulnerabilitySummary().catch(() => null),
        api.securityVulnerabilitySchedule().catch(() => null)
      ]);
      setServers(serverRows);
      setStats(statRows);
      setAgentStatus(agent);
      setSummary(vulnSummary);
      setSchedule(vulnSchedule);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 30_000);
    return () => clearInterval(iv);
  }, [load]);

  const riskSummary = useMemo(() => {
    const elevated = servers.filter((server) => server.last_status === "none" || server.last_status === "error").length;
    const review = servers.filter((server) => server.last_status === "partial").length;
    const unknown = servers.filter((server) => !server.last_status).length;
    return { elevated, review, unknown };
  }, [servers]);

  const runVulnerabilityRefresh = async () => {
    if (scanning) return;
    setScanning(true);
    try {
      setSummary(await api.securityRefreshVulnerabilities(true, false));
      await load();
    } finally {
      setScanning(false);
    }
  };

  const updateScheduleField = <K extends keyof VulnerabilitySchedule>(key: K, value: VulnerabilitySchedule[K]) => {
    setSchedule((current) => ({ ...(current ?? defaultSchedule), [key]: value }));
  };

  const saveSchedule = async () => {
    if (savingSchedule) return;
    const current = schedule ?? defaultSchedule;
    setSavingSchedule(true);
    setScheduleError("");
    try {
      const saved = await api.securityUpdateVulnerabilitySchedule({
        enabled: current.enabled,
        interval_seconds: Math.max(60, Number(current.interval_seconds || 900)),
        include_analysis: current.include_analysis,
        send_report: current.send_report,
        agent_name: current.agent_name
      });
      setSchedule(saved);
      setScheduleOpen(false);
    } catch (error) {
      setScheduleError(String(error));
    } finally {
      setSavingSchedule(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  const items = summary?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Security</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Vulnerability assets</h1>
          <p className="mt-1 text-sm text-muted-foreground">Asset CVE posture, scanner readiness, schedule, and latest findings.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => {
              setScheduleError("");
              setSchedule((current) => current ?? defaultSchedule);
              setScheduleOpen(true);
            }}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-medium transition-colors hover:bg-secondary"
          >
            <Settings className="h-4 w-4" />
            Schedule
          </button>
          <a
            href={api.securityVulnerabilityLatestExportUrl()}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-medium transition-colors hover:bg-secondary"
          >
            <Download className="h-4 w-4" />
            Export XLSX
          </a>
          <button
            onClick={runVulnerabilityRefresh}
            disabled={scanning || agentStatus?.connected === false}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-wait disabled:opacity-60"
          >
            <RefreshCw className={cn("h-4 w-4", scanning ? "animate-spin" : "")} />
            {scanning ? "Refreshing" : "Refresh from Agent"}
          </button>
        </div>
      </div>

      {scheduleOpen ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <button
            aria-label="Close schedule settings"
            className="absolute inset-0 bg-slate-950/35 backdrop-blur-sm"
            onClick={() => setScheduleOpen(false)}
            type="button"
          />
          <div className="relative w-full max-w-lg rounded-lg border border-border bg-card shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-border px-6 py-5">
              <div>
                <h2 className="text-lg font-semibold">Scheduled CVE checks</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {schedule?.enabled ? `Next run ${schedule.next_run_at ? timeAgo(schedule.next_run_at) : "pending"}` : "Periodic refresh is disabled"}
                </p>
              </div>
              <button
                onClick={() => setScheduleOpen(false)}
                className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                type="button"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4 px-6 py-5">
              <label className="flex items-center justify-between gap-3 rounded-lg border border-border bg-secondary/40 px-4 py-3 text-sm font-medium">
                Enable scheduled scan
                <input
                  type="checkbox"
                  checked={Boolean(schedule?.enabled)}
                  onChange={(event) => updateScheduleField("enabled", event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
                />
              </label>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                  Interval minutes
                  <input
                    type="number"
                    min={1}
                    max={10080}
                    value={Math.max(1, Math.round((schedule?.interval_seconds ?? 900) / 60))}
                    onChange={(event) => updateScheduleField("interval_seconds", Math.max(60, Number(event.target.value || 15) * 60))}
                    className="h-10 rounded-lg border border-border bg-background px-3 text-sm font-normal text-foreground outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </label>
                <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                  Wazuh agent filter
                  <input
                    value={schedule?.agent_name ?? ""}
                    onChange={(event) => updateScheduleField("agent_name", event.target.value)}
                    placeholder="All agents"
                    className="h-10 rounded-lg border border-border bg-background px-3 text-sm font-normal text-foreground outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </label>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs">
                  <input
                    type="checkbox"
                    checked={Boolean(schedule?.include_analysis)}
                    onChange={(event) => updateScheduleField("include_analysis", event.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
                  />
                  Include agent analysis
                </label>
                <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs">
                  <input
                    type="checkbox"
                    checked={Boolean(schedule?.send_report)}
                    onChange={(event) => updateScheduleField("send_report", event.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
                  />
                  Send report
                </label>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-muted-foreground">
                <p>Last run: {schedule?.last_run_at ? timeAgo(schedule.last_run_at) : "Never"}</p>
                <p>Status: {schedule?.last_status ?? "N/A"}</p>
                {schedule?.last_error ? <p className="mt-1 break-all text-red-700">{schedule.last_error}</p> : null}
              </div>

              {scheduleError ? <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{scheduleError}</div> : null}
            </div>

            <div className="flex justify-end gap-3 border-t border-border px-6 py-4">
              <button
                type="button"
                onClick={() => setScheduleOpen(false)}
                className="inline-flex h-10 items-center justify-center rounded-lg border border-border px-4 text-sm font-medium transition-colors hover:bg-secondary"
              >
                Cancel
              </button>
              <button
                onClick={saveSchedule}
                disabled={savingSchedule}
                className="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-wait disabled:opacity-60"
                type="button"
              >
                {savingSchedule ? "Saving" : "Save schedule"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Total Findings" value={Number(summary?.total ?? 0)} sub={summary?.scanned_at ? timeAgo(summary.scanned_at) : "No scan yet"} icon={ClipboardList} tone="slate" />
        <MetricCard label="Critical" value={Number(summary?.critical ?? 0)} icon={ShieldAlert} tone="red" />
        <MetricCard label="High" value={Number(summary?.high ?? 0)} icon={AlertTriangle} tone="amber" />
        <MetricCard label="Assets at risk" value={riskSummary.elevated + riskSummary.review} sub="Hardening posture" icon={Server} tone="blue" />
        <MetricCard label="Unknown" value={riskSummary.unknown} sub="No baseline yet" icon={CircleHelp} tone="slate" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h2 className="text-sm font-semibold">Asset vulnerability posture</h2>
            <span className="text-xs text-muted-foreground">{servers.length} assets</span>
          </div>
          <div className="divide-y divide-border">
            {servers.map((server) => {
              const exposure = exposureFor(server);
              const signal = assetSignal(server, items);
              return (
                <button
                  key={server.id}
                  type="button"
                  onClick={() => router.push(`/security/vulnerabilities/${encodeURIComponent(server.id)}`)}
                  className="grid w-full gap-3 px-5 py-3.5 text-left transition-colors hover:bg-secondary/60 lg:grid-cols-[minmax(0,1fr)_130px_130px_120px_120px_96px] lg:items-center"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{server.name}</p>
                    <p className="truncate font-mono text-xs text-muted-foreground">
                      {server.host}:{server.port} - {osTypeLabel(server.os_type)}
                    </p>
                  </div>
                  <StatusBadge status={server.last_status} size="sm" />
                  <div className={`flex items-center gap-2 text-xs font-medium ${exposure.color}`}>
                    <span className={`h-2 w-2 rounded-full ${exposure.dot}`} />
                    {exposure.label}
                  </div>
                  <span className="text-xs text-muted-foreground">{signal.findings} findings</span>
                  <span className="text-xs text-muted-foreground">Exploit {exploitLabel(signal.exploit)}</span>
                  <span className="text-xs font-medium text-primary">Details</span>
                </button>
              );
            })}
            {servers.length === 0 ? <div className="px-5 py-12 text-center text-sm text-muted-foreground">No managed assets yet.</div> : null}
          </div>
        </section>

        <div className="space-y-6">
          <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <h2 className="text-sm font-semibold">Scanner readiness</h2>
            <div className="mt-4 space-y-3">
              <ReadinessLine title="Hardening database" note={`${stats?.total ?? 0} managed assets`} ok />
              <ReadinessLine
                title="Security agent"
                note={agentStatus?.connected ? "Runtime reachable" : String(agentStatus?.error ?? "Not reachable")}
                ok={Boolean(agentStatus?.connected)}
              />
              <ReadinessLine
                title="CVE scanner feed"
                note={summary?.scanned_at ? `${summary.fetched ?? summary.total ?? 0} findings - ${timeAgo(summary.scanned_at)}` : "No scan yet"}
                ok={summary?.status === "completed"}
              />
              <ReadinessLine
                title="Scheduled checks"
                note={schedule?.enabled ? `Every ${schedule.interval_seconds}s` : "Disabled"}
                ok={Boolean(schedule?.enabled)}
              />
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <h2 className="text-sm font-semibold">Latest vulnerability signals</h2>
            <div className="mt-4 space-y-3">
              {items.slice(0, 6).map((item, index) => {
                const severity = String(item.severity ?? "").toLowerCase();
                const tone = severity === "critical" ? "bg-red-600" : severity === "high" ? "bg-orange-500" : severity === "medium" ? "bg-amber-500" : "bg-slate-400";
                return (
                  <div key={`${item.cve}-${item.agent}-${index}`} className="flex gap-3">
                    <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${tone}`} />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {item.cve ?? "N/A"} - {item.package ?? "unknown"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {item.severity ?? "Unknown"} on {item.agent ?? "unknown asset"}
                      </p>
                    </div>
                  </div>
                );
              })}
              {items.length === 0 ? <p className="text-sm text-muted-foreground">No vulnerability findings returned.</p> : null}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function ReadinessLine({ title, note, ok }: { title: string; note: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <p className="text-sm font-medium">{title}</p>
        <p className="truncate text-xs text-muted-foreground">{note}</p>
      </div>
      <span className={cn("rounded-full border px-2 py-0.5 text-xs font-medium", ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-slate-200 bg-slate-50 text-slate-600")}>
        {ok ? "Online" : "Pending"}
      </span>
    </div>
  );
}
