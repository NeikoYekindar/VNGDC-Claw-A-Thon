export interface Server {
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

export interface Check {
  level: "pass" | "fail" | "warn" | "info";
  message: string;
}

export interface Section {
  name: string;
  status: "pass" | "fail" | "warn" | "info";
  pass_count: number;
  fail_count: number;
  warn_count: number;
  info_count: number;
  checks: Check[];
}

export interface Report {
  id: string;
  server_id: string;
  checked_at: string;
  status: string | null;
  sections: Section[] | null;
  error: string | null;
  duration_seconds: number | null;
  analysis: string | null;
}

export interface Task {
  id: string;
  server_id: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  completed_at: string | null;
  report_id: string | null;
  error: string | null;
}

export interface Stats {
  total: number;
  hardened: number;
  partial: number;
  none: number;
  unchecked: number;
}

export interface ServerCreate {
  name: string;
  host: string;
  port?: number;
  username: string;
  password?: string;
  ssh_key?: string;
  os_type: string;
}

export interface AgentStatus {
  connected: boolean;
  url: string;
  error?: string;
  response?: string;
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
  intel_sources?: string[];
  detected_at?: string;
  published_at?: string;
  status?: string;
  known_exploited?: boolean;
  kev?: Record<string, unknown> | null;
  epss?: number;
  epss_percentile?: number;
  exploit_likelihood?: string;
  nvd_cvss_score?: string | number;
  nvd_cvss_vector?: string;
  nvd_severity?: string;
  cwe?: string[];
  fixed_versions?: string[];
  fixed_version?: string;
  risk_score?: number;
  risk_label?: string;
  patch_sla?: string;
  patch_sla_hours?: number;
  patch_plan?: string[];
  risk_priority?: string;
  agent_assessment?: string;
  recommendation?: string;
}

export interface VulnerabilityAssetDetail {
  server: Server;
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
    exploit_likelihoods?: Record<string, number>;
    sla_counts?: Record<string, number>;
  };
  error: string | null;
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

export interface EmergingCveItem {
  cve: string;
  severity?: string;
  cvss?: number;
  epss?: number;
  epss_percentile?: number;
  exploit_likelihood?: string;
  known_exploited?: boolean;
  title?: string;
  description?: string;
  published?: string | null;
  last_modified?: string | null;
  date_added?: string | null;
  due_date?: string | null;
  source?: string;
  references?: string[];
  vendor_project?: string;
  product?: string;
  risk_score?: number;
  risk_label?: string;
  relation: "direct" | "possible" | "not_seen" | string;
  relation_label: string;
  affected_assets: string[];
  matched_packages: string[];
  analysis: string;
  recommendation: string;
}

export interface EmergingCveResponse {
  generated_at: string;
  latest_scan_id: string | null;
  scanned_at: string | null;
  days: number;
  total: number;
  sources: string[];
  errors: string[];
  items: EmergingCveItem[];
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

const base = "/api";

async function req<T>(url: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(base + url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  stats: ()                         => req<Stats>("/stats"),
  servers: ()                       => req<Server[]>("/servers"),
  server: (id: string)              => req<Server>(`/servers/${id}`),
  createServer: (b: ServerCreate)   => req<Server>("/servers", { method: "POST", body: JSON.stringify(b) }),
  deleteServer: (id: string)        => req<void>(`/servers/${id}`, { method: "DELETE" }),
  runCheck: (id: string)            => req<Task>(`/servers/${id}/check`, { method: "POST" }),
  task: (id: string)                => req<Task>(`/tasks/${id}`),
  reports: (id: string)             => req<Report[]>(`/servers/${id}/reports`),
  latestReport: (id: string)        => req<Report>(`/servers/${id}/reports/latest`),
  vulnerabilitySummary: ()          => req<VulnerabilitySummary>("/vulnerabilities/summary"),
  emergingVulnerabilities: (limit = 10, days = 14) =>
    req<EmergingCveResponse>(`/vulnerabilities/emerging?limit=${limit}&days=${days}`),
  vulnerabilitySchedule: ()         => req<VulnerabilitySchedule>("/vulnerabilities/schedule"),
  updateVulnerabilitySchedule: (body: Pick<VulnerabilitySchedule, "enabled" | "interval_seconds" | "include_analysis" | "send_report" | "agent_name">) =>
    req<VulnerabilitySchedule>("/vulnerabilities/schedule", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  vulnerabilityAsset: (serverId: string) =>
    req<VulnerabilityAssetDetail>(`/vulnerabilities/assets/${serverId}`),
  vulnerabilityLatestExportUrl: ()  => `${base}/vulnerabilities/latest/export.xlsx`,
  vulnerabilityAssetExportUrl: (serverId: string) =>
    `${base}/vulnerabilities/assets/${serverId}/export.xlsx`,
  refreshVulnerabilities: (includeAnalysis = true, sendReport = false) =>
    req<VulnerabilitySummary>("/vulnerabilities/refresh", {
      method: "POST",
      body: JSON.stringify({ include_analysis: includeAnalysis, send_report: sendReport }),
    }),
  agentStatus: ()                   => req<AgentStatus>("/agent/status"),
  agentChatHistory: (sessionId: string) =>
    req<StoredChatMessage[]>(`/agent/chat/${encodeURIComponent(sessionId)}/messages`),
  agentChat: (message: string, sessionId: string) =>
    req<{ response: string; timestamp: string }>("/agent/chat", {
      method: "POST",
      body: JSON.stringify({ message, session_id: sessionId }),
    }),
};
