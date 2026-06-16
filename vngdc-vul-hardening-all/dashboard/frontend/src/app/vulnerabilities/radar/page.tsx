"use client";

import { useCallback, useEffect, useState } from "react";
import { EmergingCveRadar } from "@/components/emerging-cve-radar";
import { api, type EmergingCveResponse } from "@/lib/api";

export default function VulnerabilityRadarPage() {
  const [emerging, setEmerging] = useState<EmergingCveResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setEmerging(await api.emergingVulnerabilities(10, 14));
    } catch {
      setEmerging(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">CVE Radar</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Emerging and high-risk CVEs</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Track dangerous CVEs from CISA KEV, NVD, and EPSS, then compare relevance against the internal environment.
          </p>
        </div>
        <button
          onClick={refresh}
          disabled={loading}
          className="inline-flex h-10 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
        >
          {loading ? "Refreshing..." : "Refresh intelligence"}
        </button>
      </div>

      <EmergingCveRadar data={emerging} loading={loading} />
    </div>
  );
}
