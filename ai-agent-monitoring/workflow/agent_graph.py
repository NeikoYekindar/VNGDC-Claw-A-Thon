"""
LangGraph workflow for Alert RCA Agent.

State flows through nodes:
  analyze_alerts → evaluate_relevance →(low)→ generate_report
                                      →(high/med)→ investigate
                                                  → analyze_root_cause
                                                  → recommend_fix
                                                  → generate_report
                                                  → send_to_teams → END
"""

from typing import Annotated, Any, Optional, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from analyzers import AlertAnalyzer, FixRecommender, RelevanceEvaluator, RootCauseAnalyzer
from config import config, settings
from executors import SSHExecutor, get_commands_for_alert_type
from metrics import MetricsCollector
from models.alert import Alert
from models.batch import AlertBatch
from models.report import BatchReport, Confidence, Impact, InvestigationStatus, Relevance, RecommendedFix
from reporters.telegram_reporter import TelegramReporter
from utils.logger import log_rca_result
from utils.suppression import is_suppressed


# ---------------------------------------------------------------------------
# Graph state
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    batch_id: str
    alerts: list[Alert]
    alert_summaries: list[dict]
    relevance: str
    impact: str
    relevance_reason: str
    investigation_steps: list[dict]
    metrics_trends: list[dict]
    evidence: list[str]
    root_cause: str
    confidence: str
    recommended_fix: dict
    report_markdown: str
    report_sent: bool
    status: str
    error: Optional[str]
    messages: Annotated[list, add_messages]


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(llm: ChatOpenAI) -> Any:
    """Build and compile the LangGraph StateGraph."""

    alert_analyzer = AlertAnalyzer(llm)
    relevance_evaluator = RelevanceEvaluator(llm)
    rca_analyzer = RootCauseAnalyzer(llm)
    fix_recommender = FixRecommender(llm)
    ssh_executor = SSHExecutor()
    metrics_collector = MetricsCollector()
    teams_reporter = TelegramReporter()

    # ------------------------------------------------------------------ nodes

    def analyze_alerts(state: AgentState) -> dict:
        summaries = alert_analyzer.analyze_batch(state["alerts"])
        return {"alert_summaries": summaries, "status": "analyzed"}

    def evaluate_relevance(state: AgentState) -> dict:
        result = relevance_evaluator.evaluate(state["alerts"], state["alert_summaries"])
        return {
            "relevance": result["relevance"],
            "impact": result["impact"],
            "relevance_reason": result.get("reason", ""),
            "status": "relevance_evaluated",
        }

    def _plan_commands(alert_name: str, alert_description: str, summaries: list[dict]) -> list[str]:
        """Ask LLM to select diagnostic commands, prioritizing knowledge base content."""
        from utils.knowledge_loader import get_relevant_knowledge
        from executors.command_policy import is_allowed, get_commands_for_alert_type
        from langchain_core.messages import SystemMessage, HumanMessage
        import json, re

        knowledge = get_relevant_knowledge()
        knowledge_section = f"\n\n## Knowledge Base (ưu tiên dùng lệnh từ đây):\n{knowledge}" if knowledge else ""

        system = f"""Bạn là SRE assistant lên kế hoạch điều tra alert.
Nhiệm vụ: Chọn tối đa 6 lệnh shell READ-ONLY để điều tra nguyên nhân alert trên Linux server.

### Quy tắc chọn lệnh (theo thứ tự ưu tiên):
1. Nếu Knowledge Base bên dưới có phần "Các lệnh điều tra" liên quan → dùng các lệnh đó
2. Nếu không → dùng kiến thức từ training của bạn

### Lệnh được phép (read-only):
top, ps, free, df, du, ss, ip, uptime, uname, cat /etc/os-release, cat /proc/meminfo,
journalctl, tail, grep, lsblk, dmesg, vmstat, mpstat, iostat, systemctl status,
ls -lh /var/log, find /var/log, hostname, ping, netstat, cat /var/log/syslog

### Lệnh KHÔNG được phép:
rm, kill, reboot, shutdown, passwd, chmod, mkfs, dd, iptables -F{knowledge_section}

Trả về ONLY JSON array: ["lệnh1", "lệnh2", ...]"""

        alert_context = (
            f"Alert: {alert_name}\n"
            f"Description: {alert_description}\n"
            f"Summaries: {json.dumps(summaries[:3], ensure_ascii=False)}"
        )

        try:
            resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=alert_context)])
            text = resp.content.strip()
            text = re.sub(r"^```[a-z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
            candidates = json.loads(text)
            if isinstance(candidates, list):
                allowed = [c for c in candidates if isinstance(c, str) and is_allowed(c)]
                if allowed:
                    return allowed[:6]
        except Exception as exc:
            print(f"[investigate] _plan_commands failed: {exc}", flush=True)

        # Fallback to static mapping
        return get_commands_for_alert_type(alert_name)

    def investigate(state: AgentState) -> dict:
        """SSH into instances — commands chosen by LLM from knowledge base first."""
        steps: list[dict] = []
        trends: list[dict] = []

        seen_instances: set[str] = set()
        for alert in state["alerts"]:
            if not alert.instance or alert.instance in seen_instances:
                continue
            if is_suppressed(alert.instance):
                print(f"[investigate] Skip {alert.instance} — đang trong maintenance window.", flush=True)
                continue
            seen_instances.add(alert.instance)

            # LLM selects commands using knowledge base
            commands = _plan_commands(
                alert.alert_name,
                alert.description or "",
                state.get("alert_summaries", []),
            )

            results = ssh_executor.run_multiple(alert.instance, commands, state["batch_id"])
            for r in results:
                steps.append({
                    "host": alert.instance,
                    "command": r.command,
                    "stdout": r.stdout[:800],
                    "exit_code": r.exit_code,
                    "error": r.error,
                })

            # Metrics
            metric_results = metrics_collector.collect_for_alert(alert.instance, alert.metrics_url)
            trends.extend([m.to_dict() for m in metric_results])

        return {
            "investigation_steps": steps,
            "metrics_trends": trends,
            "status": "investigated",
        }

    def analyze_root_cause(state: AgentState) -> dict:
        result = rca_analyzer.analyze(
            state["alert_summaries"],
            state["investigation_steps"],
            state["metrics_trends"],
        )
        conf = result["confidence"]
        conf_val = conf.value if hasattr(conf, "value") else str(conf).split(".")[-1].lower()
        log_rca_result(state["batch_id"], result["root_cause"], conf_val)
        return {
            "root_cause": result["root_cause"],
            "evidence": result["evidence"],
            "confidence": conf_val,
            "status": "rca_done",
        }

    def recommend_fix(state: AgentState) -> dict:
        result = fix_recommender.recommend(
            state["root_cause"],
            state["alert_summaries"],
            state["evidence"],
        )
        return {
            "recommended_fix": result,
            "status": "fix_recommended",
        }

    def generate_report(state: AgentState) -> dict:
        """Format HTML report for Telegram."""
        from reporters.telegram_reporter import escape_html as e
        from datetime import datetime

        alerts    = state["alerts"]
        batch_id  = state["batch_id"]
        relevance = state.get("relevance", Relevance.MEDIUM)
        confidence= state.get("confidence", Confidence.LOW)
        root_cause= state.get("root_cause", "Chưa điều tra.")
        fix       = state.get("recommended_fix", {})
        evidence  = state.get("evidence", [])
        steps     = state.get("investigation_steps", [])
        is_low    = relevance in (Relevance.LOW, "low")

        first  = alerts[0] if alerts else None
        instance = first.instance if first else "unknown"
        sev_raw  = str(first.severity) if first else "unknown"
        ts = (first.timestamp.strftime("%d/%m/%Y %H:%M")
              if first and first.timestamp
              else datetime.utcnow().strftime("%d/%m/%Y %H:%M"))

        sev_icon  = {"Severity.CRITICAL": "🔴", "Severity.WARNING": "🟡", "Severity.INFO": "🔵"}.get(sev_raw, "⚪")
        conf_icon = {"Confidence.HIGH": "✅", "Confidence.MEDIUM": "🟡", "Confidence.LOW": "❓"}.get(str(confidence), "❓")
        alert_names = ", ".join({a.alert_name for a in alerts})

        # ── Header ───────────────────────────────────────────────────────────
        lines = [
            f"🚨 <b>CẢNH BÁO: {e(alert_names)}</b>",
            "",
            f"🖥  <b>Server:</b> <code>{e(instance)}</code>",
            f"⏰ <b>Thời gian:</b> {e(ts)} UTC",
            f"{sev_icon} <b>Mức độ:</b> {e(sev_raw.replace('Severity.', ''))}",
            f"🆔 <b>Batch:</b> <code>{e(batch_id)}</code>",
        ]

        if is_low:
            lines += [
                "",
                "━━━━━━━━━━━━━━━━━━━━━━",
                "💤 <b>Mức độ thấp — Không điều tra</b>",
                e(state.get("relevance_reason", "Alert không quan trọng với hạ tầng hiện tại.")),
            ]
        else:
            # Command results
            lines += ["", "━━━━━━━━━━━━━━━━━━━━━━",
                      "🔎 <b>KẾT QUẢ KIỂM TRA</b>",
                      "━━━━━━━━━━━━━━━━━━━━━━"]
            if steps:
                for step in steps[:6]:
                    icon = "✅" if step.get("exit_code") == 0 else "❌"
                    cmd = e(step["command"])
                    stdout = step.get("stdout", "").strip()
                    if stdout:
                        # Show first 2 lines of output
                        preview = " | ".join(stdout.splitlines()[:2])[:120]
                        lines.append(f"{icon} <code>{cmd}</code>")
                        lines.append(f"   ↳ <i>{e(preview)}</i>")
                    else:
                        lines.append(f"{icon} <code>{cmd}</code> — <i>không có output</i>")
            else:
                lines.append("❌ <i>SSH không thực hiện được.</i>")

            # Root cause
            lines += [
                "",
                "━━━━━━━━━━━━━━━━━━━━━━",
                "🎯 <b>NGUYÊN NHÂN</b>",
                "━━━━━━━━━━━━━━━━━━━━━━",
                e(root_cause),
                f"{conf_icon} <b>Độ tin cậy:</b> {e(str(confidence).replace('Confidence.', ''))}",
            ]

            # Evidence as table
            if evidence:
                lines += ["", "📌 <b>Bằng chứng:</b>"]
                for ev in evidence[:4]:
                    lines.append(f"  • {e(ev)}")

            # Fix recommendations
            lines += [
                "",
                "━━━━━━━━━━━━━━━━━━━━━━",
                "🔧 <b>KHUYẾN NGHỊ</b>",
                "━━━━━━━━━━━━━━━━━━━━━━",
            ]
            if fix.get("immediate"):
                lines.append("⚡ <b>Ngay lập tức:</b>")
                for a in fix["immediate"][:3]:
                    lines.append(f"  • {e(a)}")
            if fix.get("long_term"):
                lines.append("📅 <b>Dài hạn:</b>")
                for a in fix["long_term"][:3]:
                    lines.append(f"  • {e(a)}")
            if fix.get("need_human_approval"):
                lines.append("⚠️ <b>Cần phê duyệt:</b>")
                for a in fix["need_human_approval"][:2]:
                    lines.append(f"  • {e(a)}")

        lines += ["", "<i>🤖 Không có auto-remediation.</i>"]
        return {"report_markdown": "\n".join(lines), "status": "report_ready"}

    def send_to_teams(state: AgentState) -> dict:
        success = teams_reporter.send(state["report_markdown"], batch_id=state["batch_id"])
        return {"report_sent": success, "status": "done"}

    def propose_lesson(state: AgentState) -> dict:
        """
        After a successful RCA, ask LLM to extract a reusable knowledge entry
        and send a Telegram message with a 1-click save link.
        Only fires for HIGH/MEDIUM confidence investigated alerts.
        """
        import os
        from langchain_core.messages import SystemMessage, HumanMessage
        from reporters.telegram_reporter import escape_html as e
        from utils.auto_learn import store_pending

        confidence = str(state.get("confidence", ""))
        confidence_key = confidence.split(".")[-1].lower()
        root_cause = state.get("root_cause", "")
        steps = state.get("investigation_steps", [])

        # Only learn from investigations with meaningful confidence
        if not root_cause or not steps:
            return {}
        if confidence_key not in ("high", "medium"):
            return {}

        alert_name = state["alerts"][0].alert_name if state["alerts"] else "unknown"

        try:
            system = (
                "Bạn là SRE assistant. Từ kết quả RCA bên dưới, hãy tạo một Knowledge Base entry "
                "ngắn gọn bằng tiếng Việt để tham khảo cho lần sau.\n\n"
                "Format markdown với đúng các section này:\n"
                "## Triệu chứng\n"
                "## Nguyên nhân thường gặp\n"
                "## Các lệnh điều tra\n"
                "## Giải pháp khuyến nghị\n\n"
                "Viết đầy đủ, rõ ràng, không cắt ngang nội dung. Ưu tiên bullet dễ đọc; "
                "chỉ dùng thông tin có trong RCA."
            )
            fix = state.get("recommended_fix", {})
            human = (
                f"Alert: {alert_name}\n"
                f"Root cause: {root_cause}\n"
                f"Evidence: {'; '.join(state.get('evidence', [])[:3])}\n"
                f"Immediate fix: {fix.get('immediate', [])}\n"
                f"Long-term fix: {fix.get('long_term', [])}"
            )

            resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
            lesson = f"# {alert_name} — Bài học RCA\n\n{resp.content.strip()}"

            token = store_pending(lesson, alert_name)
            base_url = os.environ.get("AGENT_BASE_URL", "").rstrip("/")

            if base_url:
                save_url = f"{base_url}/save-knowledge?token={token}"
                tg_msg = (
                    f"💡 <b>Bài học mới từ RCA</b>\n"
                    f"Alert: <code>{e(alert_name)}</code>\n\n"
                    f"{e(lesson)}\n\n"
                    f"👉 <a href='{save_url}'>Lưu vào Knowledge Base</a>\n"
                    f"<i>Link hết hạn sau 48h. Chỉ admin mới có thể xác nhận.</i>"
                )
            else:
                tg_msg = (
                    f"💡 <b>Bài học mới từ RCA</b>\n"
                    f"Alert: <code>{e(alert_name)}</code>\n\n"
                    f"{e(lesson)}\n\n"
                    f"ℹ️ <i>Đặt env AGENT_BASE_URL để bật lưu 1-click.</i>"
                )

            lesson_batch_id = f"{state.get('batch_id', '')}:lesson" if state.get("batch_id") else ""
            teams_reporter.send(tg_msg, batch_id=lesson_batch_id)
        except Exception as exc:
            print(f"[propose_lesson] failed: {exc}", flush=True)

        return {}

    def correlate(state: AgentState) -> dict:
        """
        Phan tich tuong quan su kien:
        - Batch hien tai (co the 1 hoac nhieu server)
        - Active alerts tu Alertmanager (cac su kien lien quan dang xay ra)
        Gui Telegram neu phat hien pattern/tuong quan.
        Chi chay khi config.monitoring.correlation_enabled = true.
        """
        from config import config as _cfg
        from reporters.telegram_reporter import escape_html as e
        from langchain_core.messages import SystemMessage, HumanMessage
        from utils.monitoring_client import query_alertmanager_active, format_alertmanager_summary

        if not _cfg.monitoring.correlation_enabled:
            return {}

        unique_instances = {a.instance for a in state["alerts"] if a.instance}

        try:
            # Lay tat ca active alert tu Alertmanager
            try:
                active_alerts = query_alertmanager_active()
                alert_ctx = format_alertmanager_summary(active_alerts)
            except Exception:
                active_alerts = []
                alert_ctx = "Khong lay duoc du lieu tu Alertmanager."

            # Instance khac ngoai batch hien tai
            alertmanager_instances = {
                a.get("instance", "") for a in active_alerts if a.get("instance")
            }
            external_instances = alertmanager_instances - unique_instances

            # Can co it nhat 1 trong 2 dieu kien:
            # (a) >= 2 servers trong cung batch
            # (b) batch hien tai + co them active alerts tu servers khac tren Alertmanager
            has_multi_batch = len(unique_instances) >= 2
            has_external_alerts = len(external_instances) > 0
            if not has_multi_batch and not has_external_alerts:
                return {}

            # Tom tat investigation trong batch hien tai
            batch_summary = []
            for step in state.get("investigation_steps", [])[:10]:
                host = step.get("host", "?")
                cmd = step.get("command", "")
                out = (step.get("stdout", "") or "")[:300]
                batch_summary.append(f"[{host}] $ {cmd}\n{out}")
            inv_steps = "\n\n".join(batch_summary) if batch_summary else "Khong co ket qua SSH."

            # Mo ta batch alerts
            batch_alert_lines = []
            for a in state["alerts"]:
                name = getattr(a, "alert_name", "?")
                inst = getattr(a, "instance", "?")
                sev = getattr(a, "severity", "?")
                batch_alert_lines.append(f"  - [{sev}] {name} @ {inst}")
            batch_alert_str = "\n".join(batch_alert_lines) if batch_alert_lines else "(khong ro)"

            correlation_scope = "multi-server batch" if has_multi_batch else "single-server + external alerts"

            system = (
                "Bạn là SRE expert phân tích tương quan sự kiện infrastructure.\n"
                "Dữ liệu gồm: (1) batch alert đang xử lý, (2) kết quả SSH/metrics, "
                "(3) active alerts toàn hệ thống từ Alertmanager.\n\n"
                "Hãy trả lời bằng tiếng Việt có dấu, rõ ràng, không dùng Markdown link, "
                "không tự chèn URL từ IP/server, không viết quá lan man.\n\n"
                "Bố cục bắt buộc:\n"
                "1. Kết luận tương quan: HIGH/MEDIUM/LOW và lý do ngắn\n"
                "2. Mẫu chung quan sát được: subnet, thời điểm, service, dependency, cascade nếu có\n"
                "3. RCA khả dĩ: nguyên nhân gốc hoặc vì sao nghi false positive/stale data\n"
                "4. Bằng chứng chính: liệt kê các điểm quan trọng từ SSH/metrics/Alertmanager\n"
                "5. Hành động đề xuất: 2-4 bước tiếp theo\n\n"
                "Nếu dữ liệu thiếu, nói rõ thiếu dữ liệu nào. Ưu tiên tính đúng hơn kết luận quá chắc."
            )
            human = (
                f"=== Batch alerts ({len(state['alerts'])} alerts, {len(unique_instances)} servers) [{correlation_scope}] ===\n"
                f"Servers trong batch: {', '.join(sorted(unique_instances)) or 'N/A'}\n"
                f"Alert details:\n{batch_alert_str}\n"
                f"Root cause: {state.get('root_cause', 'N/A')}\n"
                f"Confidence: {state.get('confidence', 'N/A')}\n\n"
                f"=== SSH Investigation results ===\n{inv_steps}\n\n"
                f"=== Tat ca active alerts (Alertmanager) ===\n{alert_ctx}"
            )

            resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=human)])
            analysis = resp.content.strip()

            # Chi gui Telegram neu LLM phat hien correlation
            if len(analysis) > 50:
                servers_str = e(", ".join(sorted(unique_instances)))
                batch_short = e(state["batch_id"][:12])

                # Mo ta scope
                if has_multi_batch and has_external_alerts:
                    scope_label = f"{len(unique_instances)} servers trong batch + {len(external_instances)} servers khac dang co alert"
                elif has_multi_batch:
                    scope_label = f"{len(unique_instances)} servers trong cung batch"
                else:
                    scope_label = f"1 server trong batch + {len(external_instances)} servers khac dang co alert"

                tg_msg = (
                    "🔗 <b>PHÂN TÍCH TƯƠNG QUAN SỰ KIỆN</b>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    f"🧩 <b>Batch:</b> <code>{batch_short}</code>\n"
                    f"📌 <b>Phạm vi:</b> {e(scope_label)}\n"
                    f"🖥️ <b>Servers:</b> <code>{servers_str}</code>\n"
                    "━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"{e(analysis)}\n\n"
                    "━━━━━━━━━━━━━━━━━━━━\n"
                    "<i>Agent RCA Monitoring · Báo cáo tự động, chưa auto-remediation</i>"
                )
                teams_reporter.send(tg_msg)
                print(f"[correlate] Sent ({correlation_scope}): {len(unique_instances)} batch + {len(external_instances)} external instances.", flush=True)

        except Exception as exc:
            print(f"[correlate] failed: {exc}", flush=True)

        return {}

    # ------------------------------------------------------------------ routing

    def route_after_relevance(state: AgentState) -> str:
        if state.get("relevance") in (Relevance.LOW, "low"):
            return "generate_report"
        return "investigate"

    # ------------------------------------------------------------------ graph

    builder = StateGraph(AgentState)
    builder.add_node("analyze_alerts", analyze_alerts)
    builder.add_node("evaluate_relevance", evaluate_relevance)
    builder.add_node("investigate", investigate)
    builder.add_node("analyze_root_cause", analyze_root_cause)
    builder.add_node("recommend_fix", recommend_fix)
    builder.add_node("generate_report", generate_report)
    builder.add_node("send_to_teams", send_to_teams)
    builder.add_node("propose_lesson", propose_lesson)
    builder.add_node("correlate", correlate)

    builder.add_edge(START, "analyze_alerts")
    builder.add_edge("analyze_alerts", "evaluate_relevance")
    builder.add_conditional_edges("evaluate_relevance", route_after_relevance,
                                  {"investigate": "investigate", "generate_report": "generate_report"})
    builder.add_edge("investigate", "analyze_root_cause")
    builder.add_edge("analyze_root_cause", "recommend_fix")
    builder.add_edge("recommend_fix", "generate_report")
    builder.add_edge("generate_report", "send_to_teams")
    builder.add_edge("send_to_teams", "propose_lesson")
    builder.add_edge("propose_lesson", "correlate")
    builder.add_edge("correlate", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Runner helper
# ---------------------------------------------------------------------------

def _enum_val(v) -> str:
    """Normalize an enum value to its string key.

    Handles:
    - Enum instance -> 'low'
    - 'Confidence.LOW' style string -> 'low'
    - Already plain 'low' -> 'low'
    """
    if hasattr(v, "value"):
        return v.value
    s = str(v)
    return s.split(".")[-1].lower() if "." in s else s.lower()


def run_agent(batch: AlertBatch, graph: Any) -> BatchReport:
    """Run the graph for a batch and return a BatchReport."""
    initial_state: AgentState = {
        "batch_id": batch.batch_id,
        "alerts": batch.alerts,
        "alert_summaries": [],
        "relevance": Relevance.MEDIUM,
        "impact": Impact.MINOR,
        "relevance_reason": "",
        "investigation_steps": [],
        "metrics_trends": [],
        "evidence": [],
        "root_cause": "",
        "confidence": Confidence.LOW,
        "recommended_fix": {},
        "report_markdown": "",
        "report_sent": False,
        "status": "pending",
        "error": None,
        "messages": [],
    }

    try:
        final_state = graph.invoke(initial_state)
    except Exception as exc:  # noqa: BLE001
        return BatchReport(
            batch_id=batch.batch_id,
            status=InvestigationStatus.FAILED,
            alerts=[a.model_dump(mode="json") for a in batch.alerts],
            error=str(exc),
        )

    fix = final_state.get("recommended_fix", {})
    return BatchReport(
        batch_id=final_state["batch_id"],
        status=InvestigationStatus.INVESTIGATED,
        alerts=[a.model_dump(mode="json") for a in batch.alerts],
        summary=final_state.get("relevance_reason", ""),
        relevance=Relevance(_enum_val(final_state.get("relevance", Relevance.MEDIUM))),
        impact=Impact(_enum_val(final_state.get("impact", Impact.MINOR))),
        relevance_reason=final_state.get("relevance_reason", ""),
        investigation_steps=final_state.get("investigation_steps", []),
        evidence=final_state.get("evidence", []),
        root_cause=final_state.get("root_cause", ""),
        confidence=Confidence(_enum_val(final_state.get("confidence", Confidence.LOW))),
        recommended_fix=RecommendedFix(**fix) if fix else RecommendedFix(),
        teams_report_sent=final_state.get("report_sent", False),
    )
