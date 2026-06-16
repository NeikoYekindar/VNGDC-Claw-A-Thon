"use client";

import React from "react";

function inline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\[(?:CRITICAL|ERROR|WARNING|INFO|HIGH|MEDIUM|LOW)\])/gi).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={index} className="font-semibold text-foreground">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={index} className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.92em] text-slate-800">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (/^\[(CRITICAL|ERROR|WARNING|INFO|HIGH|MEDIUM|LOW)\]$/i.test(part)) {
      const level = part.slice(1, -1);
      return (
        <span key={index} className={severityBadgeClass(level)}>
          {level.toUpperCase()}
        </span>
      );
    }
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

function textKey(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function severityClass(value: unknown) {
  const key = textKey(String(value ?? ""));
  if (key.includes("critical") || key.includes("fail") || key.includes("error")) {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (key.includes("high")) {
    return "border-orange-200 bg-orange-50 text-orange-700";
  }
  if (key.includes("warning") || key.includes("warn") || key.includes("medium") || key.includes("pending")) {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (key.includes("info") || key.includes("low")) {
    return "border-blue-200 bg-blue-50 text-blue-700";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function severityAccentClass(value: unknown) {
  const key = textKey(String(value ?? ""));
  if (key.includes("critical") || key.includes("fail") || key.includes("error")) return "border-l-red-500 bg-red-50/60";
  if (key.includes("high")) return "border-l-orange-500 bg-orange-50/60";
  if (key.includes("warning") || key.includes("warn") || key.includes("medium") || key.includes("pending")) return "border-l-amber-500 bg-amber-50/60";
  if (key.includes("info") || key.includes("low")) return "border-l-blue-500 bg-blue-50/60";
  return "border-l-sky-400 bg-sky-50/50";
}

function severityBadgeClass(value: unknown) {
  return `mx-0.5 inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${severityClass(value)}`;
}

function parseSectionTitle(line: string) {
  const trimmed = line.trim();
  if (!trimmed.endsWith(":") || trimmed.includes("://") || trimmed.includes("|")) return "";
  const title = trimmed.slice(0, -1).trim();
  if (title.length < 2 || title.length > 58) return "";
  return title;
}

function parseKeyValueLine(line: string) {
  const match = line.match(/^([^:]{2,48}):\s*(.+)$/);
  if (!match) return null;
  const label = match[1].trim();
  const value = match[2].trim();
  if (!label || !value || label.includes("://") || label.includes("|")) return null;
  return { label, value };
}

function shouldPromoteField(field: { label: string; value: string }) {
  const label = textKey(field.label);
  return (
    label.includes("tong") ||
    label.includes("total") ||
    label.includes("severity") ||
    label.includes("domain") ||
    label.includes("status") ||
    label.includes("file") ||
    label.includes("log") ||
    label.includes("scope") ||
    label.includes("risk") ||
    label.includes("summary") ||
    label.includes("impact") ||
    label.includes("nguyen nhan") ||
    label.includes("root cause") ||
    label.includes("tac dong") ||
    label.includes("huong xu ly") ||
    label.includes("command") ||
    label.includes("intent")
  );
}

function parseFindingLine(line: string, index?: string) {
  const detailed = line.match(/^\[([A-Za-z]+)\]\s+(\S+)\s+([^:]+):\s*(.+)$/);
  if (detailed) {
    return {
      index: index || "",
      severity: detailed[1],
      location: detailed[2],
      type: detailed[3],
      message: detailed[4]
    };
  }
  const compact = line.match(/^\[([A-Za-z]+)\]\s+(.+?)\s+-\s+(.+)$/);
  if (compact) {
    return {
      index: index || "",
      severity: compact[1],
      location: compact[2],
      type: compact[3],
      message: ""
    };
  }
  return null;
}

function phaseClasses(phase: string) {
  const key = textKey(phase);
  if (key.includes("remediate") || key.includes("fix")) {
    return {
      card: "border-red-200 border-l-red-500 bg-red-50/60",
      head: "border-red-200 bg-red-100/70 text-red-700"
    };
  }
  if (key.includes("investigate") || key.includes("analyze")) {
    return {
      card: "border-blue-200 border-l-blue-500 bg-blue-50/60",
      head: "border-blue-200 bg-blue-100/70 text-blue-700"
    };
  }
  if (key.includes("validate")) {
    return {
      card: "border-emerald-200 border-l-emerald-500 bg-emerald-50/60",
      head: "border-emerald-200 bg-emerald-100/70 text-emerald-700"
    };
  }
  return {
    card: "border-teal-200 border-l-teal-500 bg-teal-50/60",
    head: "border-teal-200 bg-teal-100/70 text-teal-700"
  };
}

function parseValuePairs(value: string) {
  const trimmed = value.trim();
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    const pairs: Array<{ key: string; value: string }> = [];
    const regex = /['"]?([^'",:{}]+)['"]?\s*:\s*['"]?([^,'"}]+)['"]?/g;
    let match;
    while ((match = regex.exec(trimmed.slice(1, -1))) !== null) {
      pairs.push({ key: match[1].trim(), value: match[2].trim() });
    }
    return pairs;
  }
  if (/^[A-Za-z_, -]+$/.test(trimmed) && trimmed.includes(",")) {
    return trimmed
      .split(",")
      .map((item) => ({ key: item.trim(), value: "" }))
      .filter((item) => item.key);
  }
  return [];
}

function FieldCard({ label, value }: { label: string; value: string }) {
  const pairs = parseValuePairs(value);
  return (
    <div className="my-2 grid gap-2 rounded-lg border border-border bg-slate-50/70 px-3 py-2.5 text-sm sm:grid-cols-[150px_minmax(0,1fr)]">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">{inline(label)}</div>
      <div className="min-w-0 font-medium text-slate-800">
        {pairs.length ? (
          <div className="flex flex-wrap gap-1.5">
            {pairs.map((pair) => (
              <span key={`${pair.key}-${pair.value}`} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${severityClass(pair.key)}`}>
                <span className="text-muted-foreground">{inline(pair.key)}</span>
                {pair.value ? <span className="font-semibold text-slate-900">{inline(pair.value)}</span> : null}
              </span>
            ))}
          </div>
        ) : (
          inline(value)
        )}
      </div>
    </div>
  );
}

function FindingCard({ finding }: { finding: NonNullable<ReturnType<typeof parseFindingLine>> }) {
  return (
    <article className={`my-2 rounded-lg border border-l-4 px-3 py-2.5 shadow-sm ${severityAccentClass(finding.severity)}`}>
      <div className="flex flex-wrap items-center gap-2">
        {finding.index ? <span className="text-xs font-semibold text-muted-foreground">#{finding.index}</span> : null}
        <span className={severityBadgeClass(finding.severity)}>{String(finding.severity).toUpperCase()}</span>
        <span className="font-mono text-xs font-semibold text-slate-800">{inline(finding.location || "-")}</span>
        <span className="rounded-full border border-border bg-white/80 px-2 py-0.5 text-xs font-medium text-muted-foreground">
          {inline(finding.type || "-")}
        </span>
      </div>
      {finding.message ? <p className="mt-2 text-sm leading-6 text-slate-700">{inline(finding.message)}</p> : null}
    </article>
  );
}

function CommandCard({ phase, command }: { phase: string; command: string }) {
  const cls = phaseClasses(phase);
  return (
    <div className={`my-3 overflow-hidden rounded-lg border border-l-4 ${cls.card}`}>
      <div className={`border-b px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.08em] ${cls.head}`}>{phase}</div>
      <code className="block whitespace-pre-wrap px-3 py-3 font-mono text-xs leading-5 text-slate-900">{command}</code>
    </div>
  );
}

function splitTableRow(line: string) {
  return line
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isTableSeparator(line: string) {
  return /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line);
}

function isSpecialLine(line: string) {
  const field = parseKeyValueLine(line);
  return (
    /^#{1,3}\s+/.test(line) ||
    /^[-*]\s+/.test(line) ||
    /^\d+\.\s+/.test(line) ||
    /^(Verify|Investigate|Remediate|Validate|Check|Analyze|Fix):\s+/i.test(line) ||
    Boolean(parseSectionTitle(line)) ||
    Boolean(parseFindingLine(line)) ||
    Boolean(field && shouldPromoteField(field)) ||
    line.startsWith("```") ||
    (line.trim().startsWith("|") && line.includes("|"))
  );
}

export function MarkdownMessage({ content }: { content: string }) {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const nodes: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const language = trimmed.slice(3).trim();
      const codeLines: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].trim().startsWith("```")) {
        codeLines.push(lines[i]);
        i += 1;
      }
      if (i < lines.length) i += 1;
      nodes.push(
        <pre key={nodes.length} className="my-3 overflow-x-auto rounded-lg border border-slate-200 bg-slate-950 p-3 text-xs text-slate-50">
          {language ? <div className="mb-2 text-[11px] uppercase tracking-wide text-slate-400">{language}</div> : null}
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      continue;
    }

    if (trimmed.startsWith("# ")) {
      nodes.push(
        <h1 key={nodes.length} className="mb-3 mt-1 border-b border-border pb-2 text-xl font-semibold tracking-tight text-foreground">
          {inline(trimmed.slice(2))}
        </h1>
      );
      i += 1;
      continue;
    }

    if (trimmed.startsWith("## ")) {
      nodes.push(
        <h2 key={nodes.length} className="mb-2 mt-5 border-b border-border pb-2 text-base font-semibold text-teal-700">
          {inline(trimmed.slice(3))}
        </h2>
      );
      i += 1;
      continue;
    }

    if (trimmed.startsWith("### ")) {
      nodes.push(
        <h3 key={nodes.length} className="mb-2 mt-4 text-sm font-semibold text-slate-700">
          {inline(trimmed.slice(4))}
        </h3>
      );
      i += 1;
      continue;
    }

    const sectionTitle = parseSectionTitle(trimmed);
    if (sectionTitle) {
      nodes.push(
        <div key={nodes.length} className="mb-2 mt-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.08em] text-teal-700">
          <span className="h-1.5 w-1.5 rounded-full bg-teal-500" />
          {inline(sectionTitle)}
        </div>
      );
      i += 1;
      continue;
    }

    const directCommand = trimmed.match(/^(Verify|Investigate|Remediate|Validate|Check|Analyze|Fix):\s*(.+)$/i);
    if (directCommand) {
      nodes.push(<CommandCard key={nodes.length} phase={directCommand[1]} command={directCommand[2]} />);
      i += 1;
      continue;
    }

    const directField = parseKeyValueLine(trimmed);
    if (directField && shouldPromoteField(directField)) {
      nodes.push(<FieldCard key={nodes.length} label={directField.label} value={directField.value} />);
      i += 1;
      continue;
    }

    const directFinding = parseFindingLine(trimmed);
    if (directFinding) {
      nodes.push(<FindingCard key={nodes.length} finding={directFinding} />);
      i += 1;
      continue;
    }

    if (trimmed.startsWith("|") && i + 1 < lines.length && isTableSeparator(lines[i + 1].trim())) {
      const headers = splitTableRow(trimmed);
      const rows: string[][] = [];
      i += 2;
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        rows.push(splitTableRow(lines[i].trim()));
        i += 1;
      }
      nodes.push(
        <div key={nodes.length} className="my-3 overflow-x-auto rounded-lg border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                {headers.map((header, index) => (
                  <th key={index} className="px-3 py-2 text-left font-semibold text-slate-700">
                    {inline(header)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => (
                    <td key={cellIndex} className="px-3 py-2 text-slate-700">
                      {inline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        const item = lines[i].trim().replace(/^[-*]\s+/, "");
        const command = item.match(/^(Verify|Investigate|Remediate|Validate|Check|Analyze|Fix):\s*(.+)$/i);
        const finding = parseFindingLine(item);
        const field = parseKeyValueLine(item);
        if (command || finding || (field && shouldPromoteField(field))) {
          if (items.length) {
            nodes.push(
              <ul key={nodes.length} className="my-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
                {items.map((listItem, index) => (
                  <li key={index}>{inline(listItem)}</li>
                ))}
              </ul>
            );
            items.length = 0;
          }
          if (command) nodes.push(<CommandCard key={nodes.length} phase={command[1]} command={command[2]} />);
          if (finding) nodes.push(<FindingCard key={nodes.length} finding={finding} />);
          if (field && shouldPromoteField(field)) nodes.push(<FieldCard key={nodes.length} label={field.label} value={field.value} />);
          i += 1;
          continue;
        }
        items.push(item);
        i += 1;
      }
      if (items.length) {
        nodes.push(
          <ul key={nodes.length} className="my-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
            {items.map((item, index) => (
              <li key={index}>{inline(item)}</li>
            ))}
          </ul>
        );
      }
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        const match = lines[i].trim().match(/^(\d+)\.\s+(.+)$/);
        const item = match?.[2] ?? "";
        const finding = parseFindingLine(item, match?.[1]);
        const field = parseKeyValueLine(item);
        if (finding || (field && shouldPromoteField(field))) {
          if (items.length) {
            nodes.push(
              <ol key={nodes.length} className="my-2 list-decimal space-y-1 pl-5 text-sm leading-6 text-slate-700">
                {items.map((listItem, index) => (
                  <li key={index}>{inline(listItem)}</li>
                ))}
              </ol>
            );
            items.length = 0;
          }
          if (finding) nodes.push(<FindingCard key={nodes.length} finding={finding} />);
          if (field && shouldPromoteField(field)) nodes.push(<FieldCard key={nodes.length} label={field.label} value={field.value} />);
          i += 1;
          continue;
        }
        items.push(item);
        i += 1;
      }
      if (items.length) {
        nodes.push(
          <ol key={nodes.length} className="my-2 list-decimal space-y-1 pl-5 text-sm leading-6 text-slate-700">
            {items.map((item, index) => (
              <li key={index}>{inline(item)}</li>
            ))}
          </ol>
        );
      }
      continue;
    }

    const paragraphLines = [trimmed];
    i += 1;
    while (i < lines.length && lines[i].trim() && !isSpecialLine(lines[i].trim())) {
      paragraphLines.push(lines[i].trim());
      i += 1;
    }
    const paragraph = paragraphLines.join(" ");
    nodes.push(
      <p key={nodes.length} className="my-2 text-sm leading-6 text-slate-700">
        {inline(paragraph)}
      </p>
    );
  }

  return <div className="max-w-none">{nodes}</div>;
}
