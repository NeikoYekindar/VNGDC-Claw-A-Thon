"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type AgentStatus } from "@/lib/api";

function StatusDot({ connected }: { connected: boolean | null }) {
  if (connected === null) return <span className="h-2 w-2 rounded-full bg-slate-300" />;
  return connected ? <span className="h-2 w-2 rounded-full bg-emerald-500" /> : <span className="h-2 w-2 rounded-full bg-red-500" />;
}

export function AgentChat() {
  const [status, setStatus] = useState<AgentStatus | null>(null);

  useEffect(() => {
    const check = () =>
      api.agentStatus().then(setStatus).catch(() =>
        setStatus({ connected: false, url: "", error: "Cannot reach dashboard backend" }),
      );
    check();
    const iv = setInterval(check, 30_000);
    return () => clearInterval(iv);
  }, []);

  return (
    <Link
      href="/chat"
      className="inline-flex h-9 items-center gap-2 rounded-lg border border-border bg-card px-3 text-sm font-medium text-foreground transition-colors hover:bg-secondary"
    >
      <StatusDot connected={status?.connected ?? null} />
      Agent Chat
    </Link>
  );
}
