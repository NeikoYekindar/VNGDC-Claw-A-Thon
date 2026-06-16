"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type MouseEvent } from "react";
import { ChevronRight, ClipboardList, Play, Plus, Radar, RefreshCw, Server, ShieldAlert, ShieldCheck, Trash2, X } from "lucide-react";
import { api, type SecurityServer, type SecurityStats, type SecurityTask } from "@/lib/api";
import { JsonBlock } from "@/components/json-block";
import { MetricCard } from "@/components/metric-card";
import { StatusBadge } from "@/components/status-badge";
import { StatusPill } from "@/components/status-pill";
import { shortText, timeAgo } from "@/lib/utils";

const emptyServerForm = {
  name: "",
  host: "",
  port: 22,
  username: "",
  password: "",
  ssh_key: "",
  os_type: "ubuntu"
};

const emptyStats: SecurityStats = {
  total: 0,
  hardened: 0,
  partial: 0,
  none: 0,
  unchecked: 0
};

function isRunningTask(task: SecurityTask | null) {
  return task?.status === "pending" || task?.status === "running";
}

function RunCheckButton({
  serverId,
  onTaskUpdate,
  onDone
}: {
  serverId: string;
  onTaskUpdate: (task: SecurityTask) => void;
  onDone: () => Promise<void> | void;
}) {
  const [task, setTask] = useState<SecurityTask | null>(null);
  const running = isRunningTask(task);

  const run = async (event: MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    if (!serverId || running) return;
    try {
      const started = await api.securityRunCheck(serverId);
      setTask(started);
      onTaskUpdate(started);
    } catch (error) {
      setTask({
        id: "local-error",
        server_id: serverId,
        status: "failed",
        created_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        report_id: null,
        error: String(error)
      });
    }
  };

  useEffect(() => {
    if (!task || !isRunningTask(task)) return;
    const iv = setInterval(async () => {
      try {
        const updated = await api.securityTask(task.id);
        setTask(updated);
        onTaskUpdate(updated);
        if (updated.status === "completed" || updated.status === "failed") {
          clearInterval(iv);
          await onDone();
        }
      } catch (error) {
        clearInterval(iv);
        setTask((current) =>
          current
            ? {
                ...current,
                status: "failed",
                completed_at: new Date().toISOString(),
                error: String(error)
              }
            : current
        );
        await onDone();
      }
    }, 2000);
    return () => clearInterval(iv);
  }, [task, onDone, onTaskUpdate]);

  return (
    <button
      onClick={run}
      disabled={!serverId || running}
      className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-border px-2.5 text-xs font-medium transition-colors hover:bg-orange-50 disabled:cursor-wait disabled:opacity-60"
    >
      {running ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
      {running ? "Checking" : "Check"}
    </button>
  );
}

export default function SecurityPage() {
  const router = useRouter();
  const [stats, setStats] = useState<SecurityStats>(emptyStats);
  const [servers, setServers] = useState<SecurityServer[]>([]);
  const [connected, setConnected] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddServer, setShowAddServer] = useState(false);
  const [serverForm, setServerForm] = useState(emptyServerForm);
  const [busy, setBusy] = useState(false);
  const [busyServerId, setBusyServerId] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<Record<string, unknown> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [agents, statRows, serverRows] = await Promise.all([
        api.agentsStatus(),
        api.securityStats().catch((error) => ({ error: String(error) })),
        api.securityServers().catch(() => [])
      ]);
      setConnected(Boolean(agents.find((agent) => agent.key === "security")?.connected));
      setStats("total" in statRows ? statRows : emptyStats);
      setServers(serverRows);
    } finally {
      setLoading(false);
    }
  }, []);

  const setFormValue = (key: keyof typeof emptyServerForm, value: string | number) => {
    setServerForm((current) => ({ ...current, [key]: value }));
  };

  const createServer = async () => {
    if (busy) return;
    const payload = {
      name: serverForm.name.trim(),
      host: serverForm.host.trim(),
      port: Number(serverForm.port) || 22,
      username: serverForm.username.trim(),
      password: serverForm.password.trim() || null,
      ssh_key: serverForm.ssh_key.trim() || null,
      os_type: serverForm.os_type
    };
    if (!payload.name || !payload.host || !payload.username || (!payload.password && !payload.ssh_key)) {
      setActionResult({ status: "error", message: "Name, host, username, and password or SSH key are required." });
      return;
    }
    setBusy(true);
    try {
      const response = await api.securityCreateServer(payload);
      setActionResult({ status: "created", server: response });
      setServerForm(emptyServerForm);
      setShowAddServer(false);
      await refresh();
    } catch (error) {
      setActionResult({ status: "error", message: String(error) });
    } finally {
      setBusy(false);
    }
  };

  const deleteServer = async (serverId: string, name: unknown) => {
    if (!serverId || busyServerId) return;
    if (!window.confirm(`Delete server ${shortText(name, serverId)}?`)) return;
    setBusyServerId(serverId);
    try {
      const response = await api.securityDeleteServer(serverId);
      setActionResult({ status: "deleted", server_id: serverId, response });
      await refresh();
    } catch (error) {
      setActionResult({ status: "error", message: String(error) });
    } finally {
      setBusyServerId(null);
    }
  };

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 15_000);
    return () => clearInterval(iv);
  }, [refresh]);

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
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Security</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Hardening posture</h1>
          <p className="mt-1 text-sm text-muted-foreground">Security baseline status from the hardening and Wazuh child agent.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill connected={connected} />
          <button
            onClick={() => setShowAddServer((current) => !current)}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            {showAddServer ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            {showAddServer ? "Close" : "Add Server"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Total Servers" value={Number(stats.total)} icon={Server} tone="slate" />
        <MetricCard label="Hardened" value={Number(stats.hardened)} sub="All checks pass" icon={ShieldCheck} tone="emerald" />
        <MetricCard label="Partial" value={Number(stats.partial)} sub="Needs review" icon={ShieldAlert} tone="amber" />
        <MetricCard label="Not Hardened" value={Number(stats.none)} sub="Needs action" icon={ShieldAlert} tone="red" />
        <MetricCard label="Unchecked" value={Number(stats.unchecked)} sub="Never scanned" icon={ClipboardList} tone="slate" />
      </div>

      {showAddServer ? (
        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="mb-4">
            <h2 className="text-sm font-semibold">Add managed server</h2>
            <p className="mt-1 text-xs text-muted-foreground">Create a server record in the security child dashboard and run checks from here.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
              Name
              <input
                value={serverForm.name}
                onChange={(event) => setFormValue("name", event.target.value)}
                placeholder="VNGDC-SYS-SERVER"
                className="h-10 rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20"
              />
            </label>
            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
              OS type
              <select
                value={serverForm.os_type}
                onChange={(event) => setFormValue("os_type", event.target.value)}
                className="h-10 rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20"
              >
                <option value="ubuntu">Ubuntu</option>
                <option value="windows">Windows</option>
                <option value="junos">Juniper Junos</option>
              </select>
            </label>
            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
              Host
              <input
                value={serverForm.host}
                onChange={(event) => setFormValue("host", event.target.value)}
                placeholder="10.0.0.10"
                className="h-10 rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20"
              />
            </label>
            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
              Port
              <input
                type="number"
                min={1}
                max={65535}
                value={serverForm.port}
                onChange={(event) => setFormValue("port", Number(event.target.value))}
                className="h-10 rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20"
              />
            </label>
            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
              Username
              <input
                value={serverForm.username}
                onChange={(event) => setFormValue("username", event.target.value)}
                placeholder="agent"
                className="h-10 rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20"
              />
            </label>
            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
              Password
              <input
                type="password"
                value={serverForm.password}
                onChange={(event) => setFormValue("password", event.target.value)}
                placeholder="Optional if SSH key is used"
                className="h-10 rounded-lg border border-border bg-background px-3 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary/20"
              />
            </label>
            <label className="grid gap-1.5 text-xs font-medium text-muted-foreground md:col-span-2">
              SSH private key
              <textarea
                value={serverForm.ssh_key}
                onChange={(event) => setFormValue("ssh_key", event.target.value)}
                placeholder="Optional"
                rows={3}
                className="rounded-lg border border-border bg-background px-3 py-2 font-mono text-xs text-foreground outline-none focus:ring-2 focus:ring-primary/20"
              />
            </label>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button
              onClick={createServer}
              disabled={busy}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-wait disabled:opacity-60"
            >
              <Plus className="h-4 w-4" />
              {busy ? "Creating" : "Create Server"}
            </button>
            <button
              onClick={() => {
                setServerForm(emptyServerForm);
                setShowAddServer(false);
              }}
              className="inline-flex h-10 items-center justify-center rounded-lg border border-border px-4 text-sm font-medium transition-colors hover:bg-secondary"
            >
              Cancel
            </button>
          </div>
        </section>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h2 className="text-sm font-semibold">Managed servers</h2>
            <span className="text-xs text-muted-foreground">{servers.length} rows</span>
          </div>
          <div className="divide-y divide-border">
            {servers.map((server, index) => {
              const serverId = shortText(server.id, "");
              const isDeleting = busyServerId === serverId;
              return (
                <div
                  key={serverId || String(index)}
                  onClick={() => (serverId ? router.push(`/security/servers/${encodeURIComponent(serverId)}`) : undefined)}
                  className="grid cursor-pointer gap-3 px-5 py-3.5 transition-colors hover:bg-secondary/60 lg:grid-cols-[minmax(0,1fr)_150px_120px_190px_24px] lg:items-center"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{shortText(server.name)}</p>
                    <p className="truncate font-mono text-xs text-muted-foreground">
                      {shortText(server.username)}@{shortText(server.host)}:{shortText(server.port)} - {shortText(server.os_type)}
                    </p>
                  </div>
                  <span className="text-xs text-muted-foreground">{timeAgo(typeof server.last_checked_at === "string" ? server.last_checked_at : null)}</span>
                  <StatusBadge status={server.last_status} size="sm" />
                  <div className="flex items-center gap-2 lg:justify-end">
                    <RunCheckButton
                      serverId={serverId}
                      onTaskUpdate={(task) => setActionResult({ status: task.status === "completed" ? "check_completed" : "checking", task })}
                      onDone={refresh}
                    />
                    <button
                      onClick={(event) => {
                        event.stopPropagation();
                        deleteServer(serverId, server.name);
                      }}
                      disabled={!serverId || isDeleting}
                      className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-border px-2.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 disabled:cursor-wait disabled:opacity-60"
                    >
                      {isDeleting ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                      {isDeleting ? "Deleting" : "Delete"}
                    </button>
                  </div>
                  <ChevronRight className="hidden h-4 w-4 text-muted-foreground lg:block" />
                </div>
              );
            })}
            {servers.length === 0 ? (
              <div className="px-5 py-12 text-center text-sm text-muted-foreground">No server rows returned by the security dashboard.</div>
            ) : null}
          </div>
        </section>

        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <h2 className="text-sm font-semibold">Security workflows</h2>
          <div className="mt-4 grid gap-3">
            <Link href="/security/vulnerabilities" className="rounded-lg border border-border bg-slate-50 p-4 transition-colors hover:border-orange-200 hover:bg-orange-50/60">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <ClipboardList className="h-4 w-4 text-primary" />
                Vulnerability assets
              </div>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">Review Wazuh CVE summary and affected assets.</p>
            </Link>
            <Link href="/security/radar" className="rounded-lg border border-border bg-slate-50 p-4 transition-colors hover:border-orange-200 hover:bg-orange-50/60">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <Radar className="h-4 w-4 text-primary" />
                Emerging CVE radar
              </div>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">Track recently published CVEs and likely exposure.</p>
            </Link>
          </div>
        </section>
      </div>

      {actionResult ? (
        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold">Last security action</h2>
            <button
              onClick={() => setActionResult(null)}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-border transition-colors hover:bg-secondary"
              aria-label="Clear action result"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <JsonBlock value={actionResult} maxHeight="max-h-48" />
        </section>
      ) : null}
    </div>
  );
}
