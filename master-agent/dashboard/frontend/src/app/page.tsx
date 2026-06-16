"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, Bot, Gauge, ScrollText, ShieldCheck } from "lucide-react";
import { api, type AgentStatus, type Overview } from "@/lib/api";
import { MasterChatPanel } from "@/components/master-chat-panel";
import { MetricCard } from "@/components/metric-card";
import { StatusPill } from "@/components/status-pill";
import { cn, numberFormat, shortText, statusBadgeClass } from "@/lib/utils";

const moduleMeta = {
  monitoring: {
    title: "Monitoring",
    href: "/monitoring",
    icon: Gauge,
    tone: "blue" as const,
    description: "Metrics, alerts, batches, inventory"
  },
  logging: {
    title: "Logging",
    href: "/logging",
    icon: ScrollText,
    tone: "teal" as const,
    description: "Logs, RCA, runtime controls"
  },
  security: {
    title: "Security",
    href: "/security",
    icon: ShieldCheck,
    tone: "emerald" as const,
    description: "Hardening, Wazuh, CVE posture"
  }
};

function runtimeStatusLabel(value: unknown) {
  const label = shortText(value);
  const normalized = label.toLowerCase();
  if (normalized === "ok" || normalized === "healthy") return "Healthy";
  return label;
}

function ModuleCard({ status }: { status: AgentStatus }) {
  const meta = moduleMeta[status.key as keyof typeof moduleMeta];
  const Icon = meta?.icon ?? Bot;
  return (
    <Link href={meta?.href ?? "/"} className="group relative overflow-hidden rounded-lg border border-border bg-card p-5 shadow-sm transition-colors hover:border-orange-200 hover:bg-orange-50/35">
      <div className="absolute bottom-4 left-0 top-4 w-1 rounded-r-full bg-orange-300" />
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-orange-200 bg-orange-50 text-primary">
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="font-semibold">{meta?.title ?? status.section}</p>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">{meta?.description ?? status.name}</p>
          </div>
        </div>
        <StatusPill connected={status.connected} compact />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <div className="flex min-w-0 flex-col justify-end">
          <p className="text-muted-foreground">Latency</p>
          <p className="mt-1 font-semibold tabular-nums">{status.latency_ms ?? "-"} ms</p>
        </div>
        <div className="flex min-w-0 flex-col justify-end">
          <p className="text-muted-foreground">Runtime</p>
          <span className={cn(statusBadgeClass(status.status), "mt-1 inline-flex min-h-6 w-fit items-center leading-none")}>{runtimeStatusLabel(status.status)}</span>
        </div>
      </div>
      <div className="mt-4 flex items-center gap-2 text-xs font-medium text-primary">
        Open module
        <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
      </div>
    </Link>
  );
}

export default function OverviewPage() {
  const [overview, setOverview] = useState<Overview | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setOverview(await api.overview());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 45_000);
    return () => clearInterval(iv);
  }, [refresh]);

  const activeCount = overview?.agents.filter((agent) => agent.connected).length ?? 0;
  const monitoring = overview?.monitoring ?? {};
  const logging = overview?.logging ?? {};
  const security = overview?.security ?? {};

  const securityStats = (security.stats ?? {}) as Record<string, unknown>;
  const vuln = (security.vulnerabilities ?? {}) as Record<string, unknown>;
  const severity = (logging.severity_counts ?? {}) as Record<string, number>;

  const metrics = useMemo(
    () => [
      { label: "Active Agents", value: `${activeCount}/3`, sub: "AgentBase health checks", icon: Activity, tone: "blue" as const },
      { label: "Monitoring Inventory", value: Number(monitoring.inventory_count ?? 0), sub: "Known monitored assets", icon: Gauge, tone: "blue" as const },
      { label: "Log Alerts", value: Number(severity.critical ?? 0) + Number(severity.error ?? 0) + Number(severity.warning ?? 0), sub: "Current report window", icon: ScrollText, tone: "teal" as const },
      {
        label: "Critical CVEs",
        value: Number(vuln.critical ?? 0),
        sub: `${numberFormat(Number(securityStats.total ?? 0))} hardening assets - ${numberFormat(Number(securityStats.hardened ?? 0))} hardened, ${numberFormat(Number(securityStats.partial ?? 0))} partial, ${numberFormat(Number(securityStats.none ?? 0))} not hardened, ${numberFormat(Number(securityStats.unchecked ?? 0))} unchecked`,
        icon: ShieldCheck,
        tone: "red" as const
      }
    ],
    [
      activeCount,
      monitoring.inventory_count,
      securityStats.hardened,
      securityStats.none,
      securityStats.partial,
      securityStats.total,
      securityStats.unchecked,
      severity.critical,
      severity.error,
      severity.warning,
      vuln.critical
    ]
  );

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Multi-agent operations</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Unified agent fabric</h1>
          <p className="mt-1 text-sm text-muted-foreground">One master agent orchestrates monitoring, logging, and security specialists.</p>
        </div>
        <Link
          href="/chat"
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          <Bot className="h-4 w-4" />
          Chat with Master
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_520px]">
        <div className="space-y-6">
          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Agent modules</h2>
              <button onClick={refresh} className="text-xs font-medium text-primary hover:underline">
                Refresh
              </button>
            </div>
            <div className="grid gap-4 lg:grid-cols-3">
              {(overview?.agents ?? []).map((status) => (
                <ModuleCard key={status.key} status={status} />
              ))}
            </div>
          </section>

          <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Routing behavior</h2>
              <StatusPill connected={activeCount === 3} label={`${activeCount}/3 child agents reachable`} />
            </div>
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="rounded-lg border border-border bg-slate-50 p-4">
                <p className="text-sm font-semibold">Monitoring questions</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">CPU, RAM, disk, latency, server inventory, alert batches, SSH investigation.</p>
              </div>
              <div className="rounded-lg border border-border bg-slate-50 p-4">
                <p className="text-sm font-semibold">Logging questions</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">Logs, RCA, event timeline, incidents, reports, runtime control.</p>
              </div>
              <div className="rounded-lg border border-border bg-slate-50 p-4">
                <p className="text-sm font-semibold">Security questions</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">Hardening, Wazuh vulnerability data, CVE checks, patch priority.</p>
              </div>
            </div>
          </section>
        </div>

        <MasterChatPanel compact />
      </div>
    </div>
  );
}
