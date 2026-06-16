from __future__ import annotations

from collections import Counter
from collections.abc import Callable
import re
import unicodedata

from infra_log_sentinel.analysis.runbook import recommend_commands
from infra_log_sentinel.models import LogEvent


SEVERITY_ORDER = {"critical": 0, "error": 1, "warning": 2, "info": 3}
DOMAINS = (
    "network",
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
)
SEVERITIES = ("critical", "error", "warning", "info")


def answer_log_question(
    events: list[LogEvent],
    question: str,
    alert_levels: tuple[str, ...],
) -> str:
    question = question.strip()
    if not question:
        return (
            "Bạn có thể hỏi ví dụ:\n"
            "- Tóm tắt log hôm nay\n"
            "- Có critical network nào không?\n"
            "- Cho tôi command xử lý Host memory usage\n"
            "- Phân tích VMware warning\n"
            "- Alert nào cần ưu tiên?"
        )

    filtered = _filter_events(events, question, alert_levels)
    intent = _detect_intent(question)

    if not filtered:
        return (
            "Mình chưa tìm thấy log phù hợp với câu hỏi trong batch hiện tại.\n"
            "Gợi ý: thử thêm domain hoặc loại lỗi, ví dụ `command xử lý vmware memory` "
            "hoặc `command xử lý resource pressure`."
        )

    if intent == "commands":
        return _command_answer(filtered)
    if intent == "cause":
        return _cause_answer(filtered)
    if intent == "summary":
        return _summary_answer(filtered, title="Tóm tắt theo câu hỏi")

    return _priority_answer(filtered)


def should_answer_with_rules_first(question: str) -> bool:
    q = _normalize(question)
    has_log_scope = (
        "log" in q
        or "alert" in q
        or any(domain in q for domain in DOMAINS)
        or any(severity in q for severity in SEVERITIES)
        or bool(_event_type_terms(q))
        or bool(_message_phrase_terms(q))
    )
    if not has_log_scope:
        return False

    if _detect_intent(question) in {"summary", "commands", "cause"}:
        return True

    return any(term in q for term in ["co ", "khong", "nao", "uu tien", "can xem"])


def run_interactive_chat(
    events: list[LogEvent],
    alert_levels: tuple[str, ...],
    responder: Callable[[str], str] | None = None,
) -> None:
    print("Infrastructure Log Sentinel chat. Gõ 'exit' để thoát.")
    print(answer_log_question(events, "", alert_levels))
    while True:
        question = input("\nBạn hỏi: ").strip()
        if question.lower() in {"exit", "quit", "q"}:
            print("Đã thoát chat.")
            return
        if responder is not None:
            print(responder(question))
        else:
            print(answer_log_question(events, question, alert_levels))


def _filter_events(
    events: list[LogEvent],
    question: str,
    alert_levels: tuple[str, ...],
) -> list[LogEvent]:
    normalized_q = _normalize(question)
    domains = _domains_from_question(normalized_q)
    severities = _severities_from_question(normalized_q)

    if "alert" in normalized_q or "uu tien" in normalized_q:
        severities.extend(alert_levels)

    source_matches = [
        event.source.lower()
        for event in events
        if event.source and event.source.lower() in question.lower()
    ]
    event_type_terms = _event_type_terms(normalized_q)
    phrase_terms = _message_phrase_terms(normalized_q)

    scored = _score_events(
        events=events,
        domains=domains,
        severities=tuple(dict.fromkeys(severities)),
        source_matches=source_matches,
        event_type_terms=event_type_terms,
        phrase_terms=phrase_terms,
    )

    if domains or severities or source_matches or event_type_terms or phrase_terms:
        return [event for _, event in scored]
    return _sort_events([event for event in events if event.severity in set(alert_levels)])


def _score_events(
    events: list[LogEvent],
    domains: list[str],
    severities: tuple[str, ...],
    source_matches: list[str],
    event_type_terms: list[str],
    phrase_terms: list[str],
) -> list[tuple[int, LogEvent]]:
    scored: list[tuple[int, LogEvent]] = []
    for event in events:
        haystack = _normalize(" ".join([event.domain, event.source, event.event_type, event.message, event.raw]))
        if domains and event.domain not in domains:
            continue
        if severities and event.severity not in set(severities):
            continue
        if source_matches and event.source.lower() not in source_matches:
            continue
        event_type_match = any(term in haystack for term in event_type_terms)
        phrase_match = any(term in haystack for term in phrase_terms)
        if (event_type_terms or phrase_terms) and not (event_type_match or phrase_match):
            continue

        score = 0
        score += sum(8 for term in phrase_terms if term in haystack)
        score += sum(4 for term in event_type_terms if term in haystack)
        score += sum(3 for domain in domains if domain == event.domain)
        if source_matches and event.source.lower() in source_matches:
            score += 3
        scored.append((score, event))

    return sorted(scored, key=lambda item: (-item[0], *_sort_key(item[1])))


def _domains_from_question(question: str) -> list[str]:
    domains = [domain for domain in DOMAINS if domain in question]
    if not domains and any(term in question for term in ["host memory usage", "hostd", "vimsvc", "esxi", "vcenter"]):
        domains.append("vmware")
    return domains


def _severities_from_question(question: str) -> list[str]:
    severities = [severity for severity in SEVERITIES if severity in question]
    if "nghiem trong" in question or "khan" in question:
        severities.append("critical")
    if "canh bao" in question:
        severities.append("warning")

    # Vietnamese "loi" is usually a generic "issue" in operator questions.
    # Do not force severity=error unless the user explicitly says error.
    if "muc error" in question or "severity error" in question:
        severities.append("error")
    return severities


def _detect_intent(question: str) -> str:
    q = _normalize(question)
    if any(term in q for term in ["command", "lenh", "xu ly", "solution", "remediate", "fix", "khac phuc"]):
        return "commands"
    if any(term in q for term in ["nguyen nhan", "cause", "why", "impact", "tac dong", "phan tich"]):
        return "cause"
    if any(term in q for term in ["tom tat", "summary", "tong quan", "bao nhieu", "count"]):
        return "summary"
    return "priority"


def _summary_answer(events: list[LogEvent], title: str) -> str:
    severity_counts = Counter(event.severity for event in events)
    domain_counts = Counter(event.domain for event in events)
    lines = [
        title,
        f"- Tổng số event phù hợp: {len(events)}",
        f"- Theo severity: {dict(sorted(severity_counts.items()))}",
        f"- Theo domain: {dict(sorted(domain_counts.items()))}",
        "",
        "Top alert cần xem:",
    ]
    lines.extend(_event_lines(events[:5]))
    return "\n".join(lines)


def _priority_answer(events: list[LogEvent]) -> str:
    lines = ["Các alert nên ưu tiên:"]
    lines.extend(_event_lines(events[:7]))
    lines.append("")
    lines.append("Gợi ý: hỏi thêm `command xử lý <domain/type>` để lấy lệnh kiểm tra cụ thể.")
    return "\n".join(lines)


def _cause_answer(events: list[LogEvent]) -> str:
    lines = ["Phân tích nhanh:"]
    for index, event in enumerate(events[:5], start=1):
        lines.extend(
            [
                f"{index}. [{event.severity.upper()}] {event.domain}/{event.source} - {event.event_type}",
                f"   Summary: {event.message}",
                f"   Nguyên nhân khả dĩ: {event.probable_cause}",
                f"   Tác động: {event.impact}",
                f"   Hướng xử lý: {event.recommended_action}",
            ]
        )
    return "\n".join(lines)


def _command_answer(events: list[LogEvent]) -> str:
    lines = ["Runbook command đề xuất:"]
    for index, event in enumerate(events[:3], start=1):
        lines.append(f"{index}. [{event.severity.upper()}] {event.domain}/{event.source} - {event.event_type}")
        lines.append(f"   Log: {event.message}")
        lines.append(f"   Hướng xử lý: {event.recommended_action}")
        for command in recommend_commands(event)[:5]:
            lines.append(f"   - {command.phase}: {command.command}")
            lines.append(f"     Why: {command.purpose}")
    return "\n".join(lines)


def _event_lines(events: list[LogEvent]) -> list[str]:
    if not events:
        return ["- Không có alert phù hợp."]
    return [
        f"- [{event.severity.upper()}] {event.domain}/{event.source} {event.event_type}: {event.message}"
        for event in events
    ]


def _sort_events(events: list[LogEvent]) -> list[LogEvent]:
    return sorted(events, key=_sort_key)


def _sort_key(event: LogEvent) -> tuple[int, str, str, str]:
    return (SEVERITY_ORDER.get(event.severity, 99), event.domain, event.source, event.event_type)


def _event_type_terms(question: str) -> list[str]:
    terms = []
    mapping = {
        "bgp": "routing_neighbor",
        "ospf": "routing_neighbor",
        "routing": "routing_neighbor",
        "route": "routing_neighbor",
        "neighbor": "routing_neighbor",
        "payment subnet": "routing_neighbor",
        "interface": "interface",
        "flap": "interface",
        "flapping": "interface",
        "link down": "interface",
        "crc": "interface",
        "fec": "interface",
        "disk": "storage",
        "disk full": "capacity",
        "no space": "capacity",
        "logrotate": "capacity",
        "storage": "storage",
        "datastore": "capacity",
        "snapshot": "snapshot",
        "apd": "storage_path",
        "all paths": "storage_path",
        "auth": "authentication",
        "login": "authentication",
        "ssh": "authentication",
        "brute": "authentication",
        "brute force": "authentication",
        "auth_failed": "authentication",
        "authentication": "authentication",
        "failed password": "authentication",
        "sqlagent": "service",
        "eventid=7031": "service",
        "7031": "service",
        "plugin": "plugin",
        "dll": "dll",
        "service": "service",
        "dns": "dns",
        "named": "dns",
        "resolver": "dns",
        "query timeout": "dns",
        "application timeout": "timeout",
        "upstream timed out": "timeout",
        "fortigate": "fortigate",
        "firewall": "firewall",
        "session": "session",
        "sessions": "session",
        "policy": "policy",
        "deny": "deny",
        "broadcast": "loop",
        "loop": "loop",
        "loopback": "loop",
        "stp": "stp",
        "mac": "mac",
        "lacp": "lacp",
        "cpu": "resource",
        "memory": "resource",
        "resource": "resource",
        "resource pressure": "resource_pressure",
        "pressure": "resource",
        "syn": "syn",
        "host": "host",
        "host memory": "host memory",
        "host memory usage": "host memory usage",
    }
    for needle, term in mapping.items():
        if needle in question:
            terms.append(term)
    if "virtual machine" in question or " vm " in f" {question} ":
        terms.append("vm_")
    return list(dict.fromkeys(terms))


def _message_phrase_terms(question: str) -> list[str]:
    phrases = []
    known_phrases = [
        "host memory usage",
        "memory usage is high",
        "memory pressure",
        "power supply",
        "possible syn flooding",
        "critical medium error",
        "sqlagent service",
        "bgp notification",
        "mac address",
        "auth_failed",
        "failed password",
    ]
    for phrase in known_phrases:
        if phrase in question:
            phrases.append(phrase)

    percent_match = re.search(r"\b(\d{1,3})\s*percent\b", question)
    if percent_match:
        phrases.append(f"{percent_match.group(1)} percent")
    return phrases


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return value.lower()
