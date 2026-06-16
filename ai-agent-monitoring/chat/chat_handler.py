"""
Chat Handler -- natural language interface for server investigation.

Intent types:
  - chat               : general conversation / greeting
  - investigate        : SSH into a specific server
  - need_host          : investigation intent but no host specified
  - query_all_servers  : query Prometheus metrics across all servers
  - query_active_alerts: query Alertmanager for active alerts
  - correlate          : analyze correlation between current events

Response goes ONLY to the API caller, NOT to Telegram.
"""

import json
import logging
import re
from typing import Optional

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from executors.ssh_executor import SSHExecutor
from executors.command_policy import CommandPolicy
from metrics.metrics_collector import MetricsCollector
from utils.knowledge_loader import get_relevant_knowledge
from utils.inventory import get_servers, get_inventory_summary, load_inventory
from utils.monitoring_client import (
    query_alertmanager_active, format_alertmanager_summary,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are an AI Agent for server monitoring and root cause analysis.
You help investigate servers via SSH, query Prometheus metrics, check active alerts, and correlate events.

Analyze the user's message and respond with ONLY a valid JSON object (no markdown, no explanation).

=== Intent 1 -- General conversation (greetings, questions about you, unrelated topics):
{"type": "chat", "reply": "<natural reply in same language as user>"}

=== Intent 2 -- SSH investigation on a SPECIFIC host:
{"type": "investigate", "host": "<IP or hostname>", "check_type": "<cpu|memory|disk|network|process|logs|os|ports|general>", "commands": ["cmd1", "cmd2"]}

Rules for investigate:
- Select ONLY the minimum commands needed to answer the question (1-4 max)
- "CPU hien tai bao nhieu?" -> only: ["top -bn1 | head -5"] or ["mpstat 1 1"]
- "RAM con bao nhieu?" -> only: ["free -h"]
- "Disk day chua?" -> only: ["df -h"]
- "Port nao dang listen?" -> only: ["ss -tuln"]
- Do NOT include unrelated commands like uptime when user asks only about CPU
- Read-only commands ONLY (no rm, kill, reboot)

=== Intent 3 -- Investigation intent but NO specific host:
{"type": "need_host", "reply": "<ask for server IP/hostname in same language as user>"}

=== Intent 4 -- Query metrics across ALL servers (via Prometheus):
{"type": "query_all_servers", "metric_type": "<cpu|memory|disk|network|uptime|custom>", "promql": "<PromQL query>", "description": "<what we are checking>"}

Use this when user says "tat ca server", "all servers", "toan bo may chu", etc.
Examples:
- "CPU tat ca server" -> {"type":"query_all_servers","metric_type":"cpu","promql":"100 - (avg by(instance)(rate(node_cpu_seconds_total{mode='idle'}[5m]))*100)","description":"CPU usage across all servers"}
- "RAM con bao nhieu tren tat ca server" -> {"type":"query_all_servers","metric_type":"memory","promql":"(1 - node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)*100","description":"Memory usage across all servers"}
- "Disk usage tat ca server" -> {"type":"query_all_servers","metric_type":"disk","promql":"100 - (node_filesystem_avail_bytes{mountpoint='/'}/node_filesystem_size_bytes{mountpoint='/'}*100)","description":"Disk usage on root filesystem"}
- "Uptime tat ca server" -> {"type":"query_all_servers","metric_type":"uptime","promql":"node_time_seconds - node_boot_time_seconds","description":"Server uptime in seconds"}

=== Intent 5 -- Check active alerts (Alertmanager):
{"type": "query_active_alerts", "scope": "server", "description": "<what user asked>"}

Use this when user asks: "co alert gi khong", "alert nao dang firing", "co van de gi khong", "hien tai he thong co canh bao gi".

=== Intent 6 -- Correlate / analyze events:
{"type": "correlate", "description": "<what to correlate>"}

Use this when user asks: "cac su kien nay co lien quan khong", "nguyen nhan goc re la gi", "tai sao nhieu server cung luc", "co pattern gi khong".

### Knowledge Base (dung khi lien quan den cau hoi):
{knowledge}
"""

_SUMMARY_SYSTEM_PROMPT = """You are a DevOps assistant summarizing server investigation results.
Respond in the same language as the user's original message.

Structure:
1. **Status**: one-line verdict (normal / needs attention / critical)
2. **Findings**: key observations from the outputs
3. **Recommendation**: what to do next (if anything)

Be concise. Never expose passwords, tokens, or credentials.
"""

_CORRELATION_SYSTEM_PROMPT = """You are a DevOps expert analyzing event correlation across infrastructure.
Respond in the same language as the user.

Given the active alerts and recent events, analyze:
1. **Timeline**: thu tu xay ra su kien
2. **Pattern**: diem chung (cung subnet, cung service, cung thoi diem)
3. **Root Cause Hypothesis**: gia thuyet nguyen nhan goc re
4. **Recommendation**: hanh dong tiep theo can lam

Be specific. Reference actual hostnames, IPs, alert names from the data provided.
"""


# ---------------------------------------------------------------------------
# Chat Handler
# ---------------------------------------------------------------------------

class ChatHandler:
    def __init__(self, llm: ChatOpenAI, ssh_executor: SSHExecutor, command_policy: CommandPolicy):
        self.llm = llm
        self.ssh = ssh_executor
        self.policy = command_policy
        self.metrics = MetricsCollector()

    def handle(self, message: str, default_host: Optional[str] = None) -> dict:
        """Main entry point. Returns dict with summary and details."""
        decision = self._decide(message)
        dtype = decision.get("type", "chat")

        if dtype == "chat":
            return self._result(summary=decision.get("reply", "Xin chao!"))

        if dtype == "need_host":
            if default_host:
                decision["host"] = default_host
                dtype = "investigate"
            else:
                return self._result(summary=decision.get(
                    "reply", "Ban muon kiem tra server nao? Vui long cung cap IP hoac hostname."
                ))

        if dtype == "investigate":
            return self._handle_investigate(message, decision)

        if dtype == "query_all_servers":
            return self._handle_query_all_servers(message, decision)

        if dtype == "query_active_alerts":
            return self._handle_query_active_alerts(message, decision)

        if dtype == "correlate":
            return self._handle_correlate(message, decision)

        # Fallback
        return self._result(summary=decision.get("reply", "Toi khong hieu yeu cau nay."))

    # -- SSH investigation ----------------------------------------------------

    def _handle_investigate(self, message: str, decision: dict) -> dict:
        raw_host = decision.get("host", "")
        host = self._resolve_host(raw_host)
        if host != raw_host:
            logger.info("Host resolved: %r -> %r", raw_host, host)
        check_type = decision.get("check_type", "general")
        requested_cmds = decision.get("commands", [])

        # Filter through allowlist -- keep only what's permitted
        allowed = [c for c in requested_cmds if self.policy.is_allowed(c)]
        # Fallback only if LLM gave no valid commands at all
        if not allowed:
            allowed = self.policy.get_commands_for_check_type(check_type)

        # SSH -- run at most 5 commands
        raw_results = []
        for cmd in allowed[:5]:
            try:
                r = self.ssh.run(host=host, command=cmd)
                raw_results.append({
                    "command": cmd,
                    "stdout": (r.stdout or "")[:2000],
                    "stderr": (r.stderr or "")[:500],
                    "exit_code": r.exit_code,
                    "error": r.error,
                })
                # Stop on connection failure
                if r.error and _is_connection_error(r.error):
                    raw_results[-1]["stdout"] = ""
                    break
            except Exception as exc:
                raw_results.append({"command": cmd, "stdout": "", "stderr": str(exc), "exit_code": -1, "error": str(exc)})
                break

        knowledge = get_relevant_knowledge(check_type, message)
        summary = self._summarize(message, host, check_type, raw_results, knowledge)
        return {
            "host": host,
            "check_type": check_type,
            "commands_run": [r["command"] for r in raw_results],
            "results": raw_results,
            "summary": summary,
            "error": None,
        }

    # -- Prometheus query for all servers -------------------------------------

    def _handle_query_all_servers(self, message: str, decision: dict) -> dict:
        promql = decision.get("promql", "")
        metric_type = decision.get("metric_type", "custom")
        description = decision.get("description", message)

        if not promql:
            return self._result(
                summary="Khong the tao PromQL query tu cau hoi nay. Ban co the hoi cu the hon khong?",
                check_type=metric_type,
            )

        trend = self.metrics.query_prometheus(promql)
        if trend.error:
            return self._result(
                summary=f"Khong the query Prometheus: {trend.error}",
                check_type=metric_type,
                error=trend.error,
            )

        servers = get_servers()
        server_ctx = f"Inventory: {len(servers)} servers" if servers else "Inventory: chua co"

        summary = self._summarize_prometheus_result(
            user_message=message,
            description=description,
            promql=promql,
            raw_data=trend.raw_summary,
            server_context=server_ctx,
        )

        return {
            "host": "all-servers",
            "check_type": metric_type,
            "commands_run": [f"PromQL: {promql}"],
            "results": [{"command": promql, "stdout": trend.raw_summary, "stderr": "", "exit_code": 0}],
            "summary": summary,
            "error": None,
        }

    def _summarize_prometheus_result(
        self, user_message: str, description: str, promql: str, raw_data: str, server_context: str
    ) -> str:
        prompt = (
            f"User asked: {user_message}\n"
            f"Query: {description}\n"
            f"PromQL: {promql}\n"
            f"{server_context}\n\n"
            f"Prometheus response:\n{raw_data}\n\n"
            "Tom tat ket qua theo ngon ngu cua user. Highlight cac server co gia tri cao nhat/bat thuong."
        )
        try:
            resp = self.llm.invoke([
                SystemMessage(content=_SUMMARY_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            return resp.content
        except Exception as exc:
            logger.error("_summarize_prometheus_result failed: %s", exc)
            return f"Query thanh cong nhung khong tom tat duoc: {raw_data[:500]}"

    # -- Active alerts from Alertmanager -------------------------------------

    def _handle_query_active_alerts(self, message: str, decision: dict) -> dict:
        try:
            alerts = query_alertmanager_active()
        except ConnectionError as exc:
            return self._result(
                summary=f"Khong the ket noi Alertmanager: {exc}",
                check_type="alerts",
                error=str(exc),
            )

        raw_summary = format_alertmanager_summary(alerts)

        prompt = (
            f"User asked: {message}\n\n"
            f"{raw_summary}\n\n"
            "Tom tat tinh trang hien tai theo ngon ngu cua user. "
            "Neu co alert nghiem trong, highlight va de xuat hanh dong."
        )
        try:
            resp = self.llm.invoke([
                SystemMessage(content=_SUMMARY_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            interpreted = resp.content
        except Exception:
            interpreted = raw_summary

        return {
            "host": "alertmanager",
            "check_type": "active_alerts",
            "commands_run": [f"GET {_alertmanager_url()}/api/v2/alerts"],
            "results": [{"command": "alertmanager_query", "stdout": raw_summary, "stderr": "", "exit_code": 0}],
            "summary": interpreted,
            "alert_count": len(alerts),
            "alerts": alerts,
            "error": None,
        }

    # -- Event correlation ----------------------------------------------------

    def _handle_correlate(self, message: str, decision: dict) -> dict:
        try:
            alerts = query_alertmanager_active()
            alert_ctx = format_alertmanager_summary(alerts)
        except Exception as exc:
            alert_ctx = f"Khong lay duoc alert tu Alertmanager: {exc}"
            alerts = []

        inv = get_inventory_summary()
        inv_ctx = (
            f"He thong co {inv['total']} thiet bi: "
            f"{inv['servers']} server ({', '.join(inv['server_list'][:10])})"
        )

        prompt = (
            f"User asked: {message}\n\n"
            f"=== Active Alerts ===\n{alert_ctx}\n\n"
            f"=== Infrastructure ===\n{inv_ctx}\n\n"
            "Phan tich tuong quan giua cac su kien tren."
        )
        try:
            resp = self.llm.invoke([
                SystemMessage(content=_CORRELATION_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            summary = resp.content
        except Exception as exc:
            logger.error("correlate LLM failed: %s", exc)
            summary = f"Khong the phan tich tuong quan: {exc}\n\n{alert_ctx}"

        return {
            "host": "multi",
            "check_type": "correlation",
            "commands_run": ["alertmanager_query", "inventory_check"],
            "results": [{"command": "correlation_analysis", "stdout": summary, "stderr": "", "exit_code": 0}],
            "summary": summary,
            "alert_count": len(alerts),
            "error": None,
        }

    # -- Internal helpers -----------------------------------------------------

    def _resolve_host(self, host: str) -> str:
        """Resolve hostname to IP using inventory. Returns IP if found, else original host."""
        if not host:
            return host
        # Already looks like an IP
        import re as _re
        if _re.match(r"^\d+\.\d+\.\d+\.\d+$", host.strip()):
            return host.strip()
        # Lookup in inventory (case-insensitive hostname match)
        host_lower = host.strip().lower()
        for row in load_inventory():
            if row.get("hostname", "").strip().lower() == host_lower:
                ip = row.get("ip", "").strip()
                if ip:
                    logger.info("Resolved hostname %r -> %s", host, ip)
                    return ip
        return host  # Not found, return as-is

    def _decide(self, message: str) -> dict:
        """Single LLM call: parse intent and return structured decision."""
        try:
            knowledge = get_relevant_knowledge()
            # Inject inventory so LLM knows available servers
            inv_rows = load_inventory()
            inv_lines = "\n".join(
                f"  - hostname={r.get('hostname','')}  ip={r.get('ip','')}  type={r.get('type','')}"
                for r in inv_rows[:30]
            )
            inv_section = f"\n\n### Server Inventory (dung de phan giai hostname -> IP):\n{inv_lines}" if inv_rows else ""
            system = _SYSTEM_PROMPT.replace("{knowledge}", (knowledge or "(chua co knowledge base)") + inv_section)
            resp = self.llm.invoke([
                SystemMessage(content=system),
                HumanMessage(content=message),
            ])
            text = resp.content.strip()
            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            return json.loads(text)
        except Exception as exc:
            logger.error("ChatHandler._decide failed: %s", exc)
            return {"type": "chat", "reply": "Xin loi, toi gap su co khi xu ly yeu cau. Ban thu lai nhe?"}

    def _summarize(
        self, user_message: str, host: str, check_type: str, results: list, knowledge: str
    ) -> str:
        output_text = "\n\n".join(
            f"$ {r['command']}\n{r['stdout'] or r.get('stderr') or r.get('error') or '(no output)'}"
            for r in results
        )
        knowledge_section = f"\n\n## Knowledge Base\n{knowledge}" if knowledge else ""
        human = (
            f"User asked: {user_message}\n"
            f"Host: {host} | Check type: {check_type}\n\n"
            f"Command outputs:\n{output_text or 'No commands executed.'}"
            f"{knowledge_section}"
        )
        try:
            resp = self.llm.invoke([
                SystemMessage(content=_SUMMARY_SYSTEM_PROMPT),
                HumanMessage(content=human),
            ])
            return resp.content
        except Exception as exc:
            logger.error("ChatHandler._summarize failed: %s", exc)
            return f"Da dieu tra {host} nhung khong tong hop duoc ket qua: {exc}"

    @staticmethod
    def _result(
        summary: str,
        host: Optional[str] = None,
        check_type: Optional[str] = None,
        commands_run: Optional[list] = None,
        results: Optional[list] = None,
        error: Optional[str] = None,
    ) -> dict:
        return {
            "host": host,
            "check_type": check_type,
            "commands_run": commands_run or [],
            "results": results or [],
            "summary": summary,
            "error": error,
        }


# -- Module-level helpers -----------------------------------------------------

def _is_connection_error(error: str) -> bool:
    err = error.lower()
    return any(k in err for k in [
        "timed out", "connection refused", "no route to host",
        "name or service not known", "network unreachable",
        "connection reset", "no existing session", "unable to connect",
    ])


def _alertmanager_url() -> str:
    from config import config
    return config.monitoring.alertmanager_url
