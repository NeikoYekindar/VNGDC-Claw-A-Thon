export interface AgentStatus {
  key: "monitoring" | "logging" | "security" | string;
  name: string;
  section: string;
  connected: boolean;
  active: boolean;
  url: string;
  latency_ms: number | null;
  status: string;
  detail: string;
  checked_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface StoredChatMessage {
  id: string;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ChatSessionSummary {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChildResult {
  key: string;
  name: string;
  section: string;
  ok: boolean;
  answer: string;
  raw?: unknown;
  error?: string | null;
  latency_ms?: number | null;
}

export interface MasterChatResponse {
  status: string;
  response: string;
  routed_agents: string[];
  child_results: ChildResult[];
  timestamp: string;
}

export interface Overview {
  generated_at: string;
  agents: AgentStatus[];
  monitoring: Record<string, unknown>;
  logging: Record<string, unknown>;
  security: Record<string, unknown>;
}

export interface SecurityServer {
  id: string;
  name: string;
  host: string;
  port: number;
  username: string;
  os_type: string;
  created_at: string;
  last_checked_at: string | null;
  last_status: string | null;
}

export interface SecurityCheck {
  level: "pass" | "fail" | "warn" | "info" | string;
  message: string;
}

export interface SecuritySection {
  name: string;
  status: "pass" | "fail" | "warn" | "info" | string;
  pass_count: number;
  fail_count: number;
  warn_count: number;
  info_count: number;
  checks: SecurityCheck[];
}

export interface SecurityReport {
  id: string;
  server_id: string;
  checked_at: string;
  status: string | null;
  sections: SecuritySection[] | null;
  error: string | null;
  duration_seconds: number | null;
  analysis: string | null;
}

export interface SecurityTask {
  id: string;
  server_id: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  completed_at: string | null;
  report_id: string | null;
  error: string | null;
}

export interface SecurityStats {
  total: number;
  hardened: number;
  partial: number;
  none: number;
  unchecked: number;
}

export interface VulnerabilityItem {
  cve?: string;
  severity?: string;
  score?: string | number;
  package?: string;
  version?: string;
  agent?: string;
  agent_id?: string;
  os?: string;
  title?: string;
  reference?: string | string[];
  detected_at?: string;
  published_at?: string;
  known_exploited?: boolean;
  epss?: number;
  exploit_likelihood?: string;
  nvd_cvss_score?: string | number;
  fixed_version?: string;
  risk_score?: number;
  risk_priority?: string;
  patch_sla?: string;
  patch_sla_hours?: number;
  patch_plan?: string[];
  agent_assessment?: string;
  recommendation?: string;
}

export interface VulnerabilitySummary {
  latest_scan_id: string | null;
  scanned_at: string | null;
  status: string;
  source: string | null;
  total: number;
  fetched: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  analysis: string | null;
  error: string | null;
  items: VulnerabilityItem[];
}

export interface VulnerabilitySchedule {
  enabled: boolean;
  interval_seconds: number;
  include_analysis: boolean;
  send_report: boolean;
  agent_name: string;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: string | null;
  last_error: string | null;
  updated_at: string | null;
}

export interface VulnerabilityAssetDetail {
  server: SecurityServer;
  latest_scan_id: string | null;
  scanned_at: string | null;
  status: string;
  source: string | null;
  total: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
  items: VulnerabilityItem[];
  assessment: {
    priority: string;
    verdict: string;
    summary: string;
    counts: {
      critical: number;
      high: number;
      medium: number;
      low: number;
    };
    top_packages: Array<{ package: string; count: number }>;
    next_steps: string[];
    known_exploited?: number;
    max_risk_score?: number;
    max_epss?: number;
  };
  error: string | null;
}

const base = "/api";

async function req<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(base + url, {
    headers: { "Content-Type": "application/json" },
    ...opts
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

function unwrapArray(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (value && typeof value === "object" && Array.isArray((value as Record<string, unknown>).value)) {
    return (value as Record<string, unknown>).value as unknown[];
  }
  return [];
}

export const api = {
  overview: () => req<Overview>("/overview"),
  agentsStatus: () => req<AgentStatus[]>("/agents/status"),
  masterChatSessions: () => req<ChatSessionSummary[]>("/master/chat/sessions"),
  createMasterChatSession: (title?: string) =>
    req<ChatSessionSummary>("/master/chat/sessions", {
      method: "POST",
      body: JSON.stringify({ title })
    }),
  masterChatHistory: (sessionId: string) =>
    req<StoredChatMessage[]>(`/master/chat/${encodeURIComponent(sessionId)}/messages`),
  masterChat: (message: string, sessionId: string, targetAgents?: string[]) =>
    req<MasterChatResponse>("/master/chat", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId, target_agents: targetAgents })
    }),

  monitoringInventory: (type?: string) =>
    req<Record<string, unknown>>(`/monitoring/inventory${type ? `?type=${encodeURIComponent(type)}` : ""}`),
  monitoringUploadInventory: (csvContent: string) =>
    req<Record<string, unknown>>("/monitoring/inventory/upload", {
      method: "POST",
      body: JSON.stringify({ csv_content: csvContent })
    }),
  monitoringBatches: () => req<Record<string, unknown>>("/monitoring/batches"),
  monitoringReceiveAlert: (alert: Record<string, unknown>) =>
    req<Record<string, unknown>>("/monitoring/alert", {
      method: "POST",
      body: JSON.stringify({ alert })
    }),
  monitoringSuppressions: () => req<Record<string, unknown>>("/monitoring/suppressions"),
  monitoringCreateSuppression: (body: { instance: string; hours: number; reason: string }) =>
    req<Record<string, unknown>>("/monitoring/suppressions", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  monitoringRemoveSuppression: (instance: string) =>
    req<Record<string, unknown>>("/monitoring/suppressions/remove", {
      method: "POST",
      body: JSON.stringify({ instance })
    }),
  monitoringKnowledge: () => req<Record<string, unknown>>("/monitoring/knowledge"),
  monitoringReadKnowledge: (filename: string) =>
    req<Record<string, unknown>>("/monitoring/knowledge/read", {
      method: "POST",
      body: JSON.stringify({ filename })
    }),
  monitoringUploadKnowledge: (filename: string, content: string) =>
    req<Record<string, unknown>>("/monitoring/knowledge/upload", {
      method: "POST",
      body: JSON.stringify({ filename, content })
    }),
  monitoringDeleteKnowledge: (filename: string) =>
    req<Record<string, unknown>>("/monitoring/knowledge/delete", {
      method: "POST",
      body: JSON.stringify({ filename })
    }),
  monitoringSimulate: () => req<Record<string, unknown>>("/monitoring/simulate", { method: "POST" }),
  monitoringTriggerBatch: (batchId: string) =>
    req<Record<string, unknown>>("/monitoring/trigger-batch", {
      method: "POST",
      body: JSON.stringify({ batch_id: batchId })
    }),

  loggingStatus: () => req<Record<string, unknown>>("/logging/status"),
  loggingLatestIncident: () => req<Record<string, unknown>>("/logging/incidents/latest"),
  loggingIncidentGenerate: (body: Record<string, unknown>) =>
    req<Record<string, unknown>>("/logging/incidents/generate", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  loggingIncidentAnalyze: (body: Record<string, unknown>) =>
    req<Record<string, unknown>>("/logging/incidents/analyze", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  loggingTelegramTest: (body: Record<string, unknown>) =>
    req<Record<string, unknown>>("/logging/telegram/test", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  loggingRcaAnalyze: (body: Record<string, unknown>) =>
    req<Record<string, unknown>>("/logging/rca/analyze", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  loggingRcaGenerate: (body: Record<string, unknown>) =>
    req<Record<string, unknown>>("/logging/rca/generate", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  loggingRuntimeControl: (body: Record<string, unknown>) =>
    req<Record<string, unknown>>("/logging/runtime-control", {
      method: "POST",
      body: JSON.stringify(body)
    }),

  securityStats: () => req<SecurityStats>("/security/stats"),
  securityServers: () => req<unknown>("/security/servers").then((value) => unwrapArray(value) as SecurityServer[]),
  securityServer: (serverId: string) => req<SecurityServer>(`/security/servers/${encodeURIComponent(serverId)}`),
  securityCreateServer: (body: Record<string, unknown>) =>
    req<SecurityServer>("/security/servers", {
      method: "POST",
      body: JSON.stringify(body)
    }),
  securityDeleteServer: (serverId: string) =>
    req<void>(`/security/servers/${encodeURIComponent(serverId)}`, {
      method: "DELETE"
    }),
  securityRunCheck: (serverId: string) =>
    req<SecurityTask>(`/security/servers/${encodeURIComponent(serverId)}/check`, {
      method: "POST"
    }),
  securityTask: (taskId: string) => req<SecurityTask>(`/security/tasks/${encodeURIComponent(taskId)}`),
  securityReports: (serverId: string) =>
    req<unknown>(`/security/servers/${encodeURIComponent(serverId)}/reports`).then((value) => unwrapArray(value) as SecurityReport[]),
  securityLatestReport: (serverId: string) =>
    req<SecurityReport>(`/security/servers/${encodeURIComponent(serverId)}/reports/latest`),
  securityReportExportUrl: (serverId: string, reportId: string) =>
    `${base}/security/servers/${encodeURIComponent(serverId)}/reports/${encodeURIComponent(reportId)}/export.xlsx`,
  securityLatestReportExportUrl: (serverId: string) =>
    `${base}/security/servers/${encodeURIComponent(serverId)}/reports/latest/export.xlsx`,
  securityAgentStatus: () => req<Record<string, unknown>>("/security/agent/status"),
  securityVulnerabilitySummary: () => req<VulnerabilitySummary>("/security/vulnerabilities/summary"),
  securityVulnerabilitySchedule: () => req<VulnerabilitySchedule>("/security/vulnerabilities/schedule"),
  securityUpdateVulnerabilitySchedule: (
    body: Pick<VulnerabilitySchedule, "enabled" | "interval_seconds" | "include_analysis" | "send_report" | "agent_name">
  ) =>
    req<VulnerabilitySchedule>("/security/vulnerabilities/schedule", {
      method: "PUT",
      body: JSON.stringify(body)
    }),
  securityVulnerabilityAsset: (serverId: string) =>
    req<VulnerabilityAssetDetail>(`/security/vulnerabilities/assets/${encodeURIComponent(serverId)}`),
  securityVulnerabilityLatestExportUrl: () => `${base}/security/vulnerabilities/latest/export.xlsx`,
  securityVulnerabilityAssetExportUrl: (serverId: string) =>
    `${base}/security/vulnerabilities/assets/${encodeURIComponent(serverId)}/export.xlsx`,
  securityEmerging: (limit = 10, days = 14) =>
    req<Record<string, unknown>>(`/security/vulnerabilities/emerging?limit=${limit}&days=${days}`),
  securityRefreshVulnerabilities: (includeAnalysis = true, sendReport = false) =>
    req<VulnerabilitySummary>("/security/vulnerabilities/refresh", {
      method: "POST",
      body: JSON.stringify({ include_analysis: includeAnalysis, send_report: sendReport })
    })
};
