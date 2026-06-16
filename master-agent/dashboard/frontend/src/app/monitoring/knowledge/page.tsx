"use client";

import { useCallback, useEffect, useState } from "react";
import { BookOpen, Edit3, FileText, Plus, Save, Trash2, Upload } from "lucide-react";
import { api } from "@/lib/api";
import { JsonBlock } from "@/components/json-block";
import { MetricCard } from "@/components/metric-card";
import { cn, shortText } from "@/lib/utils";

function asArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? (value as Record<string, unknown>[]) : [];
}

export default function MonitoringKnowledgePage() {
  const [data, setData] = useState<Record<string, unknown>>({});
  const [filename, setFilename] = useState("runbook.md");
  const [content, setContent] = useState("");
  const [selectedName, setSelectedName] = useState("");
  const [busy, setBusy] = useState(false);
  const [reading, setReading] = useState(false);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setData(await api.monitoringKnowledge());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const files = asArray(data.files);
  const totalSize = files.reduce((sum, file) => sum + Number(file.size ?? 0), 0);

  const openKnowledge = async (name: string) => {
    if (!name || reading || busy) return;
    setReading(true);
    setResult(null);
    try {
      const response = await api.monitoringReadKnowledge(name);
      if (response.status === "error") {
        setResult(response);
        return;
      }
      setSelectedName(shortText(response.filename, name));
      setFilename(shortText(response.filename, name));
      setContent(typeof response.content === "string" ? response.content : "");
      setResult({ status: "ok", message: `Loaded ${shortText(response.filename, name)} for editing.` });
    } catch (error) {
      setResult({ status: "error", message: String(error) });
    } finally {
      setReading(false);
    }
  };

  const saveKnowledge = async () => {
    if (!filename.trim() || !content.trim() || busy) return;
    setBusy(true);
    try {
      const response = await api.monitoringUploadKnowledge(filename.trim(), content);
      setResult(response);
      if (response.status !== "error") {
        const savedName = shortText(response.filename, filename.trim());
        setSelectedName(savedName);
        setFilename(savedName);
        await refresh();
      }
    } catch (error) {
      setResult({ status: "error", message: String(error) });
    } finally {
      setBusy(false);
    }
  };

  const deleteKnowledge = async (name: string) => {
    if (!name || busy) return;
    setBusy(true);
    try {
      const response = await api.monitoringDeleteKnowledge(name);
      setResult(response);
      if (name === selectedName) {
        newDocument();
      }
      await refresh();
    } catch (error) {
      setResult({ status: "error", message: String(error) });
    } finally {
      setBusy(false);
    }
  };

  const readKnowledgeFile = async (file: File | null) => {
    if (!file) return;
    setSelectedName("");
    setFilename(file.name);
    setContent(await file.text());
    setResult({ status: "draft", message: `${file.name} loaded locally. Save to update the agent knowledge base.` });
  };

  const newDocument = () => {
    setSelectedName("");
    setFilename("runbook.md");
    setContent("");
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Monitoring</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Monitoring knowledge base</h1>
          <p className="mt-1 text-sm text-muted-foreground">Edit and save runbooks used by the monitoring child agent.</p>
        </div>
        <button
          onClick={refresh}
          className="inline-flex h-10 items-center justify-center rounded-lg border border-border px-4 text-sm font-medium transition-colors hover:bg-secondary"
        >
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <MetricCard label="Files" value={files.length} sub="Markdown knowledge entries" icon={BookOpen} tone="blue" />
        <MetricCard label="Size" value={`${Math.round(totalSize / 1024)} KB`} sub="Total file footprint" icon={FileText} tone="teal" />
        <MetricCard label="Editor" value="Edit" sub="Save overwrites selected file" icon={Edit3} tone="emerald" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
        <section className="overflow-hidden rounded-lg border border-border bg-card shadow-sm">
          <div className="flex items-center justify-between border-b border-border px-5 py-4">
            <h2 className="text-sm font-semibold">Knowledge files</h2>
            <span className="text-xs text-muted-foreground">{loading ? "Loading" : `${files.length} files`}</span>
          </div>
          <div className="divide-y divide-border">
            {files.map((file, index) => {
              const name = shortText(file.name, "");
              const active = Boolean(name && name === selectedName);
              return (
                <div
                  key={`${name}-${index}`}
                  className={cn(
                    "grid gap-3 px-5 py-3.5 sm:grid-cols-[minmax(0,1fr)_88px] sm:items-center",
                    active ? "bg-orange-50/60" : ""
                  )}
                >
                  <button type="button" onClick={() => openKnowledge(name)} className="min-w-0 text-left">
                    <p className="truncate text-sm font-medium">{shortText(file.name)}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{shortText(file.size, "0")} bytes</p>
                  </button>
                  <button
                    onClick={() => deleteKnowledge(name)}
                    disabled={!name || busy}
                    className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-border px-2 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </button>
                </div>
              );
            })}
            {files.length === 0 ? (
              <div className="px-5 py-12 text-center text-sm text-muted-foreground">No knowledge files returned.</div>
            ) : null}
          </div>
        </section>

        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-sm font-semibold">{selectedName ? "Edit knowledge document" : "Create knowledge document"}</h2>
              <p className="mt-1 text-xs text-muted-foreground">
                {selectedName ? `Editing ${selectedName}` : "Select a file from the list or start a new Markdown document."}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={newDocument}
                disabled={busy || reading}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border px-3 text-sm font-medium transition-colors hover:bg-secondary disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Plus className="h-4 w-4" />
                New
              </button>
              <label className="inline-flex h-9 cursor-pointer items-center justify-center gap-2 rounded-lg border border-border px-3 text-sm font-medium transition-colors hover:bg-secondary">
                <Upload className="h-4 w-4" />
                Load file
                <input
                  type="file"
                  accept=".md,text/markdown,text/plain"
                  className="hidden"
                  onChange={(event) => readKnowledgeFile(event.target.files?.[0] ?? null)}
                />
              </label>
            </div>
          </div>

          <div className="grid gap-3">
            <input
              value={filename}
              onChange={(event) => setFilename(event.target.value)}
              placeholder="runbook.md"
              className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
            />
            <textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              rows={18}
              placeholder={"# CPU Runbook\n\n- Check load average\n- Inspect top processes\n- Compare with recent deploys"}
              className="min-h-[440px] resize-y rounded-lg border border-border bg-background p-3 font-mono text-xs leading-5 outline-none focus:ring-2 focus:ring-primary/20"
            />
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <button
                onClick={saveKnowledge}
                disabled={!filename.trim() || !content.trim() || busy || reading}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Save className="h-4 w-4" />
                {busy ? "Saving" : selectedName ? "Save document" : "Create document"}
              </button>
              {result ? <JsonBlock value={result} maxHeight="max-h-48" /> : null}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
