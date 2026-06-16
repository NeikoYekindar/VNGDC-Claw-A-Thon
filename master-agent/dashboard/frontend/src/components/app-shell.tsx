"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BookOpen,
  Bot,
  ChevronDown,
  ClipboardList,
  Gauge,
  Home,
  ListTree,
  MessageSquare,
  Radar,
  ScrollText,
  SearchCode,
  Server,
  ShieldCheck,
  ShieldAlert,
  Siren,
  TerminalSquare,
  Wrench
} from "lucide-react";
import { api, type AgentStatus } from "@/lib/api";
import { cn } from "@/lib/utils";
import { StatusPill } from "@/components/status-pill";

const groups = [
  {
    key: "monitoring",
    label: "Monitoring",
    icon: Gauge,
    items: [
      { href: "/monitoring", label: "Overview", icon: Activity },
      { href: "/monitoring/alerts", label: "Alert RCA", icon: Siren },
      { href: "/monitoring/inventory", label: "Inventory", icon: Server },
      { href: "/monitoring/maintenance", label: "Maintenance", icon: Wrench },
      { href: "/monitoring/knowledge", label: "Knowledge Base", icon: BookOpen }
    ]
  },
  {
    key: "logging",
    label: "Logging",
    icon: ScrollText,
    items: [
      { href: "/logging", label: "Log Console", icon: ListTree },
      { href: "/logging/rca", label: "RCA Workspace", icon: SearchCode },
      { href: "/logging/runtime", label: "Runtime Control", icon: TerminalSquare }
    ]
  },
  {
    key: "security",
    label: "Security",
    icon: ShieldCheck,
    items: [
      { href: "/security", label: "Hardening", icon: ShieldAlert },
      { href: "/security/vulnerabilities", label: "Vul Assets", icon: ClipboardList },
      { href: "/security/radar", label: "CVE Radar", icon: Radar }
    ]
  }
];

const sectionRootHrefs = new Set(groups.map((group) => `/${group.key}`));

function isActive(pathname: string, href: string) {
  if (href === "/security") {
    return pathname === href || pathname.startsWith("/security/servers/");
  }
  if (sectionRootHrefs.has(href)) {
    return pathname === href;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function groupActive(pathname: string, key: string) {
  return pathname === `/${key}` || pathname.startsWith(`/${key}/`);
}

function SidebarStatus() {
  const [statuses, setStatuses] = useState<AgentStatus[]>([]);

  useEffect(() => {
    const load = () => api.agentsStatus().then(setStatuses).catch(() => setStatuses([]));
    load();
    const iv = setInterval(load, 30_000);
    return () => clearInterval(iv);
  }, []);

  const activeCount = statuses.filter((item) => item.connected).length;

  return (
    <div className="border-t border-slate-800 px-4 py-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase text-slate-400">Agent fabric</p>
        <StatusPill connected={activeCount === 3} label={`${activeCount}/3 active`} compact />
      </div>
      <div className="space-y-2">
        {groups.map((group) => {
          const status = statuses.find((item) => item.key === group.key);
          return (
            <div key={group.key} className="flex items-center justify-between gap-3 text-xs">
              <span className="truncate text-slate-300">{group.label}</span>
              <span className={cn("h-2 w-2 rounded-full", status?.connected ? "bg-emerald-400" : "bg-red-400")} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const expanded = useMemo(() => {
    const next: Record<string, boolean> = {};
    groups.forEach((group) => {
      next[group.key] = open[group.key] ?? groupActive(pathname, group.key);
    });
    return next;
  }, [open, pathname]);

  return (
    <div className="min-h-screen bg-background text-foreground lg:grid lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="border-r border-slate-800 bg-slate-950 text-slate-100 lg:sticky lg:top-0 lg:h-screen">
        <div className="flex h-full flex-col">
          <div className="border-b border-slate-800 p-4">
            <Link href="/" className="grid grid-cols-[44px_minmax(0,1fr)] items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-lg border border-orange-300/30 bg-orange-500/15 text-orange-200">
                <Bot className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold">VNG DATA CENTER</p>
                <p className="truncate text-xs text-slate-400">247 Operation Agent</p>
              </div>
            </Link>
          </div>

          <nav className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
            <Link
              href="/"
              className={cn(
                "mb-1 flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
                pathname === "/"
                  ? "bg-orange-500 text-white shadow-sm shadow-orange-950/10"
                  : "text-slate-300 hover:bg-slate-900 hover:text-white"
              )}
            >
              <Home className="h-4 w-4" />
              Overview
            </Link>

            <Link
              href="/chat"
              className={cn(
                "mb-4 flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
                isActive(pathname, "/chat")
                  ? "bg-orange-500 text-white shadow-sm shadow-orange-950/10"
                  : "text-slate-300 hover:bg-slate-900 hover:text-white"
              )}
            >
              <MessageSquare className="h-4 w-4" />
              Master Chat
            </Link>

            <div className="space-y-2">
              {groups.map((group) => {
                const Icon = group.icon;
                const isGroupActive = groupActive(pathname, group.key);
                return (
                  <div key={group.key}>
                    <button
                      type="button"
                      onClick={() => setOpen((current) => ({ ...current, [group.key]: !expanded[group.key] }))}
                      className={cn(
                        "flex h-10 w-full items-center gap-3 rounded-lg border-l-2 px-3 text-left text-sm font-semibold transition-colors",
                        isGroupActive ? "border-orange-400 bg-slate-900 text-white" : "border-transparent text-slate-300 hover:bg-slate-900 hover:text-white"
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      <span className="min-w-0 flex-1 truncate">{group.label}</span>
                      <ChevronDown className={cn("h-4 w-4 transition-transform", expanded[group.key] ? "rotate-180" : "")} />
                    </button>
                    {expanded[group.key] ? (
                      <div className="mt-1 space-y-1 pl-4">
                        {group.items.map((item) => {
                          const ItemIcon = item.icon;
                          const active = isActive(pathname, item.href);
                          return (
                            <Link
                              key={item.href}
                              href={item.href}
                              className={cn(
                                "flex h-9 items-center gap-3 rounded-lg border-l-2 px-3 text-sm transition-colors",
                                active
                                  ? "border-orange-400 bg-orange-500/10 text-orange-100"
                                  : "border-transparent text-slate-400 hover:bg-slate-900 hover:text-slate-100"
                              )}
                            >
                              <ItemIcon className="h-4 w-4" />
                              <span className="truncate">{item.label}</span>
                            </Link>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          </nav>

          <SidebarStatus />
        </div>
      </aside>

      <main className="min-w-0">
        <div className="pointer-events-none fixed inset-x-0 top-0 -z-10 h-52 border-b border-sky-100 bg-[linear-gradient(180deg,#f0f9ff_0%,rgba(240,249,255,0)_100%)]" />
        <div className="mx-auto w-full max-w-[1680px] px-5 py-6 sm:px-8 2xl:px-10">{children}</div>
      </main>
    </div>
  );
}
