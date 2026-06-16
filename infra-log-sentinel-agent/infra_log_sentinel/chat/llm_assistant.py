from __future__ import annotations

from collections import Counter
import json
import re
from typing import Any

import requests

from infra_log_sentinel.analysis.runbook import recommend_commands
from infra_log_sentinel.config import Settings
from infra_log_sentinel.models import LogEvent


def answer_with_llm(
    settings: Settings,
    events: list[LogEvent],
    question: str,
    alert_levels: tuple[str, ...],
) -> str | None:
    if not _llm_is_configured(settings):
        return None

    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": _system_prompt(),
            },
            {
                "role": "user",
                "content": _user_prompt(events=events, question=question, alert_levels=alert_levels),
            },
        ],
        "temperature": 0.2,
        "max_tokens": 1800,
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            _chat_completions_url(settings.llm_api_base),
            headers=headers,
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        return (
            "Mình chưa gọi được LLM để trả lời theo kiểu ChatGPT, nên đang dùng logic phân tích nội bộ.\n"
            f"LLM error: {type(exc).__name__}: {exc}"
        )

    answer = _extract_answer(data)
    if not answer:
        return None
    return answer.strip()


def suggest_rca_next_steps_with_llm(
    settings: Settings,
    events: list[LogEvent],
    question: str,
    analysis: dict[str, Any],
    alert_levels: tuple[str, ...],
) -> str | None:
    if not _llm_is_configured(settings):
        return None

    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": _rca_guidance_system_prompt(),
            },
            {
                "role": "user",
                "content": _rca_guidance_user_prompt(
                    events=events,
                    question=question,
                    analysis=analysis,
                    alert_levels=alert_levels,
                ),
            },
        ],
        "temperature": 0.15,
        "max_tokens": 1100,
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            _chat_completions_url(settings.llm_api_base),
            headers=headers,
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    answer = _extract_answer(data)
    if not answer:
        return None
    return answer.strip()


def adjudicate_rca_with_llm(
    settings: Settings,
    question: str,
    analysis: dict[str, Any],
) -> dict[str, Any] | None:
    if not _llm_is_configured(settings):
        return None
    if not analysis.get("timeline"):
        return None

    payload = {
        "model": settings.llm_model,
        "messages": [
            {
                "role": "system",
                "content": _rca_adjudicator_system_prompt(),
            },
            {
                "role": "user",
                "content": _rca_adjudicator_user_prompt(question=question, analysis=analysis),
            },
        ],
        "temperature": 0.05,
        "max_tokens": 900,
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            _chat_completions_url(settings.llm_api_base),
            headers=headers,
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    answer = _extract_answer(data)
    if not answer:
        return None
    return _parse_json_object(answer)


def _llm_is_configured(settings: Settings) -> bool:
    return all(
        [
            settings.llm_api_base.strip(),
            settings.llm_api_key.strip(),
            settings.llm_model.strip(),
        ]
    )


def _rca_adjudicator_system_prompt() -> str:
    return (
        "You are an RCA adjudicator for infrastructure logs. A deterministic analyzer has already selected "
        "a small correlated event set. Your job is to review that evidence, not to search or invent data. "
        "Use only the provided timeline, evidence, impact, and missing-data fields. If the candidate is weak, "
        "say so. If a different root cause is better supported by the provided events, explain it. Never create "
        "new hosts, timestamps, alert counts, or log lines. Return JSON only."
    )


def _rca_adjudicator_user_prompt(question: str, analysis: dict[str, Any]) -> str:
    packet = {
        "user_question_or_impact": question,
        "incident_id": analysis.get("incident_id"),
        "scope": analysis.get("scope_label"),
        "deterministic_status": analysis.get("status"),
        "deterministic_confidence": analysis.get("confidence"),
        "deterministic_root_cause": analysis.get("most_likely_root_cause"),
        "summary": analysis.get("summary"),
        "impact": analysis.get("impact"),
        "focus_terms": list(analysis.get("focus_terms") or [])[:8],
        "timeline": list(analysis.get("timeline") or [])[:10],
        "evidence": list(analysis.get("evidence") or [])[:6],
        "missing_data": list(analysis.get("missing_data") or [])[:6],
        "recommended_actions": analysis.get("recommended_actions") or {},
    }
    schema = {
        "verdict": "confirmed | needs_verification | insufficient_data | contradicted",
        "root_cause": "short root cause statement grounded only in provided events",
        "confidence": "integer 0-95, do not exceed deterministic confidence by more than 8",
        "rationale": ["1-3 concise evidence-based reasons"],
        "missing_data": ["0-4 concrete data items to verify"],
        "recommended_actions": ["0-4 safe next actions"],
    }
    return "\n".join(
        [
            "Review this RCA evidence packet and return JSON only.",
            "",
            "Evidence packet:",
            json.dumps(packet, ensure_ascii=False, indent=2),
            "",
            "Required JSON schema:",
            json.dumps(schema, ensure_ascii=False, indent=2),
        ]
    )


def _rca_guidance_system_prompt() -> str:
    return (
        "You are an RCA investigation assistant for infrastructure logs. "
        "The deterministic log analyzer has already concluded that the current log evidence is insufficient. "
        "Do not invent or confirm a root cause. Do not fabricate alert counts, timestamps, hosts, or commands. "
        "Behave like a careful public LLM assistant: explain why the RCA cannot be confirmed, offer plausible "
        "hypotheses clearly marked as unconfirmed, and propose safe next checks. Answer in Vietnamese Markdown, "
        "concise and practical. Do not use the eleven-question RCA format. Include command blocks only when they "
        "are directly useful. The answer must make clear that RCA is not confirmed yet."
    )


def _rca_guidance_user_prompt(
    events: list[LogEvent],
    question: str,
    analysis: dict[str, Any],
    alert_levels: tuple[str, ...],
) -> str:
    alert_set = set(alert_levels)
    matching_events = _rank_relevant_events(events, question)
    alert_events = [event for event in events if event.severity in alert_set]
    context_events = (matching_events or alert_events or events)[:8]

    lines = [
        f"User impact/question: {question}",
        "",
        "Deterministic RCA analyzer result:",
        f"- Incident id: {analysis.get('incident_id', '-')}",
        f"- Status: {analysis.get('status', '-')}",
        f"- Confidence: {analysis.get('confidence', 0)}%",
        f"- Candidate: {analysis.get('most_likely_root_cause', '-')}",
        f"- Summary: {analysis.get('summary', '-')}",
        f"- Correlated events: {analysis.get('correlated_events', 0)}",
        f"- Missing data: {list(analysis.get('missing_data') or [])[:6]}",
        "",
        "Available log context:",
    ]
    if not context_events:
        lines.append("- No parsed events available.")
    for index, event in enumerate(context_events, start=1):
        lines.extend(
            [
                f"{index}. [{event.severity.upper()}] {event.domain}/{event.source} - {event.event_type}",
                f"   Timestamp: {event.timestamp}",
                f"   Log: {event.message}",
                f"   Probable cause: {event.probable_cause}",
                f"   Recommended action: {event.recommended_action}",
            ]
        )

    lines.extend(
        [
            "",
            "Output format:",
            "## LLM guidance: RCA chưa đủ dữ liệu",
            "- Kết luận: nói rõ hiện tại chưa đủ log/evidence để xác nhận root cause.",
            "- Vì sao chưa đủ: giải thích các điểm thiếu hoặc tín hiệu yếu bằng 2-3 bullet.",
            "- Giả thuyết có thể kiểm tra: đưa 2-4 giả thuyết chưa xác nhận, dựa trên impact và log snippet.",
            "- Dữ liệu cần bổ sung: nêu log, metrics, topology, change record hoặc xác nhận owner cần thu thập.",
            "- Bước tiếp theo an toàn: nêu các bước verify không phá vỡ hệ thống; không remediate mạnh nếu chưa đủ bằng chứng.",
        ]
    )
    return "\n".join(lines)

    lines.extend(
        [
            "",
            "Output format:",
            "## RCA chưa đủ dữ liệu",
            "### 1. Sự cố gì đang xảy ra?",
            "Answer from user impact and available logs; say unknown if logs do not prove it.",
            "### 2. Sự cố bắt đầu từ thời điểm nào?",
            "Use earliest provided relevant timestamp, otherwise say not enough log evidence.",
            "### 3. Event nào xảy ra đầu tiên?",
            "Name the earliest relevant log event, otherwise say none available.",
            "### 4. Event nào là triệu chứng?",
            "List likely symptom events only from provided logs.",
            "### 5. Event nào là hậu quả?",
            "List likely downstream consequence events only from provided logs.",
            "### 6. Event nào là root cause candidate?",
            "Name a candidate only if log evidence supports it; otherwise say no candidate yet.",
            "### 7. Root cause khả năng cao nhất là gì?",
            "If insufficient, explicitly say RCA is not confirmed.",
            "### 8. Bằng chứng là gì?",
            "Use only analyzer evidence and provided logs.",
            "### 9. Độ tin cậy bao nhiêu phần trăm?",
            "Use analyzer confidence; do not invent a different score.",
            "### 10. Cần kiểm tra thêm dữ liệu gì?",
            "List concrete missing logs, metrics, topology, change records, or owner validation.",
            "### 11. Nên xử lý ra sao?",
            "Give the safest next steps. Do not recommend disruptive remediation without evidence.",
        ]
    )
    return "\n".join(lines)


def _chat_completions_url(base_url: str) -> str:
    base = base_url.strip().rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/v1/chat/completions"


def _extract_answer(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    if isinstance(first.get("text"), str):
        return first["text"]
    return ""


def _parse_json_object(value: str) -> dict[str, Any] | None:
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        text = match.group(0)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _system_prompt() -> str:
    return (
        "You are Infra Log Sentinel Agent, a senior infrastructure and network operations assistant. "
        "Answer in Vietnamese unless the user asks otherwise. Be conversational like ChatGPT, but stay grounded "
        "in the provided log context and runbook commands. Think like an SRE operator, not a keyword bot. "
        "Classify each user message first: informational question, log investigation, runtime action, or "
        "ambiguous/high-impact operational change. If the user asks to change, pause, resume, send, schedule, "
        "configure, or notify but omits the target, value, time window, channel, or confirmation, ask "
        "one concise clarifying question and offer 2-4 concrete options. Do not guess operational intent. "
        "If the exact log is not present, say that clearly, then provide the safest likely investigation path. "
        "Never invent alert counts, hosts, or commands that conflict with the context. For operational questions, "
        "include concrete verification commands and a short recommended next action. Do not use emoji. Use clear "
        "Markdown headings, bold emphasis for severity or impact, and fenced code blocks for commands so the UI "
        "can render copy buttons."
    )


def _user_prompt(events: list[LogEvent], question: str, alert_levels: tuple[str, ...]) -> str:
    alert_set = set(alert_levels)
    alert_events = [event for event in events if event.severity in alert_set]
    severity_counts = Counter(event.severity for event in events)
    domain_counts = Counter(event.domain for event in events)
    matching_events = _rank_relevant_events(events, question)
    context_events = matching_events[:8] if matching_events else alert_events[:8]

    lines = [
        f"User question: {question}",
        "",
        "Current log batch summary:",
        f"- Total parsed events: {len(events)}",
        f"- Severity counts: {dict(sorted(severity_counts.items()))}",
        f"- Domain counts: {dict(sorted(domain_counts.items()))}",
        "",
        "Relevant events and runbook context:",
    ]
    if not context_events:
        lines.append("- No parsed events available.")
    for index, event in enumerate(context_events, start=1):
        lines.extend(
            [
                f"{index}. [{event.severity.upper()}] {event.domain}/{event.source} - {event.event_type}",
                f"   Log: {event.message}",
                f"   Probable cause: {event.probable_cause}",
                f"   Impact: {event.impact}",
                f"   Recommended action: {event.recommended_action}",
                "   Commands:",
            ]
        )
        for command in recommend_commands(event)[:5]:
            lines.append(f"   - {command.phase}: {command.command} ({command.purpose})")

    lines.extend(
        [
            "",
            "Instructions for answer:",
            "- Start with the direct answer.",
            "- Keep the answer concise enough for a chat UI, usually under 900 Vietnamese words.",
            "- If the user asks for commands, provide commands grouped by Verify, Investigate, Remediate.",
            "- Put command examples inside fenced code blocks with language `powershell`, `bash`, or `text`.",
            "- If the user asks a broad question, summarize what the current logs suggest and what to do next.",
            "- If the user asks to change runtime behavior but misses target/value/time/channel, ask a concise clarification before recommending any action.",
            "- For ambiguous words like interval, schedule, threshold, pause, resume, send, report, alert, or it/that, explain what you need clarified.",
            "- If context does not contain an exact match, say so and provide a safe general approach.",
        ]
    )
    return "\n".join(lines)


def _rank_relevant_events(events: list[LogEvent], question: str) -> list[LogEvent]:
    q_terms = _keywords(question)
    if not q_terms:
        return []

    scored: list[tuple[int, LogEvent]] = []
    for event in events:
        haystack = " ".join(
            [
                event.domain,
                event.source,
                event.severity,
                event.event_type.replace("_", " "),
                event.message,
                event.probable_cause,
                event.impact,
                event.recommended_action,
            ]
        ).lower()
        score = sum(1 for term in q_terms if term in haystack)
        if "host memory usage" in question.lower() and "host memory usage" in haystack:
            score += 8
        if score:
            scored.append((score, event))
    return [event for _, event in sorted(scored, key=lambda item: (-item[0], item[1].domain, item[1].source))]


def _keywords(question: str) -> list[str]:
    raw_terms = [term.lower() for term in question.replace("_", " ").split()]
    stop_words = {
        "toi",
        "tôi",
        "hay",
        "cho",
        "can",
        "cần",
        "command",
        "xu",
        "xử",
        "ly",
        "lý",
        "loi",
        "lỗi",
        "the",
        "and",
        "is",
        "are",
        "what",
        "how",
    }
    terms = [term.strip(".,:;!?()[]{}\"'`") for term in raw_terms]
    terms = [term for term in terms if len(term) >= 3 and term not in stop_words]
    if "host memory usage" in question.lower():
        terms.append("host memory usage")
    return list(dict.fromkeys(terms))
