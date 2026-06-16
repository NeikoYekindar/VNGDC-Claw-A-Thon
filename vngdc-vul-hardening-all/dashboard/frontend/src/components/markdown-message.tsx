"use client";

import React from "react";

function inline(text: string): React.ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index} className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.92em] text-slate-800">{part.slice(1, -1)}</code>;
    }
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

function splitTableRow(line: string) {
  return line.replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());
}

function isTableSeparator(line: string) {
  return /^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$/.test(line);
}

function isSpecialLine(line: string) {
  return (
    /^#{1,3}\s+/.test(line) ||
    /^[-*]\s+/.test(line) ||
    /^\d+\.\s+/.test(line) ||
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
        </pre>,
      );
      continue;
    }

    if (trimmed.startsWith("# ")) {
      nodes.push(<h1 key={nodes.length} className="mb-3 mt-1 text-2xl font-semibold tracking-tight text-foreground">{inline(trimmed.slice(2))}</h1>);
      i += 1;
      continue;
    }

    if (trimmed.startsWith("## ")) {
      nodes.push(<h2 key={nodes.length} className="mb-2 mt-5 text-lg font-semibold text-foreground">{inline(trimmed.slice(3))}</h2>);
      i += 1;
      continue;
    }

    if (trimmed.startsWith("### ")) {
      nodes.push(<h3 key={nodes.length} className="mb-2 mt-4 text-sm font-semibold text-foreground">{inline(trimmed.slice(4))}</h3>);
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
              <tr>{headers.map((header, index) => <th key={index} className="px-3 py-2 text-left font-semibold text-slate-700">{inline(header)}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {row.map((cell, cellIndex) => <td key={cellIndex} className="px-3 py-2 text-slate-700">{inline(cell)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    if (/^[-*]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*]\s+/, ""));
        i += 1;
      }
      nodes.push(
        <ul key={nodes.length} className="my-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
          {items.map((item, index) => <li key={index}>{inline(item)}</li>)}
        </ul>,
      );
      continue;
    }

    if (/^\d+\.\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+\.\s+/, ""));
        i += 1;
      }
      nodes.push(
        <ol key={nodes.length} className="my-2 list-decimal space-y-1 pl-5 text-sm leading-6 text-slate-700">
          {items.map((item, index) => <li key={index}>{inline(item)}</li>)}
        </ol>,
      );
      continue;
    }

    const paragraphLines = [trimmed];
    i += 1;
    while (i < lines.length && lines[i].trim() && !isSpecialLine(lines[i].trim())) {
      paragraphLines.push(lines[i].trim());
      i += 1;
    }
    const paragraph = paragraphLines.join(" ");
    const isBreadcrumb = paragraph.endsWith(">");
    nodes.push(
      <p key={nodes.length} className={isBreadcrumb ? "mb-3 text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground" : "my-2 text-sm leading-6 text-slate-700"}>
        {inline(paragraph)}
      </p>,
    );
  }

  return <div className="max-w-none">{nodes}</div>;
}
