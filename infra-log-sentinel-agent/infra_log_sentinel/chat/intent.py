from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata


INTENT_LOG_QUESTION = "log_question"
INTENT_SAFE_ACTION = "safe_action"
INTENT_AMBIGUOUS_OPERATIONAL_CHANGE = "ambiguous_operational_change"
INTENT_ASSISTANT_FEEDBACK = "assistant_feedback"
INTENT_GENERAL_QUESTION = "general_question"

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

CHANGE_TERMS = ("doi", "set", "edit", "change", "cap nhat", "thanh", "cau hinh")
SAFE_ACTION_TERMS = (
    "xuat",
    "tao",
    "generate",
    "create",
    "export",
    "gui",
    "send",
    "tam dung",
    "tam ngung",
    "pause",
    "bat lai",
    "resume",
    "enable",
    "disable",
)
LOG_INFO_TERMS = (
    "tom tat",
    "summary",
    "tong quan",
    "bao nhieu",
    "count",
    "co",
    "khong",
    "nao",
    "command",
    "lenh",
    "xu ly",
    "solution",
    "khac phuc",
    "nguyen nhan",
    "cause",
    "impact",
    "tac dong",
    "phan tich",
    "uu tien",
    "can xem",
)
OPERATIONAL_TARGET_TERMS = (
    "telegram",
    "gmail",
    "email",
    "mail",
    "scheduler",
    "runtime",
    "generator",
    "sinh log",
    "auto log",
    "alert",
    "canh bao",
    "report",
    "bao cao",
    "interval",
    "chu ky",
    "tan suat",
    "severity",
    "level",
    "threshold",
    "nguong",
    "model",
    "channel",
    "kenh",
    "config",
    "setting",
    "tham so",
)
RUNBOOK_TERMS = (
    "bgp",
    "ospf",
    "interface",
    "disk",
    "storage",
    "datastore",
    "auth",
    "login",
    "service",
    "cpu",
    "memory",
    "resource",
    "syn",
    "host",
    "vcenter",
    "esxi",
)


@dataclass(frozen=True)
class ChatIntent:
    kind: str
    action_candidate: bool
    rules_first: bool
    reason: str


def classify_chat_intent(question: str) -> ChatIntent:
    q = normalize_text(question)
    if not q:
        return ChatIntent(
            kind=INTENT_GENERAL_QUESTION,
            action_candidate=False,
            rules_first=False,
            reason="empty question",
        )

    if _looks_like_assistant_feedback(q):
        return ChatIntent(
            kind=INTENT_ASSISTANT_FEEDBACK,
            action_candidate=False,
            rules_first=False,
            reason="user is correcting or discussing the assistant behavior",
        )

    if _looks_like_safe_action(q):
        return ChatIntent(
            kind=INTENT_SAFE_ACTION,
            action_candidate=True,
            rules_first=False,
            reason="explicit action verb and operational target",
        )

    if _looks_like_log_question(q):
        return ChatIntent(
            kind=INTENT_LOG_QUESTION,
            action_candidate=False,
            rules_first=True,
            reason="informational log question",
        )

    if _looks_like_ambiguous_operational_change(q):
        return ChatIntent(
            kind=INTENT_AMBIGUOUS_OPERATIONAL_CHANGE,
            action_candidate=True,
            rules_first=False,
            reason="change-like operational request without enough target context",
        )

    return ChatIntent(
        kind=INTENT_GENERAL_QUESTION,
        action_candidate=False,
        rules_first=False,
        reason="no high-confidence action or log-question signal",
    )


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("đ", "d")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def has_term(q: str, term: str) -> bool:
    if " " in term or "_" in term:
        return term in q
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", q))


def has_any_term(q: str, terms: tuple[str, ...]) -> bool:
    return any(has_term(q, term) for term in terms)


def _looks_like_safe_action(q: str) -> bool:
    if "control status" in q or "trang thai control" in q or "trang thai pause" in q:
        return True
    if any(term in q for term in ["kiem tra log moi", "scan new", "new log"]):
        return True
    if has_any_term(q, ("csv", "export", "excel", "xuat file", "xuat danh sach")):
        return True
    if has_any_term(q, ("gmail", "email", "mail")) and has_any_term(q, ("gui", "send")):
        return True
    if has_any_term(q, ("pdf", "xuat bao cao", "tao bao cao", "generate report", "create report")):
        return True
    if has_any_term(q, ("tam dung", "tam ngung", "pause", "bat lai", "resume", "enable")):
        return has_any_term(q, OPERATIONAL_TARGET_TERMS)
    if has_any_term(q, CHANGE_TERMS):
        return has_any_term(q, SAFE_ACTION_TERMS) and has_any_term(q, OPERATIONAL_TARGET_TERMS)
    return False


def _looks_like_assistant_feedback(q: str) -> bool:
    feedback_patterns = (
        "toi dang hoi ban",
        "toi hoi ban",
        "toi chi hoi",
        "hoi ban chu",
        "khong phai yeu cau",
        "khong yeu cau",
        "khong phai la yeu cau",
        "toi khong yeu cau thay doi",
        "khong de cap den viec thay doi",
        "khong de cap viec thay doi",
        "trong cau hoi tren khong de cap",
        "cau hoi tren khong de cap",
        "cau hoi truoc khong de cap",
        "khong co y thay doi",
        "ban dang khong hieu",
        "bot dang khong hieu",
        "agent dang khong hieu",
        "tra loi sai",
        "tra loi khong dung",
        "khong dung y",
        "khong lien quan",
        "logic tra loi",
        "cach tra loi",
    )
    if any(pattern in q for pattern in feedback_patterns):
        return True
    return (
        has_any_term(q, ("ban", "bot", "agent"))
        and has_any_term(q, ("sai", "khong dung", "khong hieu", "khong lien quan"))
    )


def _looks_like_log_question(q: str) -> bool:
    has_log_scope = (
        has_any_term(q, ("log", "alert", "event"))
        or has_any_term(q, DOMAINS)
        or has_any_term(q, SEVERITIES)
        or has_any_term(q, RUNBOOK_TERMS)
    )
    if not has_log_scope:
        return False
    if has_any_term(q, CHANGE_TERMS) and has_any_term(q, OPERATIONAL_TARGET_TERMS):
        return False
    return has_any_term(q, LOG_INFO_TERMS)


def _looks_like_ambiguous_operational_change(q: str) -> bool:
    return has_any_term(q, CHANGE_TERMS) and has_any_term(q, OPERATIONAL_TARGET_TERMS)
