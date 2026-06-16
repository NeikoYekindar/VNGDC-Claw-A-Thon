"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { AddServerDialog } from "@/components/add-server-dialog";
import { StatusBadge } from "@/components/status-badge";
import { api, type Server, type Stats, type Task } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import type { HardeningStatus } from "@/lib/utils";

const PIE_COLORS: Record<string, string> = {
  Hardened: "#059669",
  Partial: "#d97706",
  "Not Hardened": "#dc2626",
  Unchecked: "#64748b",
};

function StatCard({ label, value, sub, accent }: { label: string; value: number; sub?: string; accent: string }) {
  return (
    <div className="relative overflow-hidden rounded-lg border border-border bg-card p-4 shadow-sm">
      <div className={`absolute left-0 top-0 h-full w-1 ${accent}`} />
      <p className="pl-3 text-2xl font-semibold tabular-nums">{value}</p>
      <p className="mt-0.5 pl-3 text-sm text-muted-foreground">{label}</p>
      {sub ? <p className="mt-0.5 pl-3 text-xs text-muted-foreground/80">{sub}</p> : null}
    </div>
  );
}

function ServerIcon({ os }: { os: string }) {
  const tone =
    os === "ubuntu"
      ? "border-orange-200 bg-orange-50 text-orange-700"
      : os === "junos"
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : "border-blue-200 bg-blue-50 text-blue-700";

  return (
    <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${tone}`}>
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 7h14M7 7v10m10-10v10M5 17h14M8 11h.01M8 14h.01M16 11h.01M16 14h.01" />
      </svg>
    </div>
  );
}

function RunButton({ server, onDone }: { server: Server; onDone: () => void }) {
  const [taskId, setTaskId] = useState<string | null>(null);
  const [status, setStatus] = useState<Task["status"] | null>(null);

  const run = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const task = await api.runCheck(server.id);
      setTaskId(task.id);
      setStatus("pending");
    } catch {
      setStatus("failed");
    }
  };

  useEffect(() => {
    if (!taskId || status === "completed" || status === "failed") return;
    const iv = setInterval(async () => {
      try {
        const task = await api.task(taskId);
        setStatus(task.status);
        if (task.status === "completed" || task.status === "failed") {
          clearInterval(iv);
          onDone();
        }
      } catch {
        clearInterval(iv);
      }
    }, 2000);
    return () => clearInterval(iv);
  }, [taskId, status, onDone]);

  const isRunning = status === "pending" || status === "running";

  return (
    <button
      onClick={run}
      disabled={isRunning}
      className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border px-3 text-xs font-medium transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-50"
    >
      {isRunning ? (
        <>
          <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.6m15.3 2A8 8 0 004.6 9m0 0H9m11 11v-5h-.6m0 0a8 8 0 01-15.4-2m15.4 2H15" />
          </svg>
          Checking
        </>
      ) : (
        <>
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.8 11.2l-3.2-2.1A1 1 0 0010 9.9v4.2a1 1 0 001.6.8l3.2-2.1a1 1 0 000-1.6z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Run Check
        </>
      )}
    </button>
  );
}

export default function HardeningPage() {
  const router = useRouter();
  const [servers, setServers] = useState<Server[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [s, st] = await Promise.all([api.servers(), api.stats()]);
      setServers(s);
      setStats(st);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const pieData = stats
    ? [
        { name: "Hardened", value: stats.hardened },
        { name: "Partial", value: stats.partial },
        { name: "Not Hardened", value: stats.none },
        { name: "Unchecked", value: stats.unchecked },
      ].filter((d) => d.value > 0)
    : [];

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
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Hardening</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Server hardening checks</h1>
          <p className="mt-1 text-sm text-muted-foreground">Monitor configured Ubuntu, Windows, and Junos hardening baselines.</p>
        </div>
        <AddServerDialog onAdded={refresh} />
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatCard label="Total Servers" value={stats?.total ?? 0} accent="bg-slate-500" />
        <StatCard label="Hardened" value={stats?.hardened ?? 0} accent="bg-emerald-500" sub="All checks pass" />
        <StatCard label="Partial" value={stats?.partial ?? 0} accent="bg-amber-500" sub="Needs review" />
        <StatCard label="Not Hardened" value={stats?.none ?? 0} accent="bg-red-500" sub="Needs action" />
        <StatCard label="Unchecked" value={stats?.unchecked ?? 0} accent="bg-slate-400" sub="Never scanned" />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Hardening distribution</h2>
            <span className="text-xs text-muted-foreground">{stats?.total ?? 0} assets</span>
          </div>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={230}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={56} outerRadius={86} paddingAngle={3} dataKey="value" stroke="none">
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={PIE_COLORS[entry.name] ?? "#64748b"} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: "#ffffff", border: "1px solid #d8dee8", borderRadius: 8, color: "#172033" }}
                  labelStyle={{ color: "#172033" }}
                />
                <Legend iconType="circle" iconSize={8} formatter={(v) => <span className="text-xs text-muted-foreground">{v}</span>} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[230px] items-center justify-center text-sm text-muted-foreground">No servers added yet</div>
          )}
        </div>

        <div className="overflow-hidden rounded-lg border border-border bg-card shadow-sm lg:col-span-2">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h2 className="text-sm font-semibold">Managed servers</h2>
            <span className="text-xs text-muted-foreground">{servers.length} rows</span>
          </div>

          {servers.length === 0 ? (
            <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
              <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-lg bg-secondary text-muted-foreground">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </div>
              <p className="text-sm font-medium">No servers yet</p>
              <p className="mt-1 text-xs text-muted-foreground">Add a server to start hardening checks</p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {servers.map((server) => (
                <div
                  key={server.id}
                  className="flex cursor-pointer items-center gap-4 px-5 py-3.5 transition-colors hover:bg-secondary/60"
                  onClick={() => router.push(`/servers/${server.id}`)}
                >
                  <ServerIcon os={server.os_type} />

                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{server.name}</p>
                    <p className="truncate font-mono text-xs text-muted-foreground">
                      {server.host}:{server.port}
                    </p>
                  </div>

                  <div className="hidden w-24 shrink-0 text-right text-xs text-muted-foreground sm:block">
                    {timeAgo(server.last_checked_at)}
                  </div>

                  <div className="shrink-0">
                    <StatusBadge status={server.last_status as HardeningStatus} size="sm" />
                  </div>

                  <div className="hidden shrink-0 sm:block" onClick={(e) => e.stopPropagation()}>
                    <RunButton server={server} onDone={refresh} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
