from __future__ import annotations

from ast import literal_eval
from html import escape
import re

from infra_log_sentinel.chat.intent import (
    INTENT_AMBIGUOUS_OPERATIONAL_CHANGE,
    INTENT_ASSISTANT_FEEDBACK,
    INTENT_LOG_QUESTION,
    INTENT_SAFE_ACTION,
    classify_chat_intent,
)


TELEGRAM_PARSE_MODE = "HTML"
MAX_GENERIC_BODY = 2800

SEVERITY_BADGE = {
    "critical": "🔴 CRITICAL",
    "error": "🟠 ERROR",
    "warning": "🟡 WARNING",
    "info": "🔵 INFO",
}
DOMAIN_BADGE = {
    "network": "🌐 Network",
    "linux": "🐧 Linux",
    "windows": "🪟 Windows",
    "vmware": "🧱 VMware",
}
INTENT_BADGE = {
    INTENT_LOG_QUESTION: "🧭 Log Intel",
    INTENT_SAFE_ACTION: "⚙️ Action",
    INTENT_AMBIGUOUS_OPERATIONAL_CHANGE: "🛡️ Needs Clarity",
    INTENT_ASSISTANT_FEEDBACK: "💬 Conversation",
}


def format_chat_reply_for_telegram(question: str, answer: str) -> str:
    summary = _format_summary_answer(question, answer)
    if summary:
        return summary

    runbook = _format_runbook_answer(question, answer)
    if runbook:
        return runbook

    intent = classify_chat_intent(question)
    return _format_generic_answer(question, answer, intent.kind)


def format_help_for_telegram() -> str:
    return "\n".join(
        [
            "🧭 <b>INFRA-LOG-SENTINEL Console</b>",
            "<b>Ask:</b>",
            "1. <code>Tóm tắt log hôm nay</code>",
            "2. <code>Có critical network nào không?</code>",
            "3. <code>command xử lý vmware warning</code>",
            "",
            "<b>Actions:</b>",
            "1. <code>xuất báo cáo PDF 24 giờ gần nhất</code>",
            "2. <code>gửi báo cáo hôm nay qua Gmail</code>",
            "3. <code>export alert critical ra CSV</code>",
        ]
    )


def _format_summary_answer(question: str, answer: str) -> str:
    if "Theo severity:" not in answer or "Theo domain:" not in answer:
        return ""

    total = _extract_int(r"Tổng số event phù hợp:\s*(\d+)", answer)
    severities = _extract_dict("Theo severity", answer)
    domains = _extract_dict("Theo domain", answer)
    alerts = _extract_alert_lines(answer)

    lines = [
        "🧭 <b>INFRA-LOG-SENTINEL Brief</b>",
        f"<b>Question:</b> {escape(question)}",
        "<b>Mode:</b> Log summary",
    ]
    lines.extend(
        [
            "",
            "📊 <b>Overview</b>",
            f"<b>Total events:</b> <code>{total if total is not None else 0}</code>",
            f"<b>Severity:</b> {_severity_overview(severities)}",
            f"<b>Domain:</b> {_domain_overview(domains)}",
        ]
    )

    if alerts:
        lines.extend(["", "🚨 <b>Priority Findings</b>"])
        for index, alert in enumerate(alerts[:3], start=1):
            lines.extend(_format_summary_alert(alert, index))

    lines.extend(
        [
            "",
            "🛠 <b>Suggested Next Step</b>",
            "Ask <code>command xử lý &lt;domain/type&gt;</code> for exact runbook commands.",
        ]
    )
    return "\n".join(lines)


def _format_runbook_answer(question: str, answer: str) -> str:
    if "Runbook command" not in answer and "command" not in question.lower():
        return ""

    issues = _parse_runbook_issues(answer)
    if not issues:
        return _format_generic_answer(question, answer, INTENT_LOG_QUESTION)

    lines = [
        "🛠 <b>INFRA-LOG-SENTINEL Runbook</b>",
        f"<b>Question:</b> {escape(question)}",
    ]

    for index, issue in enumerate(issues[:2], start=1):
        lines.extend(
            [
                "",
                f"🚨 <b>Finding {index}</b>",
                f"<b>Severity:</b> {_severity_badge(str(issue['severity']))}",
                f"<b>Source:</b> <code>{escape(str(issue['source']))}</code>",
                f"<b>Type:</b> <code>{escape(str(issue['event_type']))}</code>",
                "",
                f"📌 <b>Summary</b>\n{escape(_trim(str(issue['log']), 260))}",
                f"🛠 <b>Solution</b>\n{escape(_trim(str(issue['action']), 260))}",
            ]
        )
        commands = issue["commands"]
        if isinstance(commands, list) and commands:
            lines.extend(["", "🔎 <b>Commands to run</b>"])
            for command_index, (phase, command) in enumerate(commands[:4], start=1):
                lines.append(
                    f"{command_index}. <b>{escape(str(phase))}</b>: "
                    f"<code>{escape(str(command))}</code>"
                )

    lines.extend(
        [
            "",
            "✅ <b>Operator note</b>",
            "Verify first, remediate only after the finding is confirmed.",
        ]
    )
    return "\n".join(lines)


def _format_generic_answer(question: str, answer: str, intent_kind: str) -> str:
    badge = INTENT_BADGE.get(intent_kind, "💬 Assistant")
    lines = [
        f"{badge} <b>INFRA-LOG-SENTINEL</b>",
        f"<b>Question:</b> {escape(question)}",
    ]
    lines.extend(["", _telegramize_plain_text(_trim(answer, MAX_GENERIC_BODY))])
    return "\n".join(lines)


def _severity_overview(values: dict[str, int]) -> str:
    parts = []
    for key in ("critical", "error", "warning", "info"):
        count = values.get(key, 0)
        if count:
            parts.append(f"{_severity_badge(key)} <code>{count}</code>")
    return " | ".join(parts) if parts else "<i>none</i>"


def _domain_overview(values: dict[str, int]) -> str:
    parts = []
    for key in ("network", "linux", "windows", "vmware"):
        count = values.get(key, 0)
        if count:
            parts.append(f"{DOMAIN_BADGE[key]} <code>{count}</code>")
    return " | ".join(parts) if parts else "<i>none</i>"


def _format_summary_alert(line: str, index: int) -> list[str]:
    match = re.match(r"^-\s+\[([A-Z]+)\]\s+([^ ]+)\s+([^:]+):\s+(.+)$", line)
    if not match:
        return [f"{index}. {escape(line.lstrip('- '))}"]
    severity, source, event_type, message = match.groups()
    return [
        f"{index}. <b>{_severity_badge(severity.lower())}</b> "
        f"<code>{escape(source)}</code>",
        f"   <b>Type:</b> <code>{escape(event_type)}</code>",
        f"   <b>Log:</b> {escape(_trim(message, 220))}",
    ]


def _parse_runbook_issues(answer: str) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for raw_line in answer.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        event = re.match(r"^(\d+)\.\s+\[([A-Z]+)\]\s+(.+?)\s+-\s+(.+)$", line)
        if event:
            if current:
                issues.append(current)
            _, severity, source, event_type = event.groups()
            current = {
                "severity": severity.lower(),
                "source": source,
                "event_type": event_type,
                "log": "",
                "action": "",
                "commands": [],
            }
            continue
        if current is None:
            continue
        if line.startswith("Log:"):
            current["log"] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Hướng xử lý:"):
            current["action"] = line.split(":", 1)[1].strip()
            continue
        command = re.match(r"^-\s+([^:]+):\s+(.+)$", line)
        if command:
            commands = current["commands"]
            if isinstance(commands, list):
                commands.append((command.group(1), command.group(2)))
    if current:
        issues.append(current)
    return issues


def _extract_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def _extract_dict(label: str, text: str) -> dict[str, int]:
    match = re.search(rf"{re.escape(label)}:\s*(\{{[^\n]+\}})", text)
    if not match:
        return {}
    try:
        value = literal_eval(match.group(1))
    except (SyntaxError, ValueError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {str(key).lower(): int(count) for key, count in value.items()}


def _extract_alert_lines(answer: str) -> list[str]:
    return [line for line in answer.splitlines() if re.match(r"^-\s+\[[A-Z]+\]", line.strip())]


def _severity_badge(severity: str) -> str:
    return SEVERITY_BADGE.get(severity.lower(), severity.upper())


def _telegramize_plain_text(text: str) -> str:
    converted = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            converted.append("")
            continue
        if line.endswith(":") and not line.startswith("-"):
            converted.append(f"<b>{escape(line[:-1])}</b>")
        elif line.startswith("- "):
            converted.append(f"• {escape(line[2:])}")
        else:
            converted.append(escape(line))
    return "\n".join(converted)


def _trim(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
