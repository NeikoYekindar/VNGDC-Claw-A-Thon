"use client";

import { MasterChatPanel } from "@/components/master-chat-panel";

export default function ChatPage() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Master Chat</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Chat with the master agent</h1>
        <p className="mt-1 text-sm text-muted-foreground">Questions are routed to one or more specialist agents and summarized here.</p>
      </div>
      <MasterChatPanel />
    </div>
  );
}
