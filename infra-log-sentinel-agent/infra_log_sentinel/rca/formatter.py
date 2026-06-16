from __future__ import annotations

from html import escape
from typing import Any


def format_rca_report(analysis: dict[str, Any]) -> str:
    actions = analysis.get("recommended_actions") if isinstance(analysis.get("recommended_actions"), dict) else {}
    lines = [
        "AIOps RCA Investigation",
        "",
        "Root cause:",
        *_format_root_cause_table(analysis),
        "",
        "Event timeline:",
        *_format_timeline_table(_items(analysis.get("timeline"))),
        "",
        "Evidence:",
        *_format_bullets(_items_text(analysis.get("evidence"))[:4], "- Current logs do not provide strong evidence yet."),
        *_format_llm_guidance(analysis.get("llm_guidance")),
        "",
        "Action plan:",
        *_format_action_table(actions),
    ]
    return "\n".join(lines)


def _format_llm_guidance(value: Any) -> list[str]:
    guidance = str(value or "").strip()
    if not guidance:
        return []
    return ["", "LLM guidance:", guidance]


def _format_root_cause_table(analysis: dict[str, Any]) -> list[str]:
    llm_review = _llm_review_line(analysis.get("llm_review"))
    rows = [
        "| Field | Detail |",
        "|---|---|",
        f"| Root cause | **{_table_cell(str(analysis.get('most_likely_root_cause') or '-'), 260)}** |",
        f"| Impact | {_table_cell(str(analysis.get('impact') or '-'), 220)} |",
        (
            "| Confidence | "
            f"`{analysis.get('confidence', 0)}%` / Severity `{str(analysis.get('severity', '-')).upper()}` / "
            f"Status `{analysis.get('status', '-')}` |"
        ),
    ]
    if llm_review:
        rows.append(f"| LLM review | {_table_cell(llm_review, 220)} |")
    rows.extend(
        [
            f"| Scope | `{_table_cell(str(analysis.get('scope_label') or '-'), 120)}` |",
            f"| Incident | `{_table_cell(str(analysis.get('incident_id') or '-'), 120)}` |",
        ]
    )
    return rows


def _llm_review_line(value: Any) -> str:
    if not isinstance(value, dict) or not value.get("applied"):
        return ""
    verdict = str(value.get("verdict") or "-")
    rationale = _items_text(value.get("rationale"))
    suffix = f" - {_compact_text(rationale[0], 140)}" if rationale else ""
    return f"LLM review: `{verdict}`{suffix}"


def format_rca_telegram(analysis: dict[str, Any]) -> str:
    actions = analysis.get("recommended_actions") if isinstance(analysis.get("recommended_actions"), dict) else {}
    action_items = _items_text(actions.get("immediate_actions")) + _items_text(actions.get("verification_actions"))

    lines = [
        "<b>AIOps RCA Alert</b>",
        "",
        f"<b>Incident ID:</b> <code>{escape(str(analysis.get('incident_id', '-')))}</code>",
        f"<b>Severity:</b> <code>{escape(str(analysis.get('severity', '-')).upper())}</code>",
        f"<b>Status:</b> <code>{escape(str(analysis.get('status', '-')))}</code>",
        f"<b>Confidence:</b> <code>{escape(str(analysis.get('confidence', 0)))}%</code>",
        "",
        "<b>Root cause</b>",
        escape(_compact_text(str(analysis.get("most_likely_root_cause") or "-"), 360)),
        "",
        "<b>Evidence</b>",
        *_html_numbered(_items_text(analysis.get("evidence"))[:3]),
        *_html_llm_guidance(analysis.get("llm_guidance")),
        "",
        "<b>Next actions</b>",
        *_html_numbered(action_items[:3]),
    ]
    return "\n".join(lines)


def _html_llm_guidance(value: Any) -> list[str]:
    guidance = str(value or "").strip()
    if not guidance:
        return []
    return ["", "<b>LLM guidance</b>", escape(_compact_text(guidance, 900))]


def _numbered(values: Any, empty: str) -> list[str]:
    items = _items_text(values)
    if not items:
        return [empty]
    return [f"{index}. {value}" for index, value in enumerate(items, start=1)]


def _html_numbered(values: list[str]) -> list[str]:
    if not values:
        return ["- None"]
    return [f"{index}. {escape(value)}" for index, value in enumerate(values, start=1)]


def _format_question_answers(questions: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in questions[:11]:
        question = str(item.get("question") or "-")
        lines.append(f"**{question}**")
        lines.extend(_format_answer(item.get("answer"), max_items=_answer_limit(item.get("id"))))
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def _html_question_answers(questions: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in questions[:11]:
        question = str(item.get("question") or "-")
        lines.append(f"<b>{escape(question)}</b>")
        lines.extend(_html_answer(item.get("answer"), max_items=_answer_limit(item.get("id"))))
        lines.append("")
    if lines and lines[-1] == "":
        lines.pop()
    return lines or ["- None"]


def _format_timeline_table(timeline: list[dict[str, Any]]) -> list[str]:
    if not timeline:
        return ["| Time | Role | Source | Event |", "|---|---|---|---|", "| - | - | - | No timeline evidence. |"]
    rows = ["| Time | Role | Source | Event |", "|---|---|---|---|"]
    for item in timeline[:8]:
        rows.append(
            "| "
            + " | ".join(
                [
                    _table_cell(str(item.get("time") or "-"), 34),
                    _table_cell(_role_label(str(item.get("type") or "-")), 22),
                    _table_cell(str(item.get("source") or "-"), 34),
                    _table_cell(str(item.get("event") or "-"), 110),
                ]
            )
            + " |"
        )
    return rows


def _format_bullets(values: list[str], empty: str) -> list[str]:
    if not values:
        return [empty]
    return [f"- {_compact_text(value, 220)}" for value in values]


def _format_action_table(actions: dict[str, Any]) -> list[str]:
    immediate = _items_text(actions.get("immediate_actions"))[:3]
    verify = _items_text(actions.get("verification_actions"))[:3]
    prevent = _items_text(actions.get("long_term_prevention"))[:2]
    rows = ["| Priority | Action |", "|---|---|"]
    for label, values in (
        ("Immediate", immediate),
        ("Verify", verify),
        ("Prevent", prevent),
    ):
        if values:
            rows.append(f"| {label} | {_table_cell(values[0], 180)} |")
            for value in values[1:]:
                rows.append(f"|  | {_table_cell(value, 180)} |")
    if len(rows) == 2:
        rows.append("| Verify | Collect more evidence before remediation. |")
    return rows


def _fallback_questions(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    timeline = _items(analysis.get("timeline"))
    first_event = timeline[0] if timeline else {}
    root_event = _first_timeline(timeline, {"root_cause_candidate", "change"}) or first_event
    symptoms = _timeline_by_type(timeline, {"symptom"})
    consequences = _timeline_by_type(timeline, {"impact", "consequence"})
    actions = analysis.get("recommended_actions") if isinstance(analysis.get("recommended_actions"), dict) else {}
    action_items = _items_text(actions.get("immediate_actions")) + _items_text(actions.get("verification_actions"))
    confidence = int(analysis.get("confidence") or 0)
    status_text = "confirmed" if confidence >= 85 else "needs verification" if confidence >= 70 else "insufficient evidence"
    return [
        {
            "id": "incident",
            "question": "1. Sự cố gì đang xảy ra?",
            "answer": analysis.get("summary") or analysis.get("impact") or "-",
        },
        {
            "id": "start_time",
            "question": "2. Sự cố bắt đầu từ thời điểm nào?",
            "answer": f"Dấu hiệu đầu tiên trong dữ liệu RCA: `{first_event.get('time', '-')}`.",
        },
        {
            "id": "first_event",
            "question": "3. Event nào xảy ra đầu tiên?",
            "answer": _timeline_text(first_event),
        },
        {
            "id": "symptom_events",
            "question": "4. Event nào là triệu chứng?",
            "answer": [_timeline_text(item) for item in symptoms] or _items_text(analysis.get("symptoms")) or ["Chưa tách được symptom event rõ ràng."],
        },
        {
            "id": "consequence_events",
            "question": "5. Event nào là hậu quả?",
            "answer": [_timeline_text(item) for item in consequences] or ["Chưa thấy hậu quả downstream rõ ràng trong dữ liệu hiện tại."],
        },
        {
            "id": "root_candidate_event",
            "question": "6. Event nào là root cause candidate?",
            "answer": _timeline_text(root_event),
        },
        {
            "id": "most_likely_root_cause",
            "question": "7. Root cause khả năng cao nhất là gì?",
            "answer": f"{analysis.get('most_likely_root_cause') or '-'} RCA status: `{status_text}`.",
        },
        {
            "id": "evidence",
            "question": "8. Bằng chứng là gì?",
            "answer": _items_text(analysis.get("evidence")) or ["Chưa đủ bằng chứng log để kết luận."],
        },
        {
            "id": "confidence",
            "question": "9. Độ tin cậy bao nhiêu phần trăm?",
            "answer": f"`{confidence}%` dựa trên correlation, thứ tự thời gian và bằng chứng hiện có.",
        },
        {
            "id": "missing_data",
            "question": "10. Cần kiểm tra thêm dữ liệu gì?",
            "answer": _items_text(analysis.get("missing_data")) or ["Không có missing data được xác định."],
        },
        {
            "id": "actions",
            "question": "11. Nên xử lý ra sao?",
            "answer": action_items or ["Giữ nguyên hiện trạng, bổ sung log/metrics và chạy lại RCA trước khi remediate."],
        },
    ]


def _first_timeline(timeline: list[dict[str, Any]], types: set[str]) -> dict[str, Any]:
    for item in timeline:
        if str(item.get("type") or "") in types:
            return item
    return {}


def _timeline_by_type(timeline: list[dict[str, Any]], types: set[str]) -> list[dict[str, Any]]:
    return [item for item in timeline if str(item.get("type") or "") in types]


def _timeline_text(item: dict[str, Any]) -> str:
    if not item:
        return "-"
    parts = [
        str(item.get("time") or "-"),
        str(item.get("source") or "-"),
        str(item.get("event") or "-"),
    ]
    return " | ".join(_compact_text(part, 120) for part in parts)


def _answer_limit(question_id: Any) -> int:
    if question_id in {"evidence", "missing_data", "actions"}:
        return 3
    if question_id in {"symptom_events", "consequence_events"}:
        return 2
    return 1


def _format_answer(answer: Any, max_items: int = 2) -> list[str]:
    if isinstance(answer, list):
        values = [str(value) for value in answer if str(value).strip()]
        clipped = [_compact_text(value) for value in values[:max_items]]
        return [f"- {value}" for value in clipped] or ["-"]
    return [_compact_text(str(answer or "-"))]


def _html_answer(answer: Any, max_items: int = 2) -> list[str]:
    if isinstance(answer, list):
        values = [str(value) for value in answer if str(value).strip()]
        clipped = [_compact_text(value) for value in values[:max_items]]
        return [f"- {escape(value)}" for value in clipped] or ["-"]
    return [escape(_compact_text(str(answer or "-")))]


def _compact_text(value: str, limit: int = 180) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _table_cell(value: str, limit: int = 120) -> str:
    return _compact_text(value, limit).replace("|", "/")


def _role_label(value: str) -> str:
    labels = {
        "root_cause_candidate": "Root candidate",
        "change": "Change",
        "symptom": "Symptom",
        "impact": "Impact",
        "consequence": "Consequence",
        "evidence": "Evidence",
    }
    return labels.get(value, value or "-")


def _items_text(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def _items(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, dict)]
