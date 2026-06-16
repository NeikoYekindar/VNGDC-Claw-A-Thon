"use client";

import { useEffect, useRef, useState } from "react";
import { api, type AgentStatus, type ChatMessage } from "@/lib/api";
import { MarkdownMessage } from "@/components/markdown-message";

function getSessionId(): string {
  if (typeof window === "undefined") return "ssr";
  let sid = sessionStorage.getItem("agent_session_id");
  if (!sid) {
    sid = `sess-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    sessionStorage.setItem("agent_session_id", sid);
  }
  return sid;
}

function StatusDot({ connected }: { connected: boolean | null }) {
  if (connected === null) return <span className="h-2 w-2 rounded-full bg-slate-300" />;
  return connected ? <span className="h-2 w-2 rounded-full bg-emerald-500" /> : <span className="h-2 w-2 rounded-full bg-red-500" />;
}

export function AgentChatPanel() {
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const sessionId = useRef(getSessionId());

  useEffect(() => {
    const check = () =>
      api.agentStatus().then(setStatus).catch(() =>
        setStatus({ connected: false, url: "", error: "Cannot reach dashboard backend" }),
      );
    check();
    api.agentChatHistory(sessionId.current)
      .then((rows) =>
        setMessages(
          rows.map((row) => ({
            role: row.role,
            content: row.content,
            timestamp: row.created_at,
          })),
        ),
      )
      .catch(() => undefined);
    const iv = setInterval(check, 30_000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  const send = async () => {
    const text = input.trim();
    if (!text || sending) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: text, timestamp: new Date().toISOString() }]);
    setSending(true);

    try {
      const res = await api.agentChat(text, sessionId.current);
      setMessages((prev) => [...prev, { role: "assistant", content: res.response, timestamp: res.timestamp }]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: [
            "I could not send this message to the agent runtime.",
            "",
            "Try again in a few seconds. If the error repeats, check `AGENT_URL`, the `/invocations` route, and AgentBase runtime logs.",
            "",
            `Technical detail: ${String(e)}`,
          ].join("\n"),
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const connected = status?.connected ?? null;

  return (
    <section className="flex h-[calc(100vh-220px)] min-h-[560px] flex-col overflow-hidden rounded-lg border border-border bg-card shadow-sm xl:h-full xl:min-h-0">
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-blue-200 bg-blue-50 text-primary">
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h8M8 14h5m8-2a8 8 0 11-15.5-2.8L3 21l4.2-1.4A8 8 0 0021 12z" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold">Security Agent</h2>
            <p className="text-xs text-muted-foreground">MiniMax runtime</p>
          </div>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-border bg-secondary px-2.5 py-1 text-xs text-muted-foreground">
          <StatusDot connected={connected} />
          {connected === null ? "Checking" : connected ? "Online" : "Offline"}
        </div>
      </div>

      <div className="chat-scroll-area min-h-0 flex-1 overflow-y-auto overscroll-contain bg-slate-50/70 px-6 py-6">
        {messages.length === 0 ? (
          <div className="flex h-full min-h-0 items-center justify-center">
            <div className="max-w-sm text-center">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-lg border border-border bg-card text-primary shadow-sm">
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.7} d="M12 3l7 3v5c0 4.4-2.9 8.4-7 9.7-4.1-1.3-7-5.3-7-9.7V6l7-3z" />
                </svg>
              </div>
              <p className="text-sm font-medium">No messages in this session</p>
              <p className="mt-1 text-xs text-muted-foreground">Agent context is connected to hardening and vulnerability operations.</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {messages.map((message, index) => (
              <div key={`${message.timestamp}-${index}`} className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[82%] rounded-lg px-3.5 py-2.5 text-sm leading-relaxed shadow-sm ${
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "border border-border bg-card text-foreground"
                  }`}
                >
                  {message.role === "assistant" ? (
                    <MarkdownMessage content={message.content} />
                  ) : (
                    <div className="whitespace-pre-wrap">{message.content}</div>
                  )}
                </div>
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
        <div className="flex items-end gap-2 rounded-lg border border-border bg-background p-2 focus-within:ring-2 focus-within:ring-primary/20">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder="Ask the security agent..."
            disabled={sending || status?.connected === false}
            rows={2}
            className="min-h-10 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none disabled:cursor-not-allowed disabled:opacity-60"
          />
          <button
            onClick={send}
            disabled={sending || !input.trim() || status?.connected === false}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            title="Send"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
      </div>
    </section>
  );
}
