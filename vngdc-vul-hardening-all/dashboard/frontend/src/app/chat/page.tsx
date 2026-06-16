"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AgentChatPanel } from "@/components/agent-chat-panel";
import { api, type AgentStatus, type Server, type Stats, type VulnerabilitySummary } from "@/lib/api";
import { statusLabel, timeAgo } from "@/lib/utils";
import type { HardeningStatus } from "@/lib/utils";

function SummaryRow({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="flex items-center gap-2">
        <span className={`h-2 w-2 rounded-full ${tone}`} />
        <span className="text-sm text-muted-foreground">{label}</span>
      </div>
      <span className="text-sm font-semibold tabular-nums">{value}</span>
    </div>
  );
}

function EventDot({ status }: { status: string | null }) {
  const tone =
    status === "hardened"
      ? "bg-emerald-500"
      : status === "partial"
        ? "bg-amber-500"
        : status === "none" || status === "error"
          ? "bg-red-500"
          : "bg-slate-400";

  return <span className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${tone}`} />;
}

export default function ChatPage() {
  const [servers, setServers] = useState<Server[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [vuln, setVuln] = useState<VulnerabilitySummary | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [serverRows, hardeningStats, agent, vulnerabilitySummary] = await Promise.all([
        api.servers(),
        api.stats(),
        api.agentStatus().catch(() => null),
        api.vulnerabilitySummary().catch(() => null),
      ]);
      setServers(serverRows);
      setStats(hardeningStats);
      setAgentStatus(agent);
      setVuln(vulnerabilitySummary);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 45_000);
    return () => clearInterval(iv);
  }, [refresh]);

  const vulnerabilitySignals = useMemo(() => {
    const elevated = servers.filter((server) => server.last_status === "none" || server.last_status === "error").length;
    const review = servers.filter((server) => server.last_status === "partial").length;
    const unknown = servers.filter((server) => !server.last_status).length;
    return { elevated, review, unknown };
  }, [servers]);

  const events = useMemo(() => {
    const serverEvents = [...servers]
      .sort((a, b) => new Date(b.last_checked_at ?? 0).getTime() - new Date(a.last_checked_at ?? 0).getTime())
      .slice(0, 8)
      .map((server) => ({
        id: server.id,
        title: server.name,
        description: `${statusLabel(server.last_status as HardeningStatus)} - ${timeAgo(server.last_checked_at)}`,
        status: server.last_status,
      }));

    return [
      {
        id: "agent",
        title: "Security agent runtime",
        description: agentStatus?.connected ? "Online" : "Offline or not checked",
        status: agentStatus?.connected ? "hardened" : "error",
      },
      ...serverEvents,
    ];
  }, [agentStatus?.connected, servers]);

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
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Agent Chat</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Security operations chat</h1>
        <p className="mt-1 text-sm text-muted-foreground">Hardening, vulnerability posture, and runtime events in one workspace.</p>
      </div>

      <div className="grid items-stretch gap-6 xl:h-[calc(100vh-220px)] xl:min-h-[620px] xl:grid-cols-[320px_minmax(0,1fr)_340px] 2xl:grid-cols-[380px_minmax(0,1fr)_420px]">
        <aside className="flex min-h-0 flex-col rounded-lg border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold">Operations summary</h2>
            <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${agentStatus?.connected ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-700"}`}>
              {agentStatus?.connected ? "Agent online" : "Agent offline"}
            </span>
          </div>

          <div className="mt-5 space-y-6">
            <div>
              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">Hardening</p>
                <span className="text-xs text-muted-foreground">{stats?.total ?? 0} assets</span>
              </div>
              <div className="space-y-3">
                <SummaryRow label="Hardened" value={stats?.hardened ?? 0} tone="bg-emerald-500" />
                <SummaryRow label="Partial" value={stats?.partial ?? 0} tone="bg-amber-500" />
                <SummaryRow label="Not hardened" value={stats?.none ?? 0} tone="bg-red-500" />
                <SummaryRow label="Unchecked" value={stats?.unchecked ?? 0} tone="bg-slate-400" />
              </div>
            </div>

            <div className="border-t border-border pt-5">
              <div className="mb-3 flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">Vulnerabilities</p>
                <span className="text-xs text-muted-foreground">derived</span>
              </div>
              <div className="space-y-3">
                <SummaryRow label="Critical CVEs" value={vuln?.critical ?? 0} tone="bg-red-600" />
                <SummaryRow label="High CVEs" value={vuln?.high ?? 0} tone="bg-orange-500" />
                <SummaryRow label="Elevated assets" value={vulnerabilitySignals.elevated} tone="bg-red-500" />
                <SummaryRow label="Review queue" value={vulnerabilitySignals.review + vulnerabilitySignals.unknown} tone="bg-amber-500" />
              </div>
            </div>
          </div>
        </aside>

        <AgentChatPanel />

        <aside className="flex min-h-0 flex-col rounded-lg border border-border bg-card p-6 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-sm font-semibold">Latest events</h2>
            <button
              onClick={refresh}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
              title="Refresh"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.6m15.3 2A8 8 0 004.6 9m0 0H9m11 11v-5h-.6m0 0a8 8 0 01-15.4-2m15.4 2H15" />
              </svg>
            </button>
          </div>

          <div className="chat-scroll-area mt-5 min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
            {events.map((event) => (
              <div key={event.id} className="flex gap-3">
                <EventDot status={event.status} />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{event.title}</p>
                  <p className="text-xs text-muted-foreground">{event.description}</p>
                </div>
              </div>
            ))}
            {events.length === 1 && servers.length === 0 ? (
              <p className="text-sm text-muted-foreground">No server events yet.</p>
            ) : null}
          </div>
        </aside>
      </div>
    </div>
  );
}
