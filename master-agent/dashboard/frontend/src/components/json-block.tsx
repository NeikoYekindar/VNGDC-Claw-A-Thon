"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";

export function JsonBlock({ value, maxHeight = "max-h-96" }: { value: unknown; maxHeight?: string }) {
  const [open, setOpen] = useState(false);
  const Icon = open ? ChevronDown : ChevronRight;

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 text-xs font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
      >
        <Icon className="h-3.5 w-3.5" />
        {open ? "Hide raw JSON" : "Show raw JSON"}
      </button>
      {open ? (
        <pre className={cn(maxHeight, "overflow-auto rounded-lg border border-border bg-slate-950 p-4 text-xs leading-5 text-slate-100")}>
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}
