"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Bot, ChevronDown, Gauge, MessageSquare, Plus, ScrollText, SendHorizontal, ShieldCheck, Sparkles } from "lucide-react";
import { api, type AgentStatus, type ChatMessage, type ChatSessionSummary } from "@/lib/api";
import { AgentAnswerCard } from "@/components/agent-answer-card";
import { StatusPill } from "@/components/status-pill";
import { cn } from "@/lib/utils";

function createSessionId(): string {
  return `master-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function getSessionId(): string {
  if (typeof window === "undefined") return "ssr";
  let sid = sessionStorage.getItem("master_agent_session_id");
  if (!sid) {
    sid = createSessionId();
    sessionStorage.setItem("master_agent_session_id", sid);
  }
  return sid;
}

function formatSessionTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

const agentCommands = [
  { command: "/monitoring", label: "Monitoring", icon: Gauge },
  { command: "/logging", label: "Logging", icon: ScrollText },
  { command: "/security", label: "Security", icon: ShieldCheck }
] as const;

type AgentCommand = (typeof agentCommands)[number]["command"];
type QuickActionKind = "Quick action" | "Quick impact";

const commandAliases: Record<string, AgentCommand> = {
  monitoring: "/monitoring",
  monitor: "/monitoring",
  mon: "/monitoring",
  logging: "/logging",
  log: "/logging",
  logs: "/logging",
  security: "/security",
  sec: "/security"
};

const quickActionGroups: Record<
  AgentCommand,
  {
    label: string;
    description: string;
    itemClass: string;
    items: Array<{ kind: QuickActionKind; label: string; prompt: string }>;
  }
> = {
  "/monitoring": {
    label: "Monitoring",
    description: "Health, alert, RCA, inventory, and maintenance prompts.",
    itemClass: "hover:border-sky-200 hover:bg-sky-50 hover:text-sky-800",
    items: [
      { kind: "Quick action", label: "Health overview", prompt: "Tổng quan sức khỏe hệ thống hiện tại, alert nào cần ưu tiên xử lý?" },
      { kind: "Quick action", label: "Ưu tiên alert", prompt: "Alert monitoring nào cần ưu tiên và vì sao?" },
      { kind: "Quick action", label: "RCA monitoring", prompt: "Phân tích RCA cho tín hiệu monitoring mới nhất và đề xuất bước tiếp theo." },
      { kind: "Quick action", label: "Inventory risk", prompt: "Kiểm tra inventory thiết bị, node nào đang có rủi ro hoặc mất kết nối?" },
      { kind: "Quick impact", label: "Node unreachable", prompt: "Phân tích monitoring impact: node critical unreachable trong 1 giờ qua." },
      { kind: "Quick impact", label: "CPU saturation", prompt: "Phân tích monitoring impact: CPU saturation và service latency tăng trong 1 giờ qua." },
      { kind: "Quick impact", label: "Network packet loss", prompt: "Phân tích monitoring impact: packet loss liên tục trên đường uplink trong 1 giờ qua." }
    ]
  },
  "/logging": {
    label: "Logging",
    description: "Merged Quick action and Quick impact from infra-log-sentinel-agent.",
    itemClass: "hover:border-emerald-200 hover:bg-emerald-50 hover:text-emerald-800",
    items: [
      { kind: "Quick action", label: "Tóm tắt hôm nay", prompt: "tóm tắt log hôm nay" },
      { kind: "Quick action", label: "Ưu tiên alert", prompt: "alert nào cần ưu tiên và vì sao" },
      { kind: "Quick action", label: "Command xử lý", prompt: "phân tích lỗi nghiêm trọng và đưa command xử lý" },
      { kind: "Quick action", label: "RCA incident", prompt: "sinh log su co broadcast loop roi phan tich RCA" },
      { kind: "Quick action", label: "Runtime check", prompt: "trạng thái control" },
      { kind: "Quick action", label: "Tạm ngừng sinh log", prompt: "tạm ngừng sinh log trong 5 phút" },
      { kind: "Quick action", label: "Gửi report Gmail", prompt: "gửi báo cáo hôm nay qua Gmail" },
      {
        kind: "Quick impact",
        label: "VLAN 20 internet slow",
        prompt: "phan tich RCA dua tren log hien tai: VLAN 20 users mat internet, firewall CPU saturated trong 1 gio qua"
      },
      {
        kind: "Quick impact",
        label: "Fortigate session spike",
        prompt: "phan tich RCA dua tren log hien tai: Fortigate latency tang va new sessions delayed trong 1 gio qua"
      },
      {
        kind: "Quick impact",
        label: "DNS query timeout",
        prompt: "phan tich RCA dua tren log hien tai: ung dung loi name resolution, DNS query timeout trong 1 gio qua"
      },
      {
        kind: "Quick impact",
        label: "Routing payment subnet",
        prompt: "phan tich RCA dua tren log hien tai: applications cannot reach payment subnet sau routing change trong 1 gio qua"
      },
      {
        kind: "Quick impact",
        label: "SQLAgent service down",
        prompt: "phan tich RCA dua tren log hien tai: SQLAgent service down, database jobs khong chay trong 1 gio qua"
      },
      {
        kind: "Quick impact",
        label: "SSH brute force",
        prompt: "phan tich RCA dua tren log hien tai: SSH brute force tu internet, account lockout risk trong 1 gio qua"
      }
    ]
  },
  "/security": {
    label: "Security",
    description: "Hardening, vulnerability, CVE, and asset-risk prompts.",
    itemClass: "hover:border-orange-200 hover:bg-orange-50 hover:text-orange-800",
    items: [
      { kind: "Quick action", label: "Hardening posture", prompt: "Tổng quan hardening posture, server nào cần ưu tiên xử lý trước?" },
      { kind: "Quick action", label: "Ưu tiên server", prompt: "Server security nào cần ưu tiên và vì sao?" },
      { kind: "Quick action", label: "Vulnerability assets", prompt: "Tóm tắt vulnerability assets, CVE critical/high và ưu tiên patch." },
      { kind: "Quick action", label: "CVE radar", prompt: "Kiểm tra emerging CVE radar và khả năng ảnh hưởng đến tài sản hiện có." },
      { kind: "Quick impact", label: "Not hardened server", prompt: "Phân tích security impact: server chưa hardening và rủi ro vận hành hiện tại." },
      { kind: "Quick impact", label: "Critical CVE exposure", prompt: "Phân tích security impact: tài sản có khả năng dính CVE critical/high trong 24 giờ qua." },
      { kind: "Quick impact", label: "Wazuh agent offline", prompt: "Phân tích security impact: Wazuh/security agent không reachable và baseline chưa cập nhật." }
    ]
  }
};

function detectCommand(value: string): AgentCommand | null {
  const match = value.trimStart().match(/^\/([a-z]+)\b/i);
  if (!match) return null;
  return commandAliases[match[1].toLowerCase()] ?? null;
}

export function MasterChatPanel({ compact = false }: { compact?: boolean }) {
  const [statuses, setStatuses] = useState<AgentStatus[]>([]);
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [sessionId, setSessionId] = useState(getSessionId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [selectedCommand, setSelectedCommand] = useState<AgentCommand | null>(null);
  const [quickMenuOpen, setQuickMenuOpen] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const quickMenuRef = useRef<HTMLDivElement>(null);
  const showHistory = !compact;

  const loadSessions = useCallback(async () => {
    try {
      const rows = await api.masterChatSessions();
      setSessions(rows);
    } catch {
      setSessions([]);
    }
  }, []);

  useEffect(() => {
    const loadStatus = () => api.agentsStatus().then(setStatuses).catch(() => setStatuses([]));
    loadStatus();
    const iv = setInterval(loadStatus, 30_000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    loadSessions();
    const iv = setInterval(loadSessions, 20_000);
    return () => clearInterval(iv);
  }, [loadSessions]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      sessionStorage.setItem("master_agent_session_id", sessionId);
    }

    let cancelled = false;
    api.masterChatHistory(sessionId)
      .then((rows) => {
        if (cancelled) return;
        setMessages(
          rows.map((row) => ({
            role: row.role,
            content: row.content,
            timestamp: row.created_at
          }))
        );
      })
      .catch(() => {
        if (!cancelled) setMessages([]);
      });

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    const closeMenu = (event: MouseEvent) => {
      if (!quickMenuRef.current || quickMenuRef.current.contains(event.target as Node)) return;
      setQuickMenuOpen(false);
    };

    document.addEventListener("mousedown", closeMenu);
    return () => document.removeEventListener("mousedown", closeMenu);
  }, []);

  const selectSession = (nextSessionId: string) => {
    if (sending || nextSessionId === sessionId) return;
    setSessionId(nextSessionId);
    setInput("");
    setSelectedCommand(null);
    setQuickMenuOpen(false);
  };

  const createNewChat = async () => {
    if (sending) return;
    try {
      const session = await api.createMasterChatSession();
      setSessions((current) => [session, ...current.filter((item) => item.session_id !== session.session_id)]);
      setSessionId(session.session_id);
    } catch {
      setSessionId(createSessionId());
    }
    setInput("");
    setMessages([]);
    setSelectedCommand(null);
    setQuickMenuOpen(false);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text, timestamp: new Date().toISOString() }]);
    setSending(true);

    try {
      const res = await api.masterChat(text, sessionId);
      setMessages((prev) => [...prev, { role: "assistant", content: res.response, timestamp: res.timestamp }]);
      loadSessions();
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: [
            "# Master Agent",
            "",
            "I could not send this message through the master backend.",
            "",
            `Technical detail: ${String(e)}`
          ].join("\n"),
          timestamp: new Date().toISOString()
        }
      ]);
    } finally {
      setSending(false);
    }
  };

  const activeCommand = detectCommand(input) ?? selectedCommand;
  const activeQuickGroup = activeCommand ? quickActionGroups[activeCommand] : null;

  const handleInputChange = (value: string) => {
    setInput(value);
    const nextCommand = detectCommand(value);
    if (nextCommand) setSelectedCommand(nextCommand);
    if (!value.trim()) {
      setSelectedCommand(null);
      setQuickMenuOpen(false);
    }
  };

  const applyAgentCommand = (command: AgentCommand) => {
    setSelectedCommand(command);
    setQuickMenuOpen(false);
    setInput((current) => {
      const clean = current.trim().replace(/^\/(monitoring|monitor|mon|logging|log|logs|security|sec)\s*/i, "");
      return clean ? `${command} ${clean}` : `${command} `;
    });
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const applyQuickAction = (prompt: string) => {
    if (sending || !activeCommand) return;
    setSelectedCommand(activeCommand);
    setQuickMenuOpen(false);
    setInput(`${activeCommand} ${prompt}`);
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const activeCount = statuses.filter((item) => item.connected).length;
  const activeSession = sessions.find((item) => item.session_id === sessionId);

  return (
    <section
      className={cn(
        "min-h-0 overflow-hidden rounded-lg border border-border bg-card shadow-sm",
        compact ? "flex h-[520px] flex-col" : "grid h-[calc(100vh-155px)] min-h-[620px] grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)]"
      )}
    >
      {showHistory ? (
        <aside className="flex min-h-0 flex-col border-b border-border bg-slate-50/70 lg:border-b-0 lg:border-r">
          <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-4">
            <div className="min-w-0">
              <p className="text-sm font-semibold">Chat History</p>
              <p className="truncate text-xs text-muted-foreground">{sessions.length} conversations</p>
            </div>
            <button
              type="button"
              onClick={createNewChat}
              disabled={sending}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              title="New chat"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {sessions.length === 0 ? (
              <button
                type="button"
                onClick={createNewChat}
                className="flex w-full items-center gap-3 rounded-lg border border-dashed border-border bg-card px-3 py-3 text-left text-sm text-muted-foreground transition-colors hover:border-orange-200 hover:bg-orange-50"
              >
                <MessageSquare className="h-4 w-4" />
                Start a new chat
              </button>
            ) : (
              <div className="space-y-1">
                {sessions.map((session) => {
                  const active = session.session_id === sessionId;
                  return (
                    <button
                      key={session.session_id}
                      type="button"
                      onClick={() => selectSession(session.session_id)}
                      className={cn(
                        "w-full rounded-lg px-3 py-2.5 text-left transition-colors",
                        active ? "bg-orange-50 text-primary ring-1 ring-orange-200" : "text-foreground hover:bg-card"
                      )}
                    >
                      <div className="flex items-start gap-2">
                        <MessageSquare className={cn("mt-0.5 h-4 w-4 shrink-0", active ? "text-primary" : "text-muted-foreground")} />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium" title={session.title}>
                            {session.title || "New conversation"}
                          </p>
                          <p className="mt-1 truncate text-xs text-muted-foreground">
                            {session.message_count} messages · {formatSessionTime(session.updated_at)}
                          </p>
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </aside>
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-orange-200 bg-orange-50 text-primary">
              <Bot className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <h2 className="truncate text-sm font-semibold">{activeSession?.title || "Master Agent"}</h2>
              <p className="truncate text-xs text-muted-foreground">Routes questions to Monitoring, Logging, and Security</p>
            </div>
          </div>
          <StatusPill connected={activeCount === 3} label={`${activeCount}/3 active`} />
        </div>

        <div className="chat-scroll-area min-h-0 flex-1 overflow-y-auto overscroll-contain bg-slate-50/70 px-6 py-6">
          {messages.length === 0 ? (
            <div className="flex h-full min-h-0 items-center justify-center">
              <div className="max-w-md text-center">
                <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg border border-border bg-card text-primary shadow-sm">
                  <Bot className="h-6 w-6" />
                </div>
                <p className="text-sm font-medium">Start with an operations question</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  The master agent keeps context inside this conversation.
                </p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {messages.map((message, index) => (
                <div key={`${message.timestamp}-${index}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                  {message.role === "assistant" ? (
                    <AgentAnswerCard content={message.content} />
                  ) : (
                    <div className="max-w-[86%] rounded-lg bg-primary px-3.5 py-2.5 text-sm leading-relaxed text-primary-foreground shadow-sm">
                      <div className="whitespace-pre-wrap">{message.content}</div>
                    </div>
                  )}
                </div>
              ))}
              {sending ? (
                <div className="flex justify-start">
                  <div className="flex items-center gap-1 rounded-lg border border-border bg-card px-3 py-2 shadow-sm">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" style={{ animationDelay: "0ms" }} />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" style={{ animationDelay: "150ms" }} />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted-foreground" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              ) : null}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <div className="border-t border-border bg-card p-5">
          <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-2">
              {agentCommands.map((item) => {
                const Icon = item.icon;
                const active = item.command === activeCommand;
                return (
                  <button
                    key={item.command}
                    type="button"
                    title={`Ask ${item.label}`}
                    onClick={() => applyAgentCommand(item.command)}
                    disabled={sending}
                    className={cn(
                      "inline-flex h-8 items-center gap-2 rounded-md border px-2.5 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
                      active
                        ? "border-primary/30 bg-primary/10 text-primary"
                        : "border-border bg-background text-muted-foreground hover:border-orange-200 hover:bg-orange-50 hover:text-primary"
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {item.command}
                  </button>
                );
              })}
            </div>

            <div ref={quickMenuRef} className="relative sm:ml-auto">
              <button
                type="button"
                onClick={() => {
                  if (!activeQuickGroup) return;
                  setQuickMenuOpen((current) => !current);
                }}
                disabled={sending || !activeQuickGroup}
                className={cn(
                  "inline-flex h-8 w-full items-center justify-between gap-2 rounded-md border px-2.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto",
                  activeQuickGroup
                    ? "border-orange-200 bg-orange-50 text-primary hover:bg-orange-100"
                    : "border-border bg-background text-muted-foreground"
                )}
                title={activeQuickGroup ? `Quick action for ${activeQuickGroup.label}` : "Select a module first"}
              >
                <span className="inline-flex items-center gap-2">
                  <Sparkles className="h-3.5 w-3.5" />
                  Quick action
                </span>
                <span className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] text-muted-foreground">{activeQuickGroup?.label ?? "Select module"}</span>
                <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", quickMenuOpen ? "rotate-180" : "")} />
              </button>

              {quickMenuOpen && activeQuickGroup ? (
                <div className="absolute bottom-full right-0 z-30 mb-2 w-[min(92vw,380px)] overflow-hidden rounded-lg border border-border bg-card shadow-lg">
                  <div className="border-b border-border px-3 py-2.5">
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">{activeQuickGroup.label}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{activeQuickGroup.description}</p>
                  </div>
                  <div className="max-h-[360px] overflow-y-auto p-2">
                    {(["Quick action", "Quick impact"] as const).map((kind) => {
                      const items = activeQuickGroup.items.filter((item) => item.kind === kind);
                      if (!items.length) return null;
                      return (
                        <section key={kind} className="mb-2 last:mb-0">
                          <p className="px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">{kind}</p>
                          <div className="grid gap-1">
                            {items.map((item) => (
                              <button
                                key={`${kind}-${item.label}`}
                                type="button"
                                onClick={() => applyQuickAction(item.prompt)}
                                className={cn(
                                  "w-full rounded-md border border-transparent px-2.5 py-2 text-left text-xs transition-colors",
                                  activeQuickGroup.itemClass
                                )}
                                title={item.prompt}
                              >
                                <span className="block font-semibold text-foreground">{item.label}</span>
                                <span className="mt-0.5 block truncate text-muted-foreground">{item.prompt}</span>
                              </button>
                            ))}
                          </div>
                        </section>
                      );
                    })}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
          <div className="flex items-end gap-2 rounded-lg border border-border bg-background p-2 focus-within:ring-2 focus-within:ring-primary/20">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => handleInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder="Ask the master agent..."
              disabled={sending}
              rows={2}
              className="min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-60"
            />
            <button
              onClick={send}
              disabled={sending || !input.trim()}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              title="Send"
            >
              <SendHorizontal className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
