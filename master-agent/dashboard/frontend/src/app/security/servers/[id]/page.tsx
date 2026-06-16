"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, RefreshCw, Server as ServerIconBase, ShieldCheck, Trash2 } from "lucide-react";
import { api, type SecurityReport, type SecurityServer, type SecurityTask } from "@/lib/api";
import { HardeningReport } from "@/components/hardening-report";
import { StatusBadge } from "@/components/status-badge";
import { cn, osTypeLabel, timeAgo } from "@/lib/utils";

function ServerIcon({ os }: { os: string }) {
  const tone =
    os === "ubuntu"
      ? "border-orange-200 bg-orange-50 text-orange-700"
      : os === "junos"
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : "border-blue-200 bg-blue-50 text-blue-700";

  return (
    <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg border", tone)}>
      <ServerIconBase className="h-5 w-5" />
    </div>
  );
}

function isRunningTask(task: SecurityTask | null) {
  return task?.status === "pending" || task?.status === "running";
}

export default function SecurityServerDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { id } = params;

  const [server, setServer] = useState<SecurityServer | null>(null);
  const [reports, setReports] = useState<SecurityReport[]>([]);
  const [activeReportId, setActiveReportId] = useState<string | null>(null);
  const [task, setTask] = useState<SecurityTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [srv, reps] = await Promise.all([api.securityServer(id), api.securityReports(id).catch(() => [] as SecurityReport[])]);
      setServer(srv);
      setReports(reps);
      if (!activeReportId && reps.length > 0) setActiveReportId(reps[0].id);
      setError(null);
    } catch (refreshError) {
      setError(String(refreshError));
    } finally {
      setLoading(false);
    }
  }, [id, activeReportId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const iv = setInterval(refresh, isRunningTask(task) ? 5000 : 20000);
    return () => clearInterval(iv);
  }, [refresh, task]);

  const runCheck = async () => {
    try {
      const started = await api.securityRunCheck(id);
      setTask(started);
      setError(null);
    } catch (runError) {
      setError(String(runError));
    }
  };

  useEffect(() => {
    if (!task || !isRunningTask(task)) return;
    const iv = setInterval(async () => {
      try {
        const updated = await api.securityTask(task.id);
        setTask(updated);
        if (updated.status === "completed" || updated.status === "failed") {
          clearInterval(iv);
          if (updated.report_id) setActiveReportId(updated.report_id);
          await refresh();
        }
      } catch (pollError) {
        clearInterval(iv);
        setTask((current) =>
          current
            ? {
                ...current,
                status: "failed",
                completed_at: new Date().toISOString(),
                error: String(pollError)
              }
            : current
        );
        await refresh();
      }
    }, 2000);
    return () => clearInterval(iv);
  }, [task, refresh]);

  const deleteServer = async () => {
    if (!server) return;
    if (!window.confirm(`Delete server "${server.name}" and its reports?`)) return;
    setDeleting(true);
    try {
      await api.securityDeleteServer(id);
      router.push("/security");
    } catch (deleteError) {
      setError(String(deleteError));
      setDeleting(false);
    }
  };

  const displayedReport = reports.find((report) => report.id === activeReportId) ?? reports[0] ?? null;
  const running = isRunningTask(task);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  if (!server) {
    return (
      <div className="py-16 text-center">
        <p className="text-sm font-medium">Server not found</p>
        {error ? <p className="mt-2 text-xs text-red-600">{error}</p> : null}
        <button
          onClick={() => router.push("/security")}
          className="mt-4 inline-flex h-9 items-center justify-center rounded-lg border border-border px-3 text-sm font-medium transition-colors hover:bg-secondary"
        >
          Back to Hardening
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl space-y-6">
      <div>
        <button
          onClick={() => router.push("/security")}
          className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Hardening
        </button>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <ServerIcon os={server.os_type} />
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-semibold tracking-tight">{server.name}</h1>
                <StatusBadge status={server.last_status} />
              </div>
              <p className="mt-0.5 font-mono text-sm text-muted-foreground">
                {server.username}@{server.host}:{server.port}
                <span className="ml-2 font-sans text-muted-foreground/80">- {osTypeLabel(server.os_type)}</span>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">Last checked {timeAgo(server.last_checked_at)}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              onClick={runCheck}
              disabled={running}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-wait disabled:opacity-60"
            >
              {running ? <RefreshCw className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              {running ? "Running" : "Run Hardening Check"}
            </button>
            <button
              onClick={deleteServer}
              disabled={deleting}
              className="inline-flex h-10 items-center gap-2 rounded-lg border border-red-200 px-3 text-sm font-medium text-red-700 transition-colors hover:bg-red-50 disabled:cursor-wait disabled:opacity-60"
            >
              {deleting ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
              {deleting ? "Deleting" : "Delete"}
            </button>
          </div>
        </div>

        {running ? (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
            <RefreshCw className="h-4 w-4 shrink-0 animate-spin" />
            Hardening check in progress. Dashboard is polling task status automatically.
          </div>
        ) : null}
        {task?.status === "failed" && task.error ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-800">
            <p className="font-medium">Hardening check failed</p>
            <p className="mt-1 break-all text-xs text-red-700">{task.error}</p>
          </div>
        ) : null}
        {error ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-800">
            {error}
          </div>
        ) : null}
      </div>

      {reports.length > 1 ? (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {reports.map((report, index) => (
            <button
              key={report.id}
              onClick={() => setActiveReportId(report.id)}
              className={cn(
                "shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                activeReportId === report.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              )}
            >
              {index === 0 ? "Latest" : `#${reports.length - index}`} - {timeAgo(report.checked_at)}
            </button>
          ))}
        </div>
      ) : null}

      {displayedReport ? (
        <HardeningReport report={displayedReport} />
      ) : (
        <div className="rounded-lg border border-border bg-card p-12 text-center shadow-sm">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-lg bg-secondary text-muted-foreground">
            <ShieldCheck className="h-7 w-7" />
          </div>
          <p className="text-sm font-medium">No hardening report yet</p>
          <p className="mt-1 text-xs text-muted-foreground">Run a hardening check to scan this server.</p>
        </div>
      )}
    </div>
  );
}
