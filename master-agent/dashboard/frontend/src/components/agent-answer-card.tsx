"use client";

import {
  Activity,
  Bot,
  BrainCircuit,
  ChevronDown,
  CheckCircle2,
  ClipboardList,
  HelpCircle,
  SearchCode,
  TerminalSquare
} from "lucide-react";
import { useState } from "react";
import { MarkdownMessage } from "@/components/markdown-message";
import { cn } from "@/lib/utils";

type AnswerKind = "analysis" | "summary" | "runbook" | "command" | "clarify" | "action" | "rca" | "master";

interface AnswerContext {
  type: AnswerKind;
  kicker: string;
  title: string;
  subtitle: string;
  icon: typeof Bot;
}

const tones: Record<AnswerKind, { shell: string; icon: string; accent: string }> = {
  analysis: {
    shell: "border-sky-200 bg-sky-50/70",
    icon: "border-sky-200 bg-sky-600 text-white",
    accent: "bg-sky-400"
  },
  summary: {
    shell: "border-emerald-200 bg-emerald-50/70",
    icon: "border-emerald-200 bg-emerald-600 text-white",
    accent: "bg-emerald-400"
  },
  runbook: {
    shell: "border-blue-200 bg-blue-50/70",
    icon: "border-blue-200 bg-blue-600 text-white",
    accent: "bg-blue-400"
  },
  command: {
    shell: "border-violet-200 bg-violet-50/70",
    icon: "border-violet-200 bg-violet-600 text-white",
    accent: "bg-violet-400"
  },
  clarify: {
    shell: "border-amber-200 bg-amber-50/80",
    icon: "border-amber-200 bg-amber-500 text-white",
    accent: "bg-amber-400"
  },
  action: {
    shell: "border-teal-200 bg-teal-50/70",
    icon: "border-teal-200 bg-teal-600 text-white",
    accent: "bg-teal-400"
  },
  rca: {
    shell: "border-red-200 bg-red-50/60",
    icon: "border-red-200 bg-red-600 text-white",
    accent: "bg-red-400"
  },
  master: {
    shell: "border-orange-200 bg-orange-50/70",
    icon: "border-orange-200 bg-orange-600 text-white",
    accent: "bg-orange-400"
  }
};

function fold(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function classifyAnswer(content: string): AnswerContext {
  const key = fold(content);
  if (key.includes("master agent") || key.includes("routing:") || key.includes("dieu phoi")) {
    return {
      type: "master",
      icon: Bot,
      kicker: "Response type",
      title: "Master coordination",
      subtitle: "The master response is organized from one or more specialist agents."
    };
  }
  if (key.includes("aiops rca") || key.includes("root cause") || key.includes("most likely root cause") || key.includes("timeline")) {
    return {
      type: "rca",
      icon: SearchCode,
      kicker: "Response type",
      title: "Root cause investigation",
      subtitle: "Root cause, impact, evidence and actions are grouped for incident review."
    };
  }
  if (key.includes("runbook") || key.includes("command de xuat") || (key.includes("verify:") && key.includes("remediate:"))) {
    return {
      type: "runbook",
      icon: ClipboardList,
      kicker: "Response type",
      title: "Runbook recommendation",
      subtitle: "Commands are grouped by phase so verification stays separate from remediation."
    };
  }
  if (key.includes("command insight") || key.includes("giai thich") || key.includes("dung de lam gi")) {
    return {
      type: "command",
      icon: TerminalSquare,
      kicker: "Response type",
      title: "Command explanation",
      subtitle: "Purpose, usage and operational risk are separated for quick review."
    };
  }
  if (key.includes("tom tat") || key.includes("tong so event") || key.includes("top alert") || key.includes("theo severity")) {
    return {
      type: "summary",
      icon: Activity,
      kicker: "Response type",
      title: "Operational summary",
      subtitle: "Signal, severity and priority findings are organized for scanning."
    };
  }
  if (key.includes("vui long noi ro") || key.includes("can lam ro") || key.includes("thieu ngu canh")) {
    return {
      type: "clarify",
      icon: HelpCircle,
      kicker: "Response type",
      title: "Needs clarification",
      subtitle: "The agent is asking for missing target, value, time window or channel."
    };
  }
  if (key.includes("da tao") || key.includes("da gui") || key.includes("da cap nhat") || key.includes("saved") || key.includes("deleted")) {
    return {
      type: "action",
      icon: CheckCircle2,
      kicker: "Response type",
      title: "Action result",
      subtitle: "Execution details and state changes are grouped below."
    };
  }
  return {
    type: "analysis",
    icon: BrainCircuit,
    kicker: "Response type",
    title: "Operational analysis",
    subtitle: "The answer is structured into readable findings and details."
  };
}

function extractThinkBlocks(content: string) {
  const thinkBlocks: string[] = [];
  let visibleContent = content.replace(/<think>([\s\S]*?)<\/think>/gi, (_match, thought: string) => {
    const clean = String(thought ?? "").trim();
    if (clean) thinkBlocks.push(clean);
    return "\n";
  });

  const openThinkIndex = visibleContent.toLowerCase().indexOf("<think>");
  if (openThinkIndex >= 0) {
    const thought = visibleContent.slice(openThinkIndex + "<think>".length).trim();
    if (thought) thinkBlocks.push(thought);
    visibleContent = visibleContent.slice(0, openThinkIndex);
  }

  return {
    visibleContent: visibleContent.trim(),
    thinkBlocks
  };
}

function ThinkDisclosure({ blocks }: { blocks: string[] }) {
  const [open, setOpen] = useState(false);
  if (!blocks.length) return null;

  const label = blocks.length > 1 ? `Think (${blocks.length})` : "Think";

  return (
    <div className="mb-3 overflow-hidden rounded-lg border border-slate-200 bg-slate-50/80">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-xs font-semibold uppercase tracking-[0.08em] text-slate-600 transition-colors hover:bg-slate-100"
      >
        <span className="flex items-center gap-2">
          <BrainCircuit className="h-4 w-4 text-slate-500" />
          {label}
        </span>
        <ChevronDown className={cn("h-4 w-4 text-slate-500 transition-transform", open ? "rotate-180" : "")} />
      </button>
      {open ? (
        <div className="border-t border-slate-200 bg-white px-3 py-3">
          {blocks.map((block, index) => (
            <pre key={index} className="whitespace-pre-wrap break-words rounded-md bg-slate-950 p-3 font-mono text-xs leading-5 text-slate-100">
              {block}
            </pre>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function AgentAnswerCard({ content }: { content: string }) {
  const { visibleContent, thinkBlocks } = extractThinkBlocks(content);
  const context = classifyAnswer(visibleContent || content);
  const tone = tones[context.type];
  const Icon = context.icon;

  return (
    <article className="relative max-w-[92%] overflow-hidden rounded-lg border border-border bg-card shadow-sm">
      <div className={cn("absolute bottom-4 left-0 top-4 w-1 rounded-r-full", tone.accent)} />
      <div className="p-4">
        <div className={cn("mb-4 grid grid-cols-[40px_minmax(0,1fr)] gap-3 rounded-lg border p-3", tone.shell)}>
          <div className={cn("flex h-10 w-10 items-center justify-center rounded-lg border", tone.icon)}>
            <Icon className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{context.kicker}</p>
            <p className="mt-0.5 text-base font-semibold leading-tight text-foreground">{context.title}</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">{context.subtitle}</p>
          </div>
        </div>
        <ThinkDisclosure blocks={thinkBlocks} />
        {visibleContent ? (
          <MarkdownMessage content={visibleContent} />
        ) : (
          <p className="text-sm leading-6 text-muted-foreground">No visible answer content returned.</p>
        )}
      </div>
    </article>
  );
}
