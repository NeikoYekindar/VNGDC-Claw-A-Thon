"use client";

import { useCallback, useEffect, useState } from "react";
import { Server, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { JsonBlock } from "@/components/json-block";
import { MetricCard } from "@/components/metric-card";
import { shortText } from "@/lib/utils";

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : [];
}

export default function MonitoringInventoryPage() {
  const [data, setData] = useState<Record<string, unknown>>({});
  const [filter, setFilter] = useState("all");
  const [csvContent, setCsvContent] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setData(await api.monitoringInventory(filter === "all" ? undefined : filter));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const rows = asArray(data.inventory);

  const uploadInventory = async () => {
    if (!csvContent.trim() || uploading) return;
    setUploading(true);
    try {
      const result = await api.monitoringUploadInventory(csvContent);
      setUploadResult(result);
      await refresh();
    } catch (error) {
      setUploadResult({ status: "error", message: String(error) });
    } finally {
      setUploading(false);
    }
  };

  const readCsvFile = async (file: File | null) => {
    if (!file) return;
    setCsvContent(await file.text());
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Monitoring</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Monitored inventory</h1>
          <p className="mt-1 text-sm text-muted-foreground">Assets known by the monitoring child agent.</p>
        </div>
        <div className="flex rounded-lg border border-border bg-card p-1">
          {["all", "server", "network"].map((item) => (
            <button
              key={item}
              onClick={() => setFilter(item)}
              className={`h-8 rounded-md px-3 text-xs font-medium capitalize transition-colors ${
                filter === item ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-secondary hover:text-foreground"
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard label="Rows" value={rows.length} sub="Current filtered result" icon={Server} tone="blue" />
        <MetricCard label="Servers" value={rows.filter((row) => row.type !== "network").length} sub="Compute assets" icon={Server} tone="emerald" />
        <MetricCard label="Network" value={rows.filter((row) => row.type === "network").length} sub="Network assets" icon={Server} tone="teal" />
      </div>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold">Inventory CSV import</h2>
            <p className="mt-1 text-xs text-muted-foreground">Required columns: hostname, ip, type, monitoring_source</p>
          </div>
          <label className="inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-3 text-sm font-medium transition-colors hover:bg-secondary">
            <Upload className="h-4 w-4" />
            Select CSV
            <input
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={(event) => readCsvFile(event.target.files?.[0] ?? null)}
            />
          </label>
        </div>
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_220px]">
          <textarea
            value={csvContent}
            onChange={(event) => setCsvContent(event.target.value)}
            rows={5}
            placeholder={"hostname,ip,type,monitoring_source\nweb-01,10.0.0.10,server,prometheus\nsw-core,10.0.0.1,network,checkmk"}
            className="min-h-32 resize-y rounded-lg border border-border bg-background p-3 font-mono text-xs outline-none focus:ring-2 focus:ring-primary/20"
          />
          <div className="flex flex-col gap-3">
            <button
              onClick={uploadInventory}
              disabled={!csvContent.trim() || uploading}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <Upload className="h-4 w-4" />
              {uploading ? "Uploading" : "Upload inventory"}
            </button>
            {uploadResult ? <JsonBlock value={uploadResult} maxHeight="max-h-40" /> : null}
          </div>
        </div>
      </section>

      <section className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <h2 className="text-sm font-semibold">Inventory table</h2>
          <span className="text-xs text-muted-foreground">{loading ? "Loading" : `${rows.length} rows`}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-border text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">Hostname</th>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">IP</th>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">Type</th>
                <th className="px-5 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border bg-card">
              {rows.map((row, index) => (
                <tr key={`${shortText(row.ip)}-${index}`} className="hover:bg-secondary/60">
                  <td className="px-5 py-3 font-medium">{shortText(row.hostname)}</td>
                  <td className="px-5 py-3 font-mono text-xs text-muted-foreground">{shortText(row.ip)}</td>
                  <td className="px-5 py-3">{shortText(row.type, "server")}</td>
                  <td className="px-5 py-3 text-muted-foreground">{shortText(row.monitoring_source)}</td>
                </tr>
              ))}
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-5 py-12 text-center text-sm text-muted-foreground">
                    No inventory rows returned.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
