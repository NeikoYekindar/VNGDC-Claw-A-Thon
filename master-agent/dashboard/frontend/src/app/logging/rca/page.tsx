"use client";

import { useState, type ReactNode } from "react";
import { Copy, MessageSquareText, SearchCode, Sparkles, TerminalSquare, X } from "lucide-react";
import { api } from "@/lib/api";
import { JsonBlock } from "@/components/json-block";
import { cn, shortText } from "@/lib/utils";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asTextArray(value: unknown): string[] {
  return asArray(value)
    .map((item) => shortText(item, ""))
    .filter(Boolean);
}

function phaseClasses(phase: string) {
  const key = phase.toLowerCase();
  if (key.includes("analyze")) return "border-blue-200 bg-blue-50/70 text-blue-700";
  if (key.includes("check")) return "border-emerald-200 bg-emerald-50/70 text-emerald-700";
  if (key.includes("validate")) return "border-teal-200 bg-teal-50/70 text-teal-700";
  if (key.includes("remediate") || key.includes("fix")) return "border-red-200 bg-red-50/70 text-red-700";
  return "border-green-200 bg-green-50/70 text-green-700";
}

function shellQuote(value: string) {
  return `'${String(value || "").replace(/'/g, "'\"'\"'")}'`;
}

function powershellQuote(value: string) {
  return `'${String(value || ".").replace(/'/g, "''")}'`;
}

function timelineText(item: unknown) {
  const row = asRecord(item);
  const main = [row.timestamp, row.type, row.domain, row.source, row.event_type].map((value) => shortText(value, "")).filter(Boolean).join(" | ");
  const message = shortText(row.message ?? row.event ?? row.detail, "");
  return [main, message].filter(Boolean).join(": ");
}

function rcaStatus(value: unknown) {
  const status = shortText(value, "unknown").toLowerCase();
  if (status.includes("confirm")) return "đã xác nhận";
  if (status.includes("weak")) return "evidence yếu";
  if (status.includes("no")) return "chưa đủ evidence";
  return shortText(value, "unknown");
}

function rcaActionItems(analysis: Record<string, unknown>, rawActions: string[]) {
  const anchor = asRecord(analysis.anchor_event);
  const source = shortText(anchor.source, "source chưa xác định");
  const eventType = shortText(anchor.event_type, "event_type chưa xác định");
  const timestamp = shortText(anchor.timestamp, "thời điểm RCA");
  const confidence = Number(analysis.confidence ?? 0);
  const actions = [
    `Ưu tiên kiểm tra ${source} / ${eventType} trước khi remediation.`,
    `Đối chiếu log quanh ${timestamp} để xác minh chuỗi nguyên nhân -> ảnh hưởng.`
  ];

  if (confidence < 70) {
    actions.push("Chưa chạy thao tác có rủi ro; cần thu thập thêm evidence trước.");
  } else {
    actions.push("Nếu evidence khớp, xử lý theo runbook tương ứng và thông báo impact cho service owner.");
  }

  rawActions.forEach((action) => actions.push(`Khuyến nghị kỹ thuật: ${action}`));
  return actions;
}

function rcaCommandCards(analysis: Record<string, unknown>) {
  const anchor = asRecord(analysis.anchor_event);
  const source = shortText(anchor.source, "");
  const eventType = shortText(anchor.event_type, "");
  const domain = shortText(anchor.domain, "").toLowerCase();
  const eventKey = eventType.toLowerCase();
  const sourceKey = source.toLowerCase();
  const needle = source || eventType || "ERROR";
  const cards = [
    { phase: "Investigate", command: `grep -R ${shellQuote(needle)} /app/data/logs -n | tail -80` },
    { phase: "Analyze", command: `grep -R ${shellQuote(eventType || needle)} /app/data/logs -n | tail -80` }
  ];

  if (domain.includes("linux") || eventKey.includes("dns") || sourceKey.includes("dns")) {
    cards.push({ phase: "Check", command: "journalctl --since '1 hour ago' -u named -u systemd-resolved --no-pager | tail -120" });
    cards.push({ phase: "Validate", command: "dig @127.0.0.1 example.com +time=2 +tries=1" });
  }

  if (eventKey.includes("application") || eventKey.includes("timeout") || sourceKey.includes("web")) {
    cards.push({ phase: "Check", command: "systemctl status nginx --no-pager && journalctl -u nginx --since '1 hour ago' --no-pager | tail -120" });
  }

  if (domain.includes("fortigate") || sourceKey.includes("fortigate") || eventKey.includes("session")) {
    cards.push({ phase: "Check", command: "diagnose sys session stat && diagnose sys top 5 20" });
    cards.push({ phase: "Investigate", command: `show firewall policy | grep -i ${shellQuote(eventType || "policy")}` });
  }

  if (domain.includes("windows") || sourceKey.includes("win")) {
    cards.push({
      phase: "Check",
      command: `Get-WinEvent -ComputerName ${powershellQuote(source || ".")} -FilterHashtable @{LogName='System'; StartTime=(Get-Date).AddHours(-1)} | Select-Object -First 50`
    });
  }

  if (domain.includes("vmware") || sourceKey.includes("esx") || sourceKey.includes("vcenter")) {
    cards.push({
      phase: "Check",
      command: `esxcli system syslog mark --message ${shellQuote(`RCA check ${eventType || source}`)} && tail -120 /var/log/vmkernel.log`
    });
  }

  return cards.slice(0, 5);
}

function RcaResultBlock({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-border bg-card p-4 shadow-sm">
      <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-emerald-700">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function CommandCard({ phase, command }: { phase: string; command: string }) {
  return (
    <div className={cn("overflow-hidden rounded-lg border border-l-4", phaseClasses(phase))}>
      <div className="flex items-center justify-between gap-3 border-b border-current/20 bg-white/45 px-3 py-2">
        <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.08em]">
          <TerminalSquare className="h-3.5 w-3.5" />
          {phase}
        </div>
        <button
          type="button"
          onClick={() => navigator.clipboard?.writeText(command)}
          className="inline-flex h-7 items-center gap-1.5 rounded-md border border-current/20 bg-white px-2 text-xs font-medium hover:bg-white/80"
        >
          <Copy className="h-3.5 w-3.5" />
          Copy
        </button>
      </div>
      <code className="block whitespace-pre-wrap bg-slate-50 px-3 py-3 font-mono text-xs leading-5 text-slate-950">{command}</code>
    </div>
  );
}

function RcaAnalysisResult({ analysis, status }: { analysis: Record<string, unknown>; status: unknown }) {
  const actions = asRecord(analysis.recommended_actions);
  const evidence = asTextArray(analysis.evidence);
  const timeline = asArray(analysis.timeline);
  const focusTerms = asTextArray(analysis.focus_terms);
  const missingData = asTextArray(analysis.missing_data);
  const immediate = asTextArray(actions.immediate_actions);
  const verification = asTextArray(actions.verification_actions);
  const prevention = asTextArray(actions.long_term_prevention);
  const scenarioLabel = shortText(analysis.workspace_scenario ?? analysis.scenario, "");
  const modeLabel =
    analysis.workspace_mode === "generated_incident"
      ? "generated incident"
      : analysis.workspace_mode === "current_logs"
        ? "current logs"
        : "log window";
  const scopeLabel = shortText(analysis.scope_label, scenarioLabel ? `generated ${scenarioLabel} incident burst` : modeLabel);
  const chips = [
    shortText(analysis.severity, "info").toUpperCase(),
    shortText(analysis.status, shortText(status, "-")),
    `${shortText(analysis.correlated_events, "0")} events`,
    modeLabel,
    ...focusTerms
  ].filter(Boolean);
  const evidenceItems = evidence.length ? evidence.map((item) => `Bằng chứng log: ${item}`) : timeline.map((item) => `Bằng chứng timeline: ${timelineText(item)}`);
  const analyzeItems = [
    shortText(analysis.summary ?? analysis.impact, "") ? `Tóm tắt phân tích: ${shortText(analysis.summary ?? analysis.impact)}` : "",
    `Trạng thái RCA: ${rcaStatus(analysis.status)}; confidence ${shortText(analysis.confidence, "0")}%; ${shortText(analysis.correlated_events, "0")} correlated event(s) trên ${shortText(analysis.analyzed_events, "0")} analyzed event(s).`,
    ...timeline.map((item) => `Timeline: ${timelineText(item)}`),
    ...missingData.map((item) => `Thiếu dữ liệu: ${item}`),
    shortText(analysis.llm_guidance, "") ? `Gợi ý LLM: ${shortText(analysis.llm_guidance)}` : ""
  ].filter(Boolean);
  const actionItems = rcaActionItems(analysis, [...immediate, ...verification, ...prevention]);
  const commandCards = rcaCommandCards(analysis);

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold">RCA result</h2>
          <p className="mt-1 text-xs text-muted-foreground">{shortText(analysis.incident_id ?? status, "analysis")}</p>
        </div>
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-center text-amber-800">
          <p className="text-lg font-semibold tabular-nums">{shortText(analysis.confidence, "0")}%</p>
          <p className="text-[10px] font-semibold uppercase">confidence</p>
        </div>
      </div>

      <RcaResultBlock title="Most Likely Root Cause">
        <p className="text-sm font-semibold leading-6 text-slate-950">Khả năng cao root cause là: {shortText(analysis.most_likely_root_cause ?? analysis.summary, "-")}</p>
        <p className="mt-2 text-xs text-muted-foreground">
          <span className="font-semibold text-slate-700">Scope:</span> {scopeLabel}
          {scenarioLabel ? <span> · Scenario: {scenarioLabel}</span> : null}
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {chips.map((chip) => (
            <span key={chip} className="rounded-full border border-teal-200 bg-teal-50 px-2 py-1 text-[11px] font-semibold text-teal-700">
              {chip}
            </span>
          ))}
        </div>
      </RcaResultBlock>

      <RcaResultBlock title="Evidence">
        <ul className="space-y-2 text-sm leading-6 text-slate-700">
          {(evidenceItems.length ? evidenceItems : ["Chưa có log evidence được chọn."]).map((item, index) => (
            <li key={index} className="border-l-2 border-teal-300 pl-3">{item}</li>
          ))}
        </ul>
      </RcaResultBlock>

      <RcaResultBlock title="Analyze">
        <ul className="space-y-2 text-sm leading-6 text-slate-700">
          {analyzeItems.map((item, index) => (
            <li key={index} className="border-l-2 border-teal-300 pl-3">{item}</li>
          ))}
        </ul>
      </RcaResultBlock>

      <RcaResultBlock title="Action">
        <ul className="space-y-2 text-sm leading-6 text-slate-700">
          {actionItems.map((item, index) => (
            <li key={index} className="border-l-2 border-teal-300 pl-3">{item}</li>
          ))}
        </ul>
        <div className="mt-4 grid gap-2">
          {commandCards.map((card, index) => (
            <CommandCard key={`${card.phase}-${index}`} phase={card.phase} command={card.command} />
          ))}
        </div>
      </RcaResultBlock>
    </div>
  );
}

export default function LoggingRcaPage() {
  const [impact, setImpact] = useState("");
  const [lookback, setLookback] = useState("1");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [scenario, setScenario] = useState("broadcast_loop");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [incidentScenario, setIncidentScenario] = useState("");
  const [incidentJson, setIncidentJson] = useState("");
  const [sendTelegram, setSendTelegram] = useState(false);
  const [incidentResult, setIncidentResult] = useState<Record<string, unknown> | null>(null);
  const [telegramResult, setTelegramResult] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [incidentBusy, setIncidentBusy] = useState(false);

  const analysis = asRecord(result?.analysis);
  const incidentAnalysis = asRecord(incidentResult?.analysis);

  const run = async (mode: "analyze" | "generate") => {
    setBusy(true);
    try {
      const lookbackHours = Number(lookback) > 0 ? Number(lookback) : 1;
      const body = {
        impact,
        lookback_hours: lookbackHours,
        ...(startTime.trim() && endTime.trim() ? { start_time: startTime.trim(), end_time: endTime.trim() } : {}),
        ...(mode === "generate" ? { scenario } : {})
      };
      setResult(mode === "generate" ? await api.loggingRcaGenerate(body) : await api.loggingRcaAnalyze(body));
    } catch (error) {
      setResult({ status: "error", message: String(error) });
    } finally {
      setBusy(false);
    }
  };

  const clearWorkspace = () => {
    setImpact("");
    setLookback("1");
    setStartTime("");
    setEndTime("");
    setResult(null);
  };

  const sendAsChat = async () => {
    const focus = impact.trim();
    if (!focus) {
      setResult({ status: "error", message: "RCA chat needs an impact/symptom before sending to the Logging agent." });
      return;
    }

    const lookbackHours = Number(lookback);
    const windowText = Number.isFinite(lookbackHours) && lookbackHours > 0 ? ` trong ${lookbackHours} gio` : "";
    const rangeText = startTime.trim() && endTime.trim() ? ` tu ${startTime.trim()} den ${endTime.trim()}` : windowText;
    const sessionId =
      typeof window !== "undefined"
        ? window.sessionStorage.getItem("master_agent_session_id") || `master-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
        : "master-rca-workspace";

    if (typeof window !== "undefined") {
      window.sessionStorage.setItem("master_agent_session_id", sessionId);
    }

    setBusy(true);
    try {
      const chat = await api.masterChat(`/logging phan tich RCA dua tren log hien tai: ${focus}${rangeText}`, sessionId);
      setResult({
        status: chat.status,
        sent_as_chat: true,
        response: chat.response,
        routed_agents: chat.routed_agents,
        timestamp: chat.timestamp
      });
    } catch (error) {
      setResult({ status: "error", message: String(error) });
    } finally {
      setBusy(false);
    }
  };

  const generateIncident = async () => {
    setIncidentBusy(true);
    try {
      const response = await api.loggingIncidentGenerate({
        scenario: incidentScenario,
        send_telegram: sendTelegram
      });
      setIncidentResult(response);
      if (response.incident) {
        setIncidentJson(JSON.stringify(response.incident, null, 2));
      }
    } catch (error) {
      setIncidentResult({ status: "error", message: String(error) });
    } finally {
      setIncidentBusy(false);
    }
  };

  const analyzeIncident = async () => {
    setIncidentBusy(true);
    try {
      let payload: Record<string, unknown>;
      if (incidentJson.trim()) {
        const parsed = JSON.parse(incidentJson);
        payload = parsed && typeof parsed === "object" && !Array.isArray(parsed) ? { incident: parsed } : {};
      } else {
        payload = { scenario: incidentScenario };
      }
      if (sendTelegram) payload.send_telegram = true;
      setIncidentResult(await api.loggingIncidentAnalyze(payload));
    } catch (error) {
      setIncidentResult({ status: "error", message: String(error) });
    } finally {
      setIncidentBusy(false);
    }
  };

  const telegramTest = async (dryRun: boolean) => {
    setIncidentBusy(true);
    try {
      setTelegramResult(await api.loggingTelegramTest({
        incident_id: shortText(incidentAnalysis.incident_id, ""),
        scenario: incidentScenario,
        dry_run: dryRun
      }));
    } catch (error) {
      setTelegramResult({ status: "error", message: String(error) });
    } finally {
      setIncidentBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">Logging</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">RCA workspace</h1>
        <p className="mt-1 text-sm text-muted-foreground">Analyze current logs or generate an incident burst for RCA validation.</p>
      </div>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_150px_220px_220px]">
          <label className="grid gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Impact or symptom</span>
            <textarea
              value={impact}
              onChange={(event) => setImpact(event.target.value)}
              rows={4}
              className="resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/20"
              placeholder="Example: packet loss between app and database, MAC flapping on access switch..."
            />
          </label>
          <label className="grid gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Window (hours)</span>
            <input
              type="number"
              min="0.25"
              max="168"
              step="0.25"
              value={lookback}
              onChange={(event) => setLookback(event.target.value)}
              className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
            />
          </label>
          <label className="grid gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">From</span>
            <input
              type="datetime-local"
              value={startTime}
              onChange={(event) => setStartTime(event.target.value)}
              className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
            />
          </label>
          <label className="grid gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">To</span>
            <input
              type="datetime-local"
              value={endTime}
              onChange={(event) => setEndTime(event.target.value)}
              className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
            />
          </label>
        </div>
        <div className="mt-4 grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
          <label className="grid gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Scenario</span>
            <select
              value={scenario}
              onChange={(event) => setScenario(event.target.value)}
              className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
            >
              <option value="broadcast_loop">broadcast_loop</option>
              <option value="mac_flapping">mac_flapping</option>
              <option value="interface_flapping">interface_flapping</option>
              <option value="storage_latency">storage_latency</option>
              <option value="windows_auth_storm">windows_auth_storm</option>
            </select>
          </label>
          <div className="flex flex-wrap items-end gap-2">
            <button
              onClick={() => run("analyze")}
              disabled={busy}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-wait disabled:opacity-60"
            >
              <SearchCode className="h-4 w-4" />
              Analyze current logs
            </button>
            <button
              onClick={sendAsChat}
              disabled={busy}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border px-4 text-sm font-medium hover:bg-secondary disabled:cursor-wait disabled:opacity-60"
            >
              <MessageSquareText className="h-4 w-4" />
              Send as chat
            </button>
            <button
              onClick={clearWorkspace}
              disabled={busy}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-red-200 px-4 text-sm font-medium text-red-600 hover:bg-red-50 disabled:cursor-wait disabled:opacity-60"
            >
              <X className="h-4 w-4" />
              Clear
            </button>
            <button
              onClick={() => run("generate")}
              disabled={busy}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-border px-4 text-sm font-medium hover:bg-secondary disabled:cursor-wait disabled:opacity-60"
            >
              <Sparkles className="h-4 w-4" />
              Generate and analyze
            </button>
          </div>
        </div>
      </section>

      {result ? (
        <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
          {Object.keys(analysis).length ? (
            <RcaAnalysisResult analysis={analysis} status={result.status} />
          ) : (
            <div>
              <h2 className="text-sm font-semibold">RCA result</h2>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-slate-700">
                {shortText(result.response ?? result.message ?? result.status, "No RCA analysis returned.")}
              </p>
            </div>
          )}
        </section>
      ) : null}

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold">Raw RCA payload</h2>
        <JsonBlock value={result ?? { message: "No RCA run yet." }} />
      </section>

      <section className="rounded-lg border border-border bg-card p-5 shadow-sm">
        <div className="mb-4">
          <h2 className="text-sm font-semibold">Incident RCA lab</h2>
          <p className="mt-1 text-xs text-muted-foreground">Generate or analyze structured RCA incidents and test Telegram delivery.</p>
        </div>
        <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)_180px]">
          <label className="grid gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Scenario</span>
            <input
              value={incidentScenario}
              onChange={(event) => setIncidentScenario(event.target.value)}
              placeholder="optional scenario"
              className="h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-primary/20"
            />
          </label>
          <label className="grid gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Incident JSON</span>
            <textarea
              value={incidentJson}
              onChange={(event) => setIncidentJson(event.target.value)}
              rows={5}
              placeholder='Optional: {"id":"INC-001","events":[]}'
              className="resize-none rounded-lg border border-border bg-background px-3 py-2 font-mono text-xs outline-none focus:ring-2 focus:ring-primary/20"
            />
          </label>
          <div className="space-y-3">
            <label className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs text-muted-foreground">
              <input
                type="checkbox"
                checked={sendTelegram}
                onChange={(event) => setSendTelegram(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
              />
              Send Telegram
            </label>
            <button
              onClick={generateIncident}
              disabled={incidentBusy}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-wait disabled:opacity-60"
            >
              <Sparkles className="h-4 w-4" />
              Generate
            </button>
            <button
              onClick={analyzeIncident}
              disabled={incidentBusy}
              className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-border px-4 text-sm font-medium hover:bg-secondary disabled:cursor-wait disabled:opacity-60"
            >
              <SearchCode className="h-4 w-4" />
              Analyze JSON
            </button>
            <button
              onClick={() => telegramTest(true)}
              disabled={incidentBusy}
              className="inline-flex h-10 w-full items-center justify-center rounded-lg border border-border px-4 text-sm font-medium hover:bg-secondary disabled:cursor-wait disabled:opacity-60"
            >
              Telegram dry-run
            </button>
            <button
              onClick={() => telegramTest(false)}
              disabled={incidentBusy}
              className="inline-flex h-10 w-full items-center justify-center rounded-lg border border-border px-4 text-sm font-medium text-amber-700 hover:bg-amber-50 disabled:cursor-wait disabled:opacity-60"
            >
              Send Telegram test
            </button>
          </div>
        </div>

        {incidentResult ? (
          <div className="mt-5 grid gap-4 lg:grid-cols-3">
            <div className="rounded-lg border border-border bg-slate-50 p-4">
              <p className="text-sm font-semibold">Incident status</p>
              <p className="mt-2 text-sm text-slate-700">{shortText(incidentResult.status)}</p>
              <p className="mt-1 text-xs text-muted-foreground">{shortText(incidentAnalysis.incident_id, "No incident id")}</p>
            </div>
            <div className="rounded-lg border border-border bg-slate-50 p-4 lg:col-span-2">
              <p className="text-sm font-semibold">Most likely root cause</p>
              <p className="mt-2 text-sm leading-6 text-slate-700">
                {shortText(incidentAnalysis.most_likely_root_cause ?? incidentAnalysis.summary, "No analysis returned.")}
              </p>
            </div>
          </div>
        ) : null}

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Incident result</h3>
            <JsonBlock value={incidentResult ?? { message: "No incident RCA run yet." }} maxHeight="max-h-80" />
          </div>
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Telegram test</h3>
            <JsonBlock value={telegramResult ?? { message: "No Telegram test yet." }} maxHeight="max-h-80" />
          </div>
        </div>
      </section>
    </div>
  );
}
