"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { HardeningReport } from "@/components/hardening-report";
import { StatusBadge } from "@/components/status-badge";
import { api, type Report, type Server, type Task } from "@/lib/api";
import { osTypeLabel, timeAgo } from "@/lib/utils";
import type { HardeningStatus } from "@/lib/utils";

function ServerIcon({ os }: { os: string }) {
  const tone =
    os === "ubuntu"
      ? "border-orange-200 bg-orange-50 text-orange-700"
      : os === "junos"
        ? "border-emerald-200 bg-emerald-50 text-emerald-700"
        : "border-blue-200 bg-blue-50 text-blue-700";

  return (
    <div className={`flex h-10 w-10 items-center justify-center rounded-lg border ${tone}`}>
      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 7h14M7 7v10m10-10v10M5 17h14M8 11h.01M8 14h.01M16 11h.01M16 14h.01" />
      </svg>
    </div>
  );
}

export default function ServerDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { id } = params;

  const [server, setServer] = useState<Server | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [activeReportId, setActiveReportId] = useState<string | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [srv, reps] = await Promise.all([
        api.server(id),
        api.reports(id).catch(() => [] as Report[]),
      ]);
      setServer(srv);
      setReports(reps);
      if (!activeReportId && reps.length > 0) setActiveReportId(reps[0].id);
    } finally {
      setLoading(false);
    }
  }, [id, activeReportId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runCheck = async () => {
    try {
      const t = await api.runCheck(id);
      setTask(t);
    } catch (e) {
      alert(String(e));
    }
  };

  useEffect(() => {
    if (!task || task.status === "completed" || task.status === "failed") return;
    const iv = setInterval(async () => {
      try {
        const updated = await api.task(task.id);
        setTask(updated);
        if (updated.status === "completed" || updated.status === "failed") {
          clearInterval(iv);
          await refresh();
        }
      } catch {
        setTask((prev) =>
          prev
            ? {
                ...prev,
                status: "failed",
                completed_at: new Date().toISOString(),
                error: "Lost connection while polling task status. Refreshing report list.",
              }
            : prev,
        );
        await refresh();
        clearInterval(iv);
      }
    }, 2000);
    return () => clearInterval(iv);
  }, [task, refresh]);

  const deleteServer = async () => {
    if (!confirm(`Delete server "${server?.name}"? This cannot be undone.`)) return;
    setDeleting(true);
    await api.deleteServer(id);
    router.push("/");
  };

  const displayedReport = reports.find((r) => r.id === activeReportId) ?? reports[0] ?? null;
  const isRunning = task?.status === "pending" || task?.status === "running";

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <svg className="h-6 w-6 animate-spin text-primary" viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.6m15.3 2A8 8 0 004.6 9m0 0H9m11 11v-5h-.6m0 0a8 8 0 01-15.4-2m15.4 2H15" />
        </svg>
      </div>
    );
  }

  if (!server) {
    return <div className="py-16 text-center text-muted-foreground">Server not found</div>;
  }

  return (
    <div className="max-w-5xl space-y-6">
      <div>
        <button
          onClick={() => router.push("/")}
          className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
          </svg>
          Back to Hardening
        </button>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            <ServerIcon os={server.os_type} />
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-2xl font-semibold tracking-tight">{server.name}</h1>
                <StatusBadge status={server.last_status as HardeningStatus} />
              </div>
              <p className="mt-0.5 font-mono text-sm text-muted-foreground">
                {server.username}@{server.host}:{server.port}
                <span className="ml-2 font-sans text-muted-foreground/80">
                  - {osTypeLabel(server.os_type)}
                </span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={runCheck}
              disabled={isRunning}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isRunning ? (
                <>
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.6m15.3 2A8 8 0 004.6 9m0 0H9m11 11v-5h-.6m0 0a8 8 0 01-15.4-2m15.4 2H15" />
                  </svg>
                  Running
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3l7 3v5c0 4.4-2.9 8.4-7 9.7-4.1-1.3-7-5.3-7-9.7V6l7-3z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-5" />
                  </svg>
                  Run Hardening Check
                </>
              )}
            </button>
            <button
              onClick={deleteServer}
              disabled={deleting}
              className="h-10 rounded-lg border border-red-200 px-3 text-sm text-red-700 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Delete
            </button>
          </div>
        </div>

        {isRunning ? (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-sm text-amber-800">
            <svg className="h-4 w-4 shrink-0 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.6m15.3 2A8 8 0 004.6 9m0 0H9m11 11v-5h-.6m0 0a8 8 0 01-15.4-2m15.4 2H15" />
            </svg>
            Hardening check in progress. This may take up to 2 minutes.
          </div>
        ) : null}
        {task?.status === "failed" && task.error ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-800">
            <p className="font-medium">Hardening check failed</p>
            <p className="mt-1 break-all text-xs text-red-700">{task.error}</p>
          </div>
        ) : null}
      </div>

      {reports.length > 1 ? (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {reports.map((r, i) => (
            <button
              key={r.id}
              onClick={() => setActiveReportId(r.id)}
              className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                activeReportId === r.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-secondary text-muted-foreground hover:text-foreground"
              }`}
            >
              {i === 0 ? "Latest" : `#${reports.length - i}`} - {timeAgo(r.checked_at)}
            </button>
          ))}
        </div>
      ) : null}

      {displayedReport ? (
        <HardeningReport report={displayedReport} />
      ) : (
        <div className="rounded-lg border border-border bg-card p-12 text-center shadow-sm">
          <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-lg bg-secondary text-muted-foreground">
            <svg className="h-7 w-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p className="text-sm font-medium">No hardening report yet</p>
          <p className="mt-1 text-xs text-muted-foreground">Run a hardening check to scan this server.</p>
        </div>
      )}
    </div>
  );
}
