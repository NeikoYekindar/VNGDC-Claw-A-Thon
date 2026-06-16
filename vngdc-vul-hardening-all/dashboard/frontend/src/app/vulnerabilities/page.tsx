"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { StatusBadge } from "@/components/status-badge";
import { api, type AgentStatus, type Server, type Stats, type VulnerabilityItem, type VulnerabilitySchedule, type VulnerabilitySummary } from "@/lib/api";
import { osTypeLabel, timeAgo } from "@/lib/utils";
import type { HardeningStatus } from "@/lib/utils";

function MetricCard({ label, value, tone, sub }: { label: string; value: number | string; tone: string; sub: string }) {
  return (
    <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className={`mb-3 h-1 w-10 rounded-full ${tone}`} />
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
      <p className="mt-0.5 text-sm font-medium">{label}</p>
      <p className="mt-1 text-xs text-muted-foreground">{sub}</p>
    </div>
  );
}

function exposureFor(server: Server) {
  switch (server.last_status) {
    case "hardened":
      return { label: "Baseline ok", color: "text-emerald-700", ring: "bg-emerald-500" };
    case "partial":
      return { label: "Needs review", color: "text-amber-700", ring: "bg-amber-500" };
    case "none":
    case "error":
      return { label: "Elevated", color: "text-red-700", ring: "bg-red-500" };
    default:
      return { label: "Unknown", color: "text-slate-600", ring: "bg-slate-400" };
  }
}

function itemMatchesServer(item: VulnerabilityItem, server: Server) {
  const serverName = server.name.toLowerCase();
  const serverHost = server.host.toLowerCase();
  const candidates = [item.agent, item.agent_id]
    .map((value) => String(value ?? "").toLowerCase())
    .filter(Boolean);
  return candidates.some(
    (candidate) =>
      candidate === serverName ||
      candidate === serverHost ||
      candidate.startsWith(`${serverName}.`) ||
      serverName.startsWith(`${candidate}.`),
  );
}

function assetSignal(server: Server, items: VulnerabilityItem[]) {
  const matched = items.filter((item) => itemMatchesServer(item, server));
  if (!matched.length) return { risk: 0, exploit: "Unknown", sla: "N/A" };

  const risk = Math.max(...matched.map((item) => Number(item.risk_score ?? 0)));
  const exploitOrder: Record<string, number> = {
    "Known exploited": 4,
    High: 3,
    Medium: 2,
    Low: 1,
    Unknown: 0,
  };
  const exploit = matched
    .map((item) => item.exploit_likelihood ?? "Unknown")
    .sort((a, b) => (exploitOrder[b] ?? 0) - (exploitOrder[a] ?? 0))[0];
  const sla = matched
    .filter((item) => item.patch_sla_hours)
    .sort((a, b) => Number(a.patch_sla_hours ?? 99999) - Number(b.patch_sla_hours ?? 99999))[0]?.patch_sla ?? "N/A";
  return { risk, exploit, sla };
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

function defaultSchedule(): VulnerabilitySchedule {
  return {
    enabled: false,
    interval_seconds: 900,
    include_analysis: true,
    send_report: true,
    agent_name: "",
    last_run_at: null,
    next_run_at: null,
    last_status: null,
    last_error: null,
    updated_at: null,
  };
}

export default function VulnerabilitiesPage() {
  const router = useRouter();
  const [servers, setServers] = useState<Server[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [vuln, setVuln] = useState<VulnerabilitySummary | null>(null);
  const [schedule, setSchedule] = useState<VulnerabilitySchedule | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [scheduleError, setScheduleError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [serverRows, hardeningStats, agent, vulnerabilitySummary, vulnerabilitySchedule] = await Promise.all([
        api.servers(),
        api.stats(),
        api.agentStatus().catch(() => null),
        api.vulnerabilitySummary().catch(() => null),
        api.vulnerabilitySchedule().catch(() => null),
      ]);
      setServers(serverRows);
      setStats(hardeningStats);
      setAgentStatus(agent);
      setVuln(vulnerabilitySummary);
      setSchedule(vulnerabilitySchedule);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const riskSummary = useMemo(() => {
    const elevated = servers.filter((s) => s.last_status === "none" || s.last_status === "error").length;
    const review = servers.filter((s) => s.last_status === "partial").length;
    const unknown = servers.filter((s) => !s.last_status).length;
    return { elevated, review, unknown };
  }, [servers]);

  const recentAssets = useMemo(
    () =>
      [...servers]
        .sort((a, b) => new Date(b.last_checked_at ?? 0).getTime() - new Date(a.last_checked_at ?? 0).getTime())
        .slice(0, 8),
    [servers],
  );

  const runVulnerabilityRefresh = async () => {
    if (scanning) return;
    setScanning(true);
    try {
      const result = await api.refreshVulnerabilities(true, false);
      setVuln(result);
      await refresh();
    } finally {
      setScanning(false);
    }
  };

  const updateScheduleField = <K extends keyof VulnerabilitySchedule>(key: K, value: VulnerabilitySchedule[K]) => {
    setSchedule((current) => {
      const baseline: VulnerabilitySchedule = current ?? {
        ...defaultSchedule(),
      };
      return { ...baseline, [key]: value };
    });
  };

  const saveSchedule = async () => {
    if (savingSchedule) return;
    const current = schedule ?? defaultSchedule();
    setSavingSchedule(true);
    setScheduleError("");
    try {
      const saved = await api.updateVulnerabilitySchedule({
        enabled: current.enabled,
        interval_seconds: Math.max(60, Number(current.interval_seconds || 900)),
        include_analysis: current.include_analysis,
        send_report: current.send_report,
        agent_name: current.agent_name,
      });
      setSchedule(saved);
      setScheduleOpen(false);
    } catch (err) {
      setScheduleError(String(err));
    } finally {
      setSavingSchedule(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <svg className="h-6 w-6 animate-spin text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.6m15.3 2A8 8 0 004.6 9m0 0H9m11 11v-5h-.6m0 0a8 8 0 01-15.4-2m15.4 2H15" />
        </svg>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Vulnerability Assets</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight">Asset vulnerability posture</h1>
            <p className="mt-1 text-sm text-muted-foreground">Managed assets, scanner readiness, and latest vulnerability signals.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => {
                setScheduleError("");
                setSchedule((current) => current ?? defaultSchedule());
                setScheduleOpen(true);
              }}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors hover:bg-secondary"
            >
              <span className={`h-2 w-2 rounded-full ${schedule?.enabled ? "bg-emerald-500" : "bg-slate-400"}`} />
              Scheduled CVE checks
            </button>
            <a
              href={api.vulnerabilityLatestExportUrl()}
              className="inline-flex h-10 items-center justify-center rounded-lg border border-border bg-card px-4 text-sm font-medium text-foreground transition-colors hover:bg-secondary"
            >
              Export XLSX
            </a>
            <button
              onClick={runVulnerabilityRefresh}
              disabled={scanning || agentStatus?.connected === false}
              className="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {scanning ? "Scanning..." : "Refresh from Agent"}
            </button>
          </div>
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
                  {schedule?.enabled
                    ? `Next run ${schedule.next_run_at ? timeAgo(schedule.next_run_at) : "pending"}`
                    : "Periodic vulnerability scan is disabled"}
                </p>
              </div>
              <button
                onClick={() => setScheduleOpen(false)}
                className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
                type="button"
              >
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="space-y-4 px-6 py-5">
              <label className="flex items-center justify-between gap-3 rounded-lg border border-border bg-secondary/40 px-4 py-3 text-sm font-medium text-slate-800">
                Enable scheduled scan
                <input
                  type="checkbox"
                  checked={Boolean(schedule?.enabled)}
                  onChange={(event) => updateScheduleField("enabled", event.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
                />
              </label>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="grid gap-1.5 text-xs font-medium text-slate-700">
                  Interval minutes
                  <input
                    type="number"
                    min={1}
                    max={10080}
                    value={Math.max(1, Math.round((schedule?.interval_seconds ?? 900) / 60))}
                    onChange={(event) => updateScheduleField("interval_seconds", Math.max(60, Number(event.target.value || 15) * 60))}
                    className="h-10 rounded-lg border border-border bg-white px-3 text-sm font-normal text-foreground outline-none focus:border-primary"
                  />
                </label>
                <label className="grid gap-1.5 text-xs font-medium text-slate-700">
                  Wazuh agent filter
                  <input
                    value={schedule?.agent_name ?? ""}
                    onChange={(event) => updateScheduleField("agent_name", event.target.value)}
                    placeholder="All agents"
                    className="h-10 rounded-lg border border-border bg-white px-3 text-sm font-normal text-foreground outline-none focus:border-primary"
                  />
                </label>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs text-slate-700">
                  <input
                    type="checkbox"
                    checked={Boolean(schedule?.include_analysis)}
                    onChange={(event) => updateScheduleField("include_analysis", event.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
                  />
                  Include agent analysis
                </label>
                <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs text-slate-700">
                  <input
                    type="checkbox"
                    checked={Boolean(schedule?.send_report)}
                    onChange={(event) => updateScheduleField("send_report", event.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
                  />
                  Send Excel report
                </label>
              </div>

              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-muted-foreground">
                <p>Last run: {schedule?.last_run_at ? timeAgo(schedule.last_run_at) : "Never"}</p>
                <p>Status: {schedule?.last_status ?? "N/A"}</p>
                {schedule?.last_error ? <p className="mt-1 break-all text-red-700">{schedule.last_error}</p> : null}
              </div>

              {scheduleError ? (
                <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{scheduleError}</div>
              ) : null}
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
                className="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                type="button"
              >
                {savingSchedule ? "Saving..." : "Save schedule"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard label="Critical CVEs" value={vuln?.critical ?? 0} tone="bg-red-600" sub={vuln?.scanned_at ? `Last scan ${timeAgo(vuln.scanned_at)}` : "No CVE data yet"} />
        <MetricCard label="High CVEs" value={vuln?.high ?? 0} tone="bg-orange-500" sub={vuln?.source ? `Source: ${vuln.source}` : "Waiting for scanner results"} />
        <MetricCard label="Assets at risk" value={riskSummary.elevated + riskSummary.review} tone="bg-amber-500" sub="Derived from hardening posture" />
        <MetricCard label="Unknown coverage" value={riskSummary.unknown} tone="bg-slate-400" sub="Assets not checked yet" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="overflow-hidden rounded-lg border border-border bg-card shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h2 className="text-sm font-semibold">Managed assets</h2>
            <span className="text-xs text-muted-foreground">{servers.length} assets</span>
          </div>

          {recentAssets.length === 0 ? (
            <div className="px-6 py-14 text-center text-sm text-muted-foreground">No managed assets yet.</div>
          ) : (
            <div className="divide-y divide-border">
              {recentAssets.map((server) => {
                const exposure = exposureFor(server);
                const signal = assetSignal(server, vuln?.items ?? []);
                return (
                  <button
                    key={server.id}
                    type="button"
                    onClick={() => router.push(`/vulnerabilities/${server.id}`)}
                    className="grid w-full gap-3 px-5 py-3.5 text-left transition-colors hover:bg-blue-50 md:grid-cols-[1fr_130px_130px_115px_130px_90px_90px] md:items-center"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{server.name}</p>
                      <p className="truncate font-mono text-xs text-muted-foreground">
                        {server.host}:{server.port}
                      </p>
                    </div>
                    <div className="text-xs text-muted-foreground">{osTypeLabel(server.os_type)}</div>
                    <StatusBadge status={server.last_status as HardeningStatus} size="sm" />
                    <div className={`flex items-center gap-2 text-xs font-medium ${exposure.color}`}>
                      <span className={`h-2 w-2 rounded-full ${exposure.ring}`} />
                      {exposure.label}
                    </div>
                    <div className="text-xs text-slate-700">
                      <span className="font-medium">Exploit</span> {exploitLabel(signal.exploit)}
                    </div>
                    <div className="text-xs text-slate-700">
                      <span className="font-medium">SLA</span> {signal.sla}
                    </div>
                    <span className="text-xs font-medium text-primary">View details</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <h2 className="text-sm font-semibold">Scanner readiness</h2>
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">Hardening database</p>
                  <p className="text-xs text-muted-foreground">{stats?.total ?? 0} managed assets</p>
                </div>
                <span className="rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">Online</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">Security agent</p>
                  <p className="text-xs text-muted-foreground">{agentStatus?.connected ? "Runtime reachable" : "Runtime not reachable"}</p>
                </div>
                <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${agentStatus?.connected ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700"}`}>
                  {agentStatus?.connected ? "Online" : "Offline"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium">CVE scanner feed</p>
                  <p className="text-xs text-muted-foreground">
                    {vuln?.scanned_at ? `${vuln.fetched} findings fetched - ${timeAgo(vuln.scanned_at)}` : "No dashboard feed response"}
                  </p>
                </div>
                <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${vuln?.status === "completed" ? "border-emerald-200 bg-emerald-50 text-emerald-700" : vuln?.status === "failed" ? "border-red-200 bg-red-50 text-red-700" : "border-slate-200 bg-slate-50 text-slate-600"}`}>
                  {vuln?.status === "completed" ? "Online" : vuln?.status === "failed" ? "Error" : "Pending"}
                </span>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <h2 className="text-sm font-semibold">Latest vulnerability signals</h2>
            <div className="mt-4 space-y-3">
              {(vuln?.items ?? []).slice(0, 6).map((item, index) => {
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
              {(vuln?.items ?? []).length === 0 ? <p className="text-sm text-muted-foreground">No vulnerability events yet.</p> : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
