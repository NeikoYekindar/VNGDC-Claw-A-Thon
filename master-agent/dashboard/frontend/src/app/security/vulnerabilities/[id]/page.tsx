"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Download, RefreshCw, Server as ServerIconBase } from "lucide-react";
import { api, type SecurityServer, type VulnerabilityAssetDetail } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { VulnerabilityAssetDetailPanel } from "@/components/vulnerability-asset-detail";
import { cn, osTypeLabel } from "@/lib/utils";

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

export default function SecurityVulnerabilityAssetPage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const { id } = params;

  const [server, setServer] = useState<SecurityServer | null>(null);
  const [detail, setDetail] = useState<VulnerabilityAssetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const [srv, assetDetail] = await Promise.all([api.securityServer(id), api.securityVulnerabilityAsset(id)]);
      setServer(srv);
      setDetail(assetDetail);
    } catch (refreshError) {
      setError(String(refreshError));
      setDetail(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const runVulnerabilityRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      await api.securityRefreshVulnerabilities(true, false);
      await refresh();
    } catch (refreshError) {
      setError(String(refreshError));
    } finally {
      setRefreshing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  if (!server) {
    return (
      <div className="max-w-5xl space-y-4">
        <button
          onClick={() => router.push("/security/vulnerabilities")}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Vulnerabilities
        </button>
        <div className="rounded-lg border border-border bg-card p-12 text-center text-sm text-muted-foreground shadow-sm">
          Server not found.
          {error ? <p className="mt-2 break-all text-xs text-red-600">{error}</p> : null}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl space-y-6">
      <div>
        <button
          onClick={() => router.push("/security/vulnerabilities")}
          className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Vulnerabilities
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
                {server.host}:{server.port}
                <span className="ml-2 font-sans text-muted-foreground/80">- {osTypeLabel(server.os_type)}</span>
              </p>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <a
              href={api.securityVulnerabilityAssetExportUrl(id)}
              className="inline-flex h-10 items-center gap-2 rounded-lg border border-border bg-card px-4 text-sm font-medium transition-colors hover:bg-secondary"
            >
              <Download className="h-4 w-4" />
              XLSX
            </a>
            <button
              onClick={runVulnerabilityRefresh}
              disabled={refreshing}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-wait disabled:opacity-60"
            >
              <RefreshCw className={cn("h-4 w-4", refreshing ? "animate-spin" : "")} />
              {refreshing ? "Refreshing" : "Rescan CVEs"}
            </button>
          </div>
        </div>

        {error ? (
          <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm text-red-800">
            <p className="font-medium">Vulnerability detail failed</p>
            <p className="mt-1 break-all text-xs text-red-700">{error}</p>
          </div>
        ) : null}
      </div>

      <VulnerabilityAssetDetailPanel detail={detail} loading={false} server={server} />
    </div>
  );
}
