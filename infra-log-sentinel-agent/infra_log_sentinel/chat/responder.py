from __future__ import annotations

from collections import Counter
from datetime import datetime
import re

from infra_log_sentinel.analysis.time_window import (
    extract_time_range_from_text,
    filter_events_by_lookback,
    filter_events_by_time_range,
    format_time_range_label,
)
from infra_log_sentinel.chat.actions import try_execute_chat_action
from infra_log_sentinel.chat.conversation import ConversationSnapshot, ConversationStore
from infra_log_sentinel.chat.intent import (
    INTENT_ASSISTANT_FEEDBACK,
    INTENT_GENERAL_QUESTION,
    classify_chat_intent,
    normalize_text,
)
from infra_log_sentinel.chat.llm_assistant import (
    adjudicate_rca_with_llm,
    answer_with_llm,
    suggest_rca_next_steps_with_llm,
)
from infra_log_sentinel.chat.log_chat import answer_log_question, should_answer_with_rules_first
from infra_log_sentinel.config import Settings
from infra_log_sentinel.ingestion.local_folder import iter_log_lines
from infra_log_sentinel.models import LogEvent, RawLogLine
from infra_log_sentinel.notifications.telegram_sender import send_telegram_message
from infra_log_sentinel.parsing.log_parser import parse_raw_lines
from infra_log_sentinel.rca import (
    RcaIncidentStore,
    analyze_incident,
    format_rca_report,
    format_rca_telegram,
    generate_incident,
    list_scenarios,
)
from infra_log_sentinel.rca.log_analyzer import analyze_log_events, apply_llm_review
from infra_log_sentinel.simulator.log_generator import (
    INCIDENT_SCENARIOS,
    generate_incident_log_lines,
)


SEVERITY_ORDER = ("critical", "error", "warning", "info")
DOMAIN_ORDER = ("network", "linux", "windows", "vmware")


def answer_or_execute_chat(
    settings: Settings,
    question: str,
    dry_run: bool = False,
    channel: str = "default",
) -> str:
    conversation_channel = channel.strip() if channel.strip() else "default"
    conversation_store = ConversationStore(settings.state_db_path)
    context = conversation_store.get(conversation_channel)
    raw_lines = list(iter_log_lines(settings.log_root_path))
    events = parse_raw_lines(raw_lines)
    intent = classify_chat_intent(question)

    if _is_context_reset_request(question):
        conversation_store.clear(conversation_channel)
        return _remember_and_return(
            conversation_store=conversation_store,
            channel=conversation_channel,
            question=question,
            answer="Đã mở ngữ cảnh hội thoại mới. Các câu tiếp theo sẽ không bám theo RCA/report trước đó.",
            intent="context_reset",
            action="context_reset",
        )

    if _should_start_new_investigation(question, context):
        conversation_store.clear(conversation_channel)
        context = conversation_store.get(conversation_channel)

    if intent.kind == INTENT_ASSISTANT_FEEDBACK:
        return _remember_and_return(
            conversation_store=conversation_store,
            channel=conversation_channel,
            question=question,
            answer=_answer_assistant_feedback(),
            intent=intent.kind,
        )

    rca_command_answer = _answer_rca_command_if_requested(
        events=events,
        question=question,
        alert_levels=settings.severity_alert_levels,
    )
    if rca_command_answer:
        return _remember_and_return(
            conversation_store=conversation_store,
            channel=conversation_channel,
            question=question,
            answer=rca_command_answer,
            intent=intent.kind,
            action="rca_command",
        )

    rca_answer = _answer_rca_if_requested(
        settings=settings,
        events=events,
        question=question,
        dry_run=dry_run,
    )
    if rca_answer:
        return _remember_and_return(
            conversation_store=conversation_store,
            channel=conversation_channel,
            question=question,
            answer=rca_answer,
            intent="rca",
            action="rca",
        )

    command_explanation = _answer_command_explanation_if_requested(question)
    if command_explanation:
        return _remember_and_return(
            conversation_store=conversation_store,
            channel=conversation_channel,
            question=question,
            answer=command_explanation,
            intent=intent.kind,
            action="command_explanation",
        )

    inline_report = _answer_inline_report_if_requested(
        settings=settings,
        events=events,
        question=question,
        context=context,
    )
    if inline_report:
        return _remember_and_return(
            conversation_store=conversation_store,
            channel=conversation_channel,
            question=question,
            answer=inline_report,
            intent=intent.kind if intent.kind else INTENT_GENERAL_QUESTION,
            action="inline_report",
            artifact_path=context.last_artifact_path,
        )

    if intent.action_candidate:
        action_result = try_execute_chat_action(
            settings=settings,
            events=events,
            question=question,
            dry_run=dry_run,
        )
        if action_result.handled:
            action = _infer_action_name(question, action_result.message)
            return _remember_and_return(
                conversation_store=conversation_store,
                channel=conversation_channel,
                question=question,
                answer=action_result.message,
                intent=intent.kind,
                action=action,
                artifact_path=_extract_artifact_path(action_result.message),
            )

    if intent.rules_first or should_answer_with_rules_first(question):
        return _remember_and_return(
            conversation_store=conversation_store,
            channel=conversation_channel,
            question=question,
            answer=answer_log_question(events, question, settings.severity_alert_levels),
            intent=intent.kind,
        )

    llm_answer = answer_with_llm(settings, events, question, settings.severity_alert_levels)
    if llm_answer:
        return _remember_and_return(
            conversation_store=conversation_store,
            channel=conversation_channel,
            question=question,
            answer=llm_answer,
            intent=intent.kind,
        )

    return _remember_and_return(
        conversation_store=conversation_store,
        channel=conversation_channel,
        question=question,
        answer=_answer_general_fallback(),
        intent=intent.kind,
    )


def _answer_rca_if_requested(
    settings: Settings,
    events: list[LogEvent],
    question: str,
    dry_run: bool,
) -> str:
    q = normalize_text(question)
    if not _looks_like_rca_request(q):
        return ""

    store = RcaIncidentStore(settings.state_db_path)
    if _looks_like_synthetic_rca_request(q):
        incident = generate_incident(_extract_rca_scenario(q))
        analysis = analyze_incident(incident)
        store.save(incident, analysis)
        report = format_rca_report(analysis)
        report += "\n\nMode: synthetic JSON RCA lab."
    else:
        generated_count = 0
        generated = []
        selected_scenario = _extract_rca_scenario(q)
        time_scope = _extract_rca_time_scope(question, q, settings.report_lookback_hours, settings.app_timezone)
        lookback_hours = time_scope["lookback_hours"]
        focus_text = _rca_focus_text(question)
        if _looks_like_generate_log_rca_request(q):
            generated = generate_incident_log_lines(
                settings.log_root_path,
                scenario=selected_scenario,
            )
            generated_count = len(generated)
            recent_events = _events_from_generated_log_lines(generated)
            window_label = f"generated {selected_scenario} incident burst"
        elif time_scope["start_time"] and time_scope["end_time"]:
            recent_events = filter_events_by_time_range(
                events,
                start_time=time_scope["start_time"],
                end_time=time_scope["end_time"],
            )
            window_label = time_scope["label"]
        else:
            recent_events = filter_events_by_lookback(events, lookback_hours)
            window_label = time_scope["label"]
        analysis = analyze_log_events(
            recent_events,
            lookback_hours=lookback_hours,
            alert_levels=settings.severity_alert_levels,
            focus_text=focus_text,
            window_label=window_label,
        )
        _adjudicate_rca_answer_with_llm(settings, question, analysis)
        if _rca_needs_guidance(analysis):
            _attach_rca_guidance(
                settings=settings,
                events=recent_events,
                question=question,
                analysis=analysis,
            )
        incident = {
            "incident_id": analysis["incident_id"],
            "source": "log_generator" if generated_count else "current_logs",
            "scenario": selected_scenario if generated_count else "",
            "generated_count": generated_count,
            "lookback_hours": lookback_hours,
            "window_label": window_label,
            "focus_text": focus_text,
        }
        store.save(incident, analysis)
        report = format_rca_report(analysis)
        if generated_count:
            report += (
                f"\n\nMode: RCA from generated incident burst. "
                f"Scenario: `{selected_scenario}`. Generated logs: `{generated_count}`."
            )
        else:
            report += f"\n\nMode: RCA from current parsed logs. Scope: `{window_label}`."

    if _rca_should_send_telegram(q):
        if dry_run:
            report += "\n\nTelegram: dry-run, RCA message was not sent."
        else:
            message_id = send_telegram_message(
                settings=settings,
                text=format_rca_telegram(analysis),
                parse_mode="HTML",
            )
            report += f"\n\nTelegram: RCA message sent with message_id `{message_id}`."
    report += "\n\nTip: dùng `sinh log su co <scenario> roi phan tich RCA` khi cần demo một incident mới."
    return report


def _adjudicate_rca_answer_with_llm(settings: Settings, question: str, analysis: dict[str, object]) -> None:
    review = adjudicate_rca_with_llm(
        settings=settings,
        question=question,
        analysis=analysis,
    )
    if review:
        apply_llm_review(analysis, review)


def _events_from_generated_log_lines(generated: list[object]) -> list[LogEvent]:
    raw_lines = [
        RawLogLine(
            domain=str(item.domain),
            source_file=item.path,
            line_number=index,
            text=str(item.text),
        )
        for index, item in enumerate(generated, start=1)
    ]
    return parse_raw_lines(raw_lines)


def _is_context_reset_request(question: str) -> bool:
    q = normalize_text(question)
    reset_terms = (
        "new chat",
        "new conversation",
        "new topic",
        "reset context",
        "clear context",
        "clear chat",
        "xoa context",
        "xoa ngu canh",
        "cuoc hoi thoai moi",
        "hoi thoai moi",
        "chu de moi",
        "bat dau lai",
    )
    return any(term in q for term in reset_terms)


def _should_start_new_investigation(question: str, context: ConversationSnapshot) -> bool:
    if not context.last_user_message:
        return False
    q = normalize_text(question)
    current_is_investigation = _looks_like_rca_request(q) or should_answer_with_rules_first(question)
    previous_was_investigation = context.last_action in {"rca", "inline_report"} or context.last_intent == "log_question"
    if not current_is_investigation or not previous_was_investigation:
        return False
    current = _topic_signature(q)
    previous = _topic_signature(context.last_user_message)
    if "khac" in q or "moi" in q:
        return bool(current)
    return bool(current and previous and current.isdisjoint(previous))


def _topic_signature(value: str) -> set[str]:
    q = normalize_text(value)
    markers = {
        "fortigate",
        "juniper",
        "aruba",
        "linux",
        "windows",
        "vmware",
        "checkmk",
        "cacti",
        "prometheus",
        "grafana",
        "elk",
        "wazuh",
        "syslog",
        "sqlagent",
        "sqlserveragent",
        "bgp",
        "ospf",
        "dns",
        "ssh",
        "brute",
        "disk",
        "datastore",
        "vpn",
        "wifi",
        "wireless",
        "malware",
        "service",
        "app",
        "api",
        "database",
    }
    signature = {marker for marker in markers if marker in q}
    signature.update(re.findall(r"\b[a-z0-9-]+(?:\.example\.local|\.local)\b", q))
    for scenario in list(INCIDENT_SCENARIOS) + list(list_scenarios()):
        normalized = normalize_text(scenario.replace("_", " "))
        if normalized and normalized in q:
            signature.add(normalized)
    return signature


def _rca_needs_guidance(analysis: dict[str, object]) -> bool:
    confidence = int(analysis.get("confidence") or 0)
    return analysis.get("status") == "insufficient_data" or confidence < 70


def _attach_rca_guidance(
    settings: Settings,
    events: list[LogEvent],
    question: str,
    analysis: dict[str, object],
) -> None:
    guidance = suggest_rca_next_steps_with_llm(
        settings=settings,
        events=events,
        question=question,
        analysis=analysis,
        alert_levels=settings.severity_alert_levels,
    )
    analysis["llm_guidance"] = guidance or _fallback_rca_guidance(analysis)


def _rca_investigation_guidance(
    settings: Settings,
    events: list[LogEvent],
    question: str,
    analysis: dict[str, object],
) -> str:
    guidance = suggest_rca_next_steps_with_llm(
        settings=settings,
        events=events,
        question=question,
        analysis=analysis,
        alert_levels=settings.severity_alert_levels,
    )
    if guidance:
        return "\n\n" + guidance
    missing = analysis.get("missing_data") or []
    missing_lines = "\n".join(f"- {item}" for item in list(missing)[:4])
    if not missing_lines:
        missing_lines = "- Timestamp-aligned application, OS, network, and dependency logs around the impact window."
    return (
        "\n\n## RCA chưa đủ dữ liệu"
        "\n- Kết luận: log hiện tại chưa đủ bằng chứng để xác nhận nguyên nhân gốc."
        "\n- Cần kiểm tra tiếp: mở rộng time window, đối chiếu log ứng dụng/hệ điều hành/network cùng timestamp, và xác nhận impact thực tế từ service owner."
        "\n- Dữ liệu còn thiếu:\n"
        f"{missing_lines}"
        "\n- Next action: cung cấp thêm impact cụ thể hoặc tăng window RCA rồi chạy lại phân tích."
    )


def _fallback_rca_guidance(analysis: dict[str, object]) -> str:
    missing = analysis.get("missing_data") or []
    missing_lines = "\n".join(f"- {item}" for item in list(missing)[:4])
    if not missing_lines:
        missing_lines = "- Timestamp-aligned application, OS, network, and dependency logs around the impact window."
    return (
        "## LLM guidance: RCA chưa đủ dữ liệu"
        "\n- Kết luận: log hiện tại chưa đủ bằng chứng để xác nhận nguyên nhân gốc."
        "\n- Vì sao chưa đủ: chưa có chuỗi event, timestamp, dependency hoặc change record đủ chặt để kết luận."
        "\n- Dữ liệu cần bổ sung:\n"
        f"{missing_lines}"
        "\n- Bước tiếp theo an toàn: mở rộng time window, đối chiếu log/metrics theo cùng timestamp, xác nhận impact với service owner rồi chạy lại RCA."
    )


def _answer_rca_command_if_requested(
    events: list[LogEvent],
    question: str,
    alert_levels: tuple[str, ...],
) -> str:
    q = normalize_text(question)
    if not _looks_like_rca_command_request(q):
        return ""
    answer = answer_log_question(events, question, alert_levels)
    if answer.startswith("AIOps RCA Investigation"):
        return ""
    return (
        "Mình hiểu câu này là yêu cầu command/check trong ngữ cảnh RCA, "
        "không phải yêu cầu chạy lại full RCA investigation.\n\n"
        f"{answer}"
    )


def _looks_like_rca_command_request(q: str) -> bool:
    if not _looks_like_rca_request(q):
        return False
    if any(term in q for term in ("command", "lenh", "runbook")):
        return True
    check_terms = ("check", "kiem tra", "verify", "investigate", "troubleshoot")
    technical_terms = (
        "broadcast",
        "loop",
        "mac",
        "flapping",
        "ssh",
        "brute",
        "wazuh",
        "dns",
        "named",
        "fortigate",
        "firewall",
        "session",
        "sqlagent",
        "service",
        "disk",
        "linux",
        "windows",
        "vmware",
        "routing",
        "route",
        "datastore",
        "snapshot",
        "interface",
    )
    return any(term in q for term in check_terms) and any(term in q for term in technical_terms)


def _looks_like_rca_request(q: str) -> bool:
    return any(
        term in q
        for term in (
            "rca",
            "root cause",
            "nguyen nhan goc",
            "phan tich su co",
            "su co",
            "incident",
            "outage",
            "mat ket noi",
            "khong truy cap",
            "khong vao duoc",
            "internet cham",
            "mang cham",
            "app loi",
            "service down",
            "impact",
            "anh huong",
            "synthetic incident",
            "demo incident",
            "incident gia lap",
            "tao incident",
        )
    )


def _extract_rca_scenario(q: str) -> str:
    aliases = {
        "broadcast": "broadcast_loop",
        "loop": "broadcast_loop",
        "mac": "mac_flapping",
        "fortigate": "fortigate_session_spike",
        "firewall": "fortigate_session_spike",
        "dns": "dns_timeout",
        "disk": "linux_disk_full",
        "linux": "linux_disk_full",
        "windows": "windows_service_crash",
        "service": "windows_service_crash",
        "vmware": "vmware_datastore_full",
        "datastore": "vmware_datastore_full",
        "interface": "interface_flapping",
        "routing": "routing_issue",
        "route": "routing_issue",
        "brute": "brute_force_wazuh",
        "wazuh": "brute_force_wazuh",
        "ssh": "brute_force_wazuh",
    }
    for scenario in list_scenarios():
        if scenario in q or scenario.replace("_", " ") in q:
            return scenario
    for term, scenario in aliases.items():
        if term in q:
            return scenario
    return "broadcast_loop"


def _looks_like_synthetic_rca_request(q: str) -> bool:
    return any(term in q for term in ("synthetic json", "json incident", "incident json", "lab json"))


def _looks_like_generate_log_rca_request(q: str) -> bool:
    return (
        any(term in q for term in ("sinh log", "tao log", "generate log", "append log", "log generator"))
        and _looks_like_rca_request(q)
    )


def _extract_rca_lookback_hours(q: str, default_hours: int) -> float:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(phut|minute|minutes|min|m)\b", q)
    if match:
        return max(float(match.group(1).replace(",", ".")) / 60, 1 / 60)
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*(gio|hour|hours|h)\b", q)
    if match:
        return max(float(match.group(1).replace(",", ".")), 1 / 60)
    if "hom nay" in q or "today" in q:
        return 24
    if "gan day" in q or "recent" in q:
        return min(default_hours, 6)
    return float(default_hours)


def _extract_rca_time_scope(
    question: str,
    normalized_question: str,
    default_hours: int,
    timezone_name: str,
) -> dict[str, object]:
    time_range = extract_time_range_from_text(question, timezone_name=timezone_name)
    if time_range:
        start_time, end_time = time_range
        lookback_hours = max((end_time - start_time).total_seconds() / 3600, 1 / 60)
        return {
            "start_time": start_time,
            "end_time": end_time,
            "lookback_hours": lookback_hours,
            "label": format_time_range_label(start_time, end_time),
        }
    lookback_hours = _extract_rca_lookback_hours(normalized_question, default_hours)
    return {
        "start_time": None,
        "end_time": None,
        "lookback_hours": lookback_hours,
        "label": f"last {lookback_hours:g}h",
    }


def _rca_focus_text(question: str) -> str:
    cleaned = question.strip()
    cleaned = re.sub(r"(?i)\b(rca|root cause|phan tich|chan doan|diagnose|check|kiem tra)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:240]


def _rca_should_send_telegram(q: str) -> bool:
    return "telegram" in q and any(term in q for term in ("send", "gui", "push"))


def _answer_inline_report_if_requested(
    settings: Settings,
    events: list[LogEvent],
    question: str,
    context: ConversationSnapshot,
) -> str:
    if not _looks_like_inline_report_request(question):
        return ""
    return _inline_chat_report(settings, events, context)


def _answer_command_explanation_if_requested(question: str) -> str:
    q = normalize_text(question)
    if not _looks_like_command_explanation_request(q):
        return ""

    command = _extract_command_from_question(question)
    if not command:
        return ""
    return _explain_command(command)


def _looks_like_command_explanation_request(q: str) -> bool:
    explanation_terms = (
        "khong hieu lenh",
        "khong hieu command",
        "lenh nay dung de lam gi",
        "command nay dung de lam gi",
        "dung de lam gi",
        "giai thich y nghia",
        "giai thich lenh",
        "giai thich command",
        "y nghia cua",
        "what does",
        "explain command",
        "explain this command",
        "meaning of",
    )
    if not any(term in q for term in explanation_terms):
        return False
    return _extract_command_from_question(q) != "" or _extract_command_from_question(q.replace('"', "")) != ""


def _extract_command_from_question(question: str) -> str:
    for pattern in (r"`([^`]+)`", r'"([^"]+)"', r"'([^']+)'"):
        match = re.search(pattern, question)
        if match:
            candidate = match.group(1).strip()
            if _looks_like_shell_command(candidate):
                return candidate

    command_names = (
        "Get-Service",
        "Restart-Service",
        "Start-Service",
        "Stop-Service",
        "Get-WinEvent",
        "Get-EventLog",
        "Get-Process",
        "Get-Content",
        "Select-String",
        "Where-Object",
        "Test-NetConnection",
        "systemctl",
        "journalctl",
        "grep",
        "tail",
    )
    command_pattern = r"(?i)\b(" + "|".join(re.escape(name) for name in command_names) + r")\b[^\n`\"']*"
    match = re.search(command_pattern, question)
    if not match:
        return ""

    command = match.group(0).strip()
    command = re.sub(r"[.?!,;:]+$", "", command).strip()
    return command if _looks_like_shell_command(command) else ""


def _looks_like_shell_command(value: str) -> bool:
    normalized = value.strip().lower()
    return bool(
        re.match(
            r"^(get|restart|start|stop|set|new|remove|test)-[a-z0-9-]+\b",
            normalized,
        )
        or normalized.startswith(("systemctl ", "journalctl ", "grep ", "tail "))
    )


def _explain_command(command: str) -> str:
    command = command.strip()
    cmdlet = command.split()[0] if command.split() else command
    normalized_cmdlet = cmdlet.lower()
    args = command.split()[1:]
    target = " ".join(args).strip()

    intro = [
        "Mình hiểu câu này là yêu cầu giải thích command, không phải yêu cầu sinh thêm runbook.",
        "",
        f"Command: `{command}`",
        "",
    ]

    if normalized_cmdlet == "get-service":
        target_text = target or "<service-name>"
        lines = intro + [
            "Ý nghĩa:",
            "- `Get-Service` là PowerShell cmdlet dùng để xem thông tin Windows Service.",
            f"- `{target_text}` là tên service muốn kiểm tra.",
            "- Kết quả thường cho biết service đang `Running`, `Stopped`, hoặc không tồn tại.",
            "",
            "Dùng khi nào:",
            "- Kiểm tra nhanh service có đang chạy không trước khi điều tra hoặc restart.",
            "- Với SQL Server Agent, tên service thực tế có thể là `SQLSERVERAGENT` hoặc `SQLAgent$<instance>` tùy cách cài đặt.",
            "",
            "Cách kiểm tra rộng hơn nếu tên service chưa chắc:",
            "`Get-Service *SQL*Agent*`",
        ]
        return "\n".join(lines)

    if normalized_cmdlet == "restart-service":
        target_text = target or "<service-name>"
        return "\n".join(
            intro
            + [
                "Ý nghĩa:",
                "- `Restart-Service` dừng rồi khởi động lại một Windows Service.",
                f"- `{target_text}` là service bị restart.",
                "",
                "Lưu ý vận hành:",
                "- Đây là lệnh có tác động thật, có thể làm gián đoạn dịch vụ.",
                "- Chỉ chạy sau khi xác nhận dependency, change window và ảnh hưởng ứng dụng.",
            ]
        )

    if normalized_cmdlet == "get-winevent":
        return "\n".join(
            intro
            + [
                "Ý nghĩa:",
                "- `Get-WinEvent` đọc Windows Event Log.",
                "- `-FilterHashtable` lọc log theo điều kiện như log name, event id, thời gian.",
                "- Ví dụ `Id=7031` thường dùng để tìm sự kiện service bị crash/terminated.",
                "",
                "Dùng khi nào:",
                "- Điều tra service failure gần đây thay vì xem toàn bộ Event Viewer thủ công.",
            ]
        )

    if normalized_cmdlet == "get-eventlog":
        return "\n".join(
            intro
            + [
                "Ý nghĩa:",
                "- `Get-EventLog` đọc Windows Event Log kiểu cũ.",
                "- `-LogName Application` chọn log Application.",
                "- `-Newest 50` lấy 50 event mới nhất.",
                "- Nếu có `Where-Object`, phần sau dùng để lọc message theo từ khóa.",
                "",
                "Dùng khi nào:",
                "- Tìm lỗi ứng dụng liên quan tới service hoặc process cụ thể.",
            ]
        )

    return "\n".join(
        intro
        + [
            "Ý nghĩa tổng quát:",
            f"- `{cmdlet}` là command chính.",
            f"- Phần sau command (`{target}`) là tham số/đối tượng mà command thao tác." if target else "- Command này chưa có tham số cụ thể.",
            "",
            "Nếu anh muốn, hãy gửi thêm output của command đó; mình sẽ giải thích từng cột/kết quả cụ thể.",
        ]
    )


def _looks_like_inline_report_request(question: str) -> bool:
    q = normalize_text(question)
    if not any(term in q for term in ("report", "bao cao")):
        return False

    explicit_mail_delivery = any(term in q for term in ("gmail", "email", "mail")) and not any(
        term in q for term in ("khong gui", "dung gui", "khong can gui")
    )
    if explicit_mail_delivery:
        return False

    chat_surface_terms = (
        "giao dien chat",
        "trong chat",
        "o chat",
        "tai chat",
        "tren chat",
        "tai giao dien",
        "trong giao dien",
        "hien thi tai day",
        "hien thi o day",
        "hien thi tren chat",
        "tra loi tai day",
        "noi dung tai day",
        "inline",
        "in chat",
        "chat ui",
    )
    return any(term in q for term in chat_surface_terms)


def _inline_chat_report(
    settings: Settings,
    events: list[LogEvent],
    context: ConversationSnapshot,
) -> str:
    recent_events = filter_events_by_lookback(
        events,
        lookback_hours=settings.report_lookback_hours,
    )
    alert_levels = set(settings.severity_alert_levels)
    alert_events = _sort_events([event for event in recent_events if event.severity in alert_levels])
    priority_events = alert_events if alert_events else _sort_events(recent_events)

    if context.last_action in {"report", "email_report"}:
        lead = (
            "Đã hiểu đây là câu nối tiếp của report vừa rồi. "
            "Mình sẽ hiển thị report ngay trong chat, không tạo PDF mới và không gửi Gmail."
        )
    else:
        lead = "Đã hiểu: report sẽ hiển thị ngay trong chat, không tạo PDF và không gửi Gmail."

    lines = [
        lead,
        "",
        "INFRA-LOG-SENTINEL Chat Report",
        f"- Window: {settings.report_lookback_hours} giờ gần nhất",
        f"- Total events: {len(recent_events)}",
        f"- Severity: {_format_counts(Counter(event.severity for event in recent_events), SEVERITY_ORDER, upper=True)}",
        f"- Domain: {_format_counts(Counter(event.domain for event in recent_events), DOMAIN_ORDER)}",
    ]
    if context.last_artifact_path:
        lines.append(f"- File trước đó: {context.last_artifact_path}")

    lines.extend(["", "Top alert cần ưu tiên:"])
    if not priority_events:
        lines.append("- Không có event phù hợp trong cửa sổ report.")
    else:
        for index, event in enumerate(priority_events[:7], start=1):
            lines.append(
                f"{index}. [{event.severity.upper()}] {event.domain}/{event.source} "
                f"{event.event_type}: {event.message}"
            )

    lines.extend(
        [
            "",
            "Gợi ý tiếp theo:",
            "- Hỏi `command xử lý <domain/type>` nếu cần runbook cụ thể.",
            "- Hỏi `xuất PDF report` nếu thật sự muốn tạo file.",
            "- Hỏi `gửi report qua Gmail` nếu muốn delivery qua mail.",
        ]
    )
    return "\n".join(lines)


def _sort_events(events: list[LogEvent]) -> list[LogEvent]:
    severity_rank = {severity: index for index, severity in enumerate(SEVERITY_ORDER)}
    return sorted(
        events,
        key=lambda event: (
            severity_rank.get(event.severity, 99),
            event.domain,
            event.source,
            event.event_type,
        ),
    )


def _format_counts(counter: Counter[str], order: tuple[str, ...], upper: bool = False) -> str:
    parts = []
    for name in order:
        count = counter.get(name, 0)
        if count:
            label = name.upper() if upper else name
            parts.append(f"{label} {count}")
    for name, count in sorted(counter.items()):
        if name not in order and count:
            label = name.upper() if upper else name
            parts.append(f"{label} {count}")
    return " | ".join(parts) if parts else "none"


def _infer_action_name(question: str, answer: str) -> str:
    normalized = normalize_text(" ".join([question, answer]))
    if "runtime control" in normalized or "tam dung" in normalized or "bat lai" in normalized:
        return "runtime_control"
    if "gmail" in normalized or "email" in normalized or "mail" in normalized:
        return "email_report"
    if "csv" in normalized:
        return "export_csv"
    if "pdf" in normalized or "report" in normalized or "bao cao" in normalized:
        return "report"
    return ""


def _extract_artifact_path(answer: str) -> str:
    match = re.search(r"(?im)^-\s*File:\s*(.+?)\s*$", answer)
    return match.group(1).strip() if match else ""


def _remember_and_return(
    conversation_store: ConversationStore,
    channel: str,
    question: str,
    answer: str,
    intent: str,
    action: str = "",
    artifact_path: str = "",
) -> str:
    try:
        conversation_store.update(
            channel=channel,
            user_message=question,
            agent_message=answer,
            intent=intent,
            action=action,
            artifact_path=artifact_path,
        )
    except Exception:
        pass
    return answer


def _answer_assistant_feedback() -> str:
    return (
        "Bạn nói đúng. Đây là phản hồi về cách mình hiểu câu hỏi, không phải yêu cầu truy vấn hay xuất log.\n\n"
        "Mình sẽ xử lý theo nguyên tắc mới:\n"
        "- Chỉ liệt kê log khi bạn hỏi rõ về dữ liệu log, ví dụ `có warning nào hôm nay?`.\n"
        "- Nếu bạn đang hỏi hoặc góp ý với bot, mình trả lời trực tiếp vào ý đó.\n"
        "- Nếu câu có thể hiểu theo nhiều hướng, mình hỏi lại trước thay vì tự suy diễn.\n\n"
        "Bạn có thể hỏi lại câu muốn mình trả lời; mình sẽ không tự động xuất danh sách warning từ câu phản hồi này."
    )


def _answer_general_fallback() -> str:
    return (
        "Mình chưa đủ chắc đây là câu hỏi về log, runbook hay thao tác runtime, nên mình sẽ không tự xuất alert.\n\n"
        "Bạn có thể hỏi theo một trong ba hướng:\n"
        "- Hỏi log: `tóm tắt log hôm nay`, `có critical network nào không?`\n"
        "- Hỏi xử lý: `command xử lý vmware warning`\n"
        "- Thao tác: `xuất báo cáo PDF 24 giờ gần nhất`\n\n"
        "Nếu đây là câu hỏi hội thoại bình thường, hãy nói rõ nội dung bạn muốn mình trả lời."
    )
