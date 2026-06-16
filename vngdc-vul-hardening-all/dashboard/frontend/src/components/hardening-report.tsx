"use client";

import { useState } from "react";
import type { Report, Section } from "@/lib/api";
import { CheckLevelIcon, StatusBadge } from "./status-badge";
import type { HardeningStatus } from "@/lib/utils";
import { timeAgo } from "@/lib/utils";
import { MarkdownMessage } from "@/components/markdown-message";

function SectionItem({ section }: { section: Section }) {
  const [open, setOpen] = useState(section.status === "fail");

  const totalChecks = section.pass_count + section.fail_count + section.warn_count;
  const pct = totalChecks > 0 ? Math.round((section.pass_count / totalChecks) * 100) : 0;

  const sectionColor: Record<string, string> = {
    pass: "border-l-emerald-500 bg-emerald-50",
    fail: "border-l-red-500 bg-red-50",
    warn: "border-l-amber-500 bg-amber-50",
    info: "border-l-blue-500 bg-blue-50",
  };

  return (
    <div className={`rounded-r-lg border-l-2 transition-all ${sectionColor[section.status] ?? sectionColor.info}`}>
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <div className="flex min-w-0 items-center gap-3">
          <svg
            className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-90" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          <span className="truncate text-sm font-medium">{section.name}</span>
        </div>

        <div className="ml-3 flex shrink-0 items-center gap-3">
          {section.fail_count > 0 && (
            <span className="hidden text-xs font-medium text-red-700 sm:inline">{section.fail_count} issues</span>
          )}
          <div className="hidden items-center gap-1.5 sm:flex">
            <div className="h-1.5 w-20 overflow-hidden rounded-full bg-white/80">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${pct}%`,
                  background: pct === 100 ? "#059669" : pct > 60 ? "#d97706" : "#dc2626",
                }}
              />
            </div>
            <span className="w-8 text-right text-xs text-muted-foreground">{pct}%</span>
          </div>
          <StatusBadge status={section.status as HardeningStatus} size="sm" />
        </div>
      </button>

      {open && section.checks.length > 0 && (
        <div className="space-y-1.5 border-t border-white/70 px-4 pb-3 pt-2">
          {section.checks.map((c, i) => (
            <div key={i} className="flex items-start gap-2 text-sm">
              <CheckLevelIcon level={c.level} />
              <span
                className={
                  c.level === "fail"
                    ? "text-red-800"
                    : c.level === "warn"
                      ? "text-amber-800"
                      : c.level === "pass"
                        ? "text-emerald-800"
                        : "text-muted-foreground"
                }
              >
                {c.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function HardeningReport({ report }: { report: Report }) {
  const sections = report.sections ?? [];
  const scoredSections = sections.filter((s) => s.status === "pass" || s.status === "fail" || s.status === "warn");
  const totalSections = scoredSections.length;
  const passSections = scoredSections.filter((s) => s.status === "pass").length;
  const failSections = scoredSections.filter((s) => s.status === "fail").length;
  const warnSections = scoredSections.filter((s) => s.status === "warn").length;
  const pct = totalSections > 0 ? Math.round((passSections / totalSections) * 100) : 0;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-card p-4 shadow-sm">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-medium">
              {passSections} / {totalSections} sections passed
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Checked {timeAgo(report.checked_at)}
              {report.duration_seconds ? ` - ${report.duration_seconds}s` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={`/api/servers/${report.server_id}/reports/${report.id}/export.xlsx`}
              download
              className="inline-flex items-center rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              XLSX
            </a>
            <StatusBadge status={report.status as HardeningStatus} />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${pct}%`,
                background: pct === 100 ? "#059669" : pct > 60 ? "#d97706" : "#dc2626",
              }}
            />
          </div>
          <span className="w-10 text-right text-sm font-semibold tabular-nums">{pct}%</span>
        </div>

        <div className="mt-3 flex gap-4">
          {[
            { label: "Pass", count: passSections, color: "text-emerald-700" },
            { label: "Fail", count: failSections, color: "text-red-700" },
            { label: "Warn", count: warnSections, color: "text-amber-700" },
          ].map((item) => (
            <div key={item.label} className="text-xs">
              <span className={`font-semibold ${item.color}`}>{item.count}</span>
              <span className="ml-1 text-muted-foreground">{item.label}</span>
            </div>
          ))}
        </div>
      </div>

      {report.error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          <p className="mb-1 font-medium">Check failed</p>
          <pre className="whitespace-pre-wrap break-all text-xs text-red-700">{report.error}</pre>
        </div>
      ) : (
        <div className="space-y-2">
          {sections.map((section, i) => (
            <SectionItem key={i} section={section} />
          ))}
        </div>
      )}

      {report.analysis && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="mb-3 flex items-center gap-2">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-blue-200 bg-white text-primary">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.7 17h4.6M12 3v1m6.4 1.6l-.7.7M21 12h-1M4 12H3m3.3-5.7l-.7-.7m2.8 9.9a5 5 0 117.1 0l-.6.6A3.4 3.4 0 0014 18.5V19a2 2 0 11-4 0v-.5c0-.9-.4-1.8-1-2.4l-.6-.6z" />
              </svg>
            </div>
            <p className="text-sm font-medium text-primary">AI analysis</p>
            <span className="text-xs text-muted-foreground">MiniMax Security Agent</span>
          </div>
          <MarkdownMessage content={report.analysis} />
        </div>
      )}
    </div>
  );
}
