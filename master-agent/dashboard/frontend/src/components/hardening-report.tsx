"use client";

import { useState } from "react";
import { Download, Lightbulb, ChevronRight } from "lucide-react";
import { api, type SecurityReport, type SecuritySection } from "@/lib/api";
import { MarkdownMessage } from "@/components/markdown-message";
import { CheckLevelIcon, StatusBadge } from "@/components/status-badge";
import { cn, timeAgo } from "@/lib/utils";

function count(value: unknown) {
  return Number(value) || 0;
}

function SectionItem({ section }: { section: SecuritySection }) {
  const [open, setOpen] = useState(section.status === "fail");
  const checks = Array.isArray(section.checks) ? section.checks : [];
  const passCount = count(section.pass_count);
  const failCount = count(section.fail_count);
  const warnCount = count(section.warn_count);
  const totalChecks = passCount + failCount + warnCount;
  const pct = totalChecks > 0 ? Math.round((passCount / totalChecks) * 100) : 0;

  const sectionColor: Record<string, string> = {
    pass: "border-l-emerald-500 bg-emerald-50",
    fail: "border-l-red-500 bg-red-50",
    warn: "border-l-amber-500 bg-amber-50",
    info: "border-l-blue-500 bg-blue-50"
  };

  return (
    <div className={cn("rounded-r-lg border-l-2 transition-all", sectionColor[String(section.status)] ?? sectionColor.info)}>
      <button onClick={() => setOpen(!open)} className="flex w-full items-center justify-between px-4 py-3 text-left">
        <div className="flex min-w-0 items-center gap-3">
          <ChevronRight className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform", open ? "rotate-90" : "")} />
          <span className="truncate text-sm font-medium">{section.name}</span>
        </div>

        <div className="ml-3 flex shrink-0 items-center gap-3">
          {failCount > 0 ? <span className="hidden text-xs font-medium text-red-700 sm:inline">{failCount} issues</span> : null}
          <div className="hidden items-center gap-1.5 sm:flex">
            <div className="h-1.5 w-20 overflow-hidden rounded-full bg-white/80">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${pct}%`,
                  background: pct === 100 ? "#059669" : pct > 60 ? "#d97706" : "#dc2626"
                }}
              />
            </div>
            <span className="w-8 text-right text-xs text-muted-foreground">{pct}%</span>
          </div>
          <StatusBadge status={section.status} size="sm" />
        </div>
      </button>

      {open ? (
        <div className="space-y-1.5 border-t border-white/70 px-4 pb-3 pt-2">
          {checks.length > 0 ? (
            checks.map((check, index) => (
              <div key={`${check.level}-${index}`} className="flex items-start gap-2 text-sm">
                <CheckLevelIcon level={check.level} />
                <span
                  className={
                    check.level === "fail"
                      ? "text-red-800"
                      : check.level === "warn"
                        ? "text-amber-800"
                        : check.level === "pass"
                          ? "text-emerald-800"
                          : "text-muted-foreground"
                  }
                >
                  {check.message}
                </span>
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">No checks returned for this section.</p>
          )}
        </div>
      ) : null}
    </div>
  );
}

export function HardeningReport({ report }: { report: SecurityReport }) {
  const sections = Array.isArray(report.sections) ? report.sections : [];
  const scoredSections = sections.filter((section) => ["pass", "fail", "warn"].includes(String(section.status)));
  const totalSections = scoredSections.length;
  const passSections = scoredSections.filter((section) => section.status === "pass").length;
  const failSections = scoredSections.filter((section) => section.status === "fail").length;
  const warnSections = scoredSections.filter((section) => section.status === "warn").length;
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
              href={api.securityReportExportUrl(report.server_id, report.id)}
              download
              className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
            >
              <Download className="h-3.5 w-3.5" />
              XLSX
            </a>
            <StatusBadge status={report.status} />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-secondary">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${pct}%`,
                background: pct === 100 ? "#059669" : pct > 60 ? "#d97706" : "#dc2626"
              }}
            />
          </div>
          <span className="w-10 text-right text-sm font-semibold tabular-nums">{pct}%</span>
        </div>

        <div className="mt-3 flex gap-4">
          {[
            { label: "Pass", count: passSections, color: "text-emerald-700" },
            { label: "Fail", count: failSections, color: "text-red-700" },
            { label: "Warn", count: warnSections, color: "text-amber-700" }
          ].map((item) => (
            <div key={item.label} className="text-xs">
              <span className={cn("font-semibold", item.color)}>{item.count}</span>
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
          {sections.length > 0 ? (
            sections.map((section, index) => <SectionItem key={`${section.name}-${index}`} section={section} />)
          ) : (
            <div className="rounded-lg border border-border bg-card p-8 text-center text-sm text-muted-foreground">
              No parsed sections in this report.
            </div>
          )}
        </div>
      )}

      {report.analysis ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <div className="mb-3 flex items-center gap-2">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-blue-200 bg-white text-primary">
              <Lightbulb className="h-3.5 w-3.5" />
            </div>
            <p className="text-sm font-medium text-primary">AI analysis</p>
            <span className="text-xs text-muted-foreground">MiniMax Security Agent</span>
          </div>
          <MarkdownMessage content={report.analysis} />
        </div>
      ) : null}
    </div>
  );
}
