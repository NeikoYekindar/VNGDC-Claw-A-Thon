from __future__ import annotations

from collections import Counter
from datetime import datetime
import re
from typing import Any

from infra_log_sentinel.models import LogEvent


SEVERITY_RANK = {
    "critical": 0,
    "error": 1,
    "warning": 2,
    "info": 3,
}

ROOT_CAUSE_EVENT_TYPES = {
    "switch_port_errdisable": "Loopback or protection event disabled a switch port.",
    "mac_flapping": "Layer-2 instability such as loop, mispatch, or teaming issue.",
    "routing_neighbor_down": "Routing adjacency loss or control-plane transport issue.",
    "storage_path_issue": "Storage path, disk, or datastore IO issue.",
    "capacity_warning": "Capacity pressure crossed an operational threshold.",
    "service_failure": "Service/process failure, often after dependency or deployment change.",
    "application_crash": "Application crash or dependency fault.",
    "dns_timeout": "DNS service timeout or resolver dependency issue.",
    "vpn_tunnel_down": "VPN tunnel outage or firewall transport issue.",
    "wireless_ap_down": "Wireless access point lost controller connectivity.",
    "wireless_gateway_failover": "Wireless gateway failover or cluster peer loss.",
    "monitoring_polling_failure": "Monitoring scrape or SNMP polling cannot reach the target.",
    "monitoring_datasource_failure": "Dashboard or alerting datasource query failed.",
    "search_cluster_red": "Elasticsearch primary shard or cluster health issue.",
    "log_pipeline_blocked": "Log ingestion pipeline is blocked or backpressured.",
    "security_threat_detected": "Security control detected malware, IPS, or antivirus activity.",
    "file_integrity_change": "Unexpected file integrity change or configuration drift.",
    "network_packet_loss": "Packet loss on a monitored network path.",
    "authentication_failure": "Credential failure pattern or possible brute-force activity.",
    "possible_syn_flood": "Traffic surge or SYN flood pattern.",
    "power_supply_failure": "Hardware power module failure or removal.",
    "host_failure": "Hypervisor/host connectivity, power, or management failure.",
    "interface_down": "Physical/interface state failure or peer-side shutdown.",
}

ROOT_CAUSE_PRIORITY = {
    "switch_port_errdisable": 0,
    "application_crash": 0,
    "capacity_warning": 0,
    "authentication_failure": 0,
    "possible_syn_flood": 0,
    "mac_flapping": 1,
    "interface_down": 1,
    "storage_path_issue": 2,
    "dns_timeout": 2,
    "vpn_tunnel_down": 2,
    "wireless_ap_down": 2,
    "wireless_gateway_failover": 2,
    "monitoring_polling_failure": 2,
    "monitoring_datasource_failure": 2,
    "network_packet_loss": 2,
    "search_cluster_red": 3,
    "log_pipeline_blocked": 3,
    "security_threat_detected": 3,
    "file_integrity_change": 3,
    "service_failure": 3,
    "routing_neighbor_down": 3,
    "host_failure": 3,
    "power_supply_failure": 3,
}

CHANGE_PATTERNS = (
    re.compile(r"\bconfigured\b", re.IGNORECASE),
    re.compile(r"\btype=config\b", re.IGNORECASE),
    re.compile(r"\bconfig(?:uration)?\s+(?:change|reload|update)\b", re.IGNORECASE),
    re.compile(r"\bdeployed\b", re.IGNORECASE),
    re.compile(r"\bupdated\b", re.IGNORECASE),
    re.compile(r"\bsnapshot created\b", re.IGNORECASE),
    re.compile(r"\bpowered on\b", re.IGNORECASE),
)

FOCUS_ALIASES = {
    "broadcast": "loop",
    "flap": "flapping",
    "flaping": "flapping",
    "flapped": "flapping",
    "session": "session",
    "sessions": "session",
    "fortinet": "fortigate",
    "firewall": "fortigate",
    "fw": "fortigate",
    "bgp": "routing",
    "ospf": "routing",
    "route": "routing",
    "routes": "routing",
    "sqlagent": "sqlagent",
}

SIGNAL_PATTERNS = (
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"\b[0-9a-f]{2}(?::[0-9a-f]{2}){5}\b", re.IGNORECASE),
    re.compile(r"\bvlan\s*[-:=]?\s*\d+\b", re.IGNORECASE),
    re.compile(r"\b(?:gi|te|fa|eth|ens)\d+(?:/\d+){0,3}\b", re.IGNORECASE),
    re.compile(r"\b(?:gigabitethernet|tengigabitethernet|fastethernet)\d+(?:/\d+){0,3}\b", re.IGNORECASE),
    re.compile(r"\bport-channel\d+\b", re.IGNORECASE),
    re.compile(r"\bge-\d+/\d+/\d+\b", re.IGNORECASE),
    re.compile(r"\bpolicy(?:id)?\s*[=:-]?\s*\d+\b", re.IGNORECASE),
    re.compile(r"\b[a-z0-9][a-z0-9.-]*\.(?:example\.local|local)\b", re.IGNORECASE),
)


def analyze_log_events(
    events: list[LogEvent],
    lookback_hours: float,
    alert_levels: tuple[str, ...],
    focus_text: str = "",
    window_label: str = "",
) -> dict[str, Any]:
    recent = _sort_events(events)
    alert_set = set(alert_levels)
    alert_events = [event for event in recent if event.severity in alert_set]
    focus_terms = _focus_terms(focus_text)
    candidate_events = _focus_candidate_events(alert_events, recent, focus_terms)
    if focus_terms and not candidate_events:
        return _focus_miss_analysis(
            events=recent,
            lookback_hours=lookback_hours,
            focus_text=focus_text,
            focus_terms=focus_terms,
            window_label=window_label,
        )
    anchor = _choose_anchor(candidate_events, focus_terms)
    if anchor is None:
        return _empty_analysis(lookback_hours, window_label=window_label)

    cluster = _related_events(anchor, recent, focus_terms)
    root_candidate = _choose_root_candidate(anchor, cluster, focus_terms)
    evidence = _evidence(cluster, root_candidate)
    confidence = _confidence(cluster, root_candidate, evidence, focus_terms)
    status = "confirmed" if confidence >= 85 else "need_verification" if confidence >= 70 else "insufficient_data"
    cause = _root_cause_text(root_candidate, anchor)

    timeline = [_timeline_item(event, root_candidate) for event in cluster[:10]]
    symptoms = _symptoms(cluster, anchor)
    impact = _impact(cluster, anchor)
    missing_data = _missing_data(cluster)
    recommended_actions = {
        "immediate_actions": _immediate_actions(root_candidate, anchor, confidence),
        "verification_actions": _verification_steps(root_candidate, anchor),
        "long_term_prevention": _prevention(root_candidate, anchor),
    }
    most_likely_root_cause = cause if confidence >= 70 else "Insufficient log evidence for a high-confidence RCA."

    return {
        "incident_id": _incident_id(anchor),
        "source": "log_correlation",
        "severity": anchor.severity,
        "summary": _summary(anchor, cause, len(cluster), lookback_hours, focus_text, window_label),
        "scope_label": window_label or f"last {lookback_hours:g}h",
        "timeline": timeline,
        "symptoms": symptoms,
        "impact": impact,
        "root_cause_hypotheses": [
            {
                "hypothesis": cause,
                "confidence": confidence,
                "supporting_evidence": evidence,
                "contradicting_evidence": _contradicting_evidence(cluster),
                "missing_data": missing_data,
                "verification_steps": _verification_steps(root_candidate, anchor),
            }
        ],
        "most_likely_root_cause": most_likely_root_cause,
        "confidence": confidence,
        "evidence": evidence[:6],
        "recommended_actions": recommended_actions,
        "missing_data": missing_data,
        "status": status,
        "analyzed_events": len(recent),
        "correlated_events": len(cluster),
        "focus_terms": focus_terms,
        "anchor_event": _event_summary(anchor),
        "rca_questions": _rca_question_answers(
            anchor=anchor,
            cluster=cluster,
            root_candidate=root_candidate,
            cause=most_likely_root_cause,
            evidence=evidence,
            confidence=confidence,
            missing_data=missing_data,
            recommended_actions=recommended_actions,
            impact=impact,
            focus_text=focus_text,
        ),
    }


def log_rca_compact(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "incident_id": analysis.get("incident_id"),
        "severity": analysis.get("severity"),
        "status": analysis.get("status"),
        "confidence": analysis.get("confidence"),
        "most_likely_root_cause": analysis.get("most_likely_root_cause"),
        "summary": analysis.get("summary"),
        "evidence": list(analysis.get("evidence") or [])[:3],
        "timeline": list(analysis.get("timeline") or [])[:5],
        "recommended_actions": analysis.get("recommended_actions", {}),
        "correlated_events": analysis.get("correlated_events", 0),
        "analyzed_events": analysis.get("analyzed_events", 0),
        "focus_terms": list(analysis.get("focus_terms") or [])[:6],
        "anchor_event": analysis.get("anchor_event"),
        "rca_questions": list(analysis.get("rca_questions") or [])[:11],
        "llm_review": analysis.get("llm_review"),
        "llm_guidance": analysis.get("llm_guidance"),
    }


def apply_llm_review(analysis: dict[str, Any], review: dict[str, Any] | None) -> dict[str, Any]:
    if not review:
        return analysis

    verdict = _review_verdict(review.get("verdict"))
    deterministic_confidence = _safe_int(analysis.get("confidence"), 0)
    llm_confidence = _safe_int(review.get("confidence"), deterministic_confidence)
    confidence = _merge_review_confidence(deterministic_confidence, llm_confidence, verdict)
    root_cause = _review_text(review.get("root_cause"), 220)
    rationale = _review_list(review.get("rationale"), 3, 220)
    missing_data = _review_list(review.get("missing_data"), 4, 180)
    recommended_actions = _review_list(review.get("recommended_actions"), 4, 180)

    if root_cause and verdict in {"confirmed", "needs_verification"}:
        analysis["most_likely_root_cause"] = root_cause
    analysis["confidence"] = confidence
    analysis["status"] = _status_from_confidence(confidence, verdict)
    analysis["llm_review"] = {
        "provider": "llm",
        "verdict": verdict,
        "confidence": confidence,
        "root_cause": root_cause,
        "rationale": rationale,
        "applied": True,
    }

    evidence = list(analysis.get("evidence") or [])
    if rationale:
        evidence.append(f"LLM review ({verdict}): {rationale[0]}")
    analysis["evidence"] = _dedupe_text(evidence)[:6]

    analysis["missing_data"] = _dedupe_text(list(analysis.get("missing_data") or []) + missing_data)[:6]
    actions = analysis.get("recommended_actions") if isinstance(analysis.get("recommended_actions"), dict) else {}
    verification_actions = list(actions.get("verification_actions") or [])
    actions["verification_actions"] = _dedupe_text(verification_actions + recommended_actions)[:5]
    analysis["recommended_actions"] = actions

    hypotheses = analysis.get("root_cause_hypotheses")
    if isinstance(hypotheses, list) and hypotheses and isinstance(hypotheses[0], dict):
        hypotheses[0]["hypothesis"] = analysis.get("most_likely_root_cause")
        hypotheses[0]["confidence"] = confidence
        hypotheses[0]["supporting_evidence"] = analysis.get("evidence")
        hypotheses[0]["missing_data"] = analysis.get("missing_data")

    _refresh_question_answers_from_review(analysis)
    return analysis


def _empty_analysis(lookback_hours: float, window_label: str = "") -> dict[str, Any]:
    scope_label = window_label or f"last {lookback_hours:g}h"
    return {
        "incident_id": "LOG-RCA-NONE",
        "source": "log_correlation",
        "severity": "info",
        "summary": f"No events are available for RCA in the selected window ({scope_label}).",
        "scope_label": scope_label,
        "timeline": [],
        "symptoms": [],
        "impact": "No impact detected from current logs.",
        "root_cause_hypotheses": [],
        "most_likely_root_cause": "No RCA candidate.",
        "confidence": 0,
        "evidence": [],
        "recommended_actions": {
            "immediate_actions": ["No immediate action required from current logs."],
            "verification_actions": ["Confirm log ingestion is active."],
            "long_term_prevention": [],
        },
        "missing_data": ["Current log window has no events."],
        "status": "insufficient_data",
        "analyzed_events": 0,
        "correlated_events": 0,
        "rca_questions": _empty_rca_question_answers(lookback_hours),
    }


def _focus_miss_analysis(
    events: list[LogEvent],
    lookback_hours: float,
    focus_text: str,
    focus_terms: list[str],
    window_label: str = "",
) -> dict[str, Any]:
    scope_label = window_label or f"last {lookback_hours:g}h"
    focus_label = focus_text.strip() or ", ".join(focus_terms)
    analysis = _empty_analysis(lookback_hours, window_label=window_label)
    analysis.update(
        {
            "incident_id": "LOG-RCA-FOCUS-NOT-FOUND",
            "summary": (
                f"No RCA candidate was selected because no parsed event in {scope_label} "
                f"matched the requested focus: {focus_label}."
            ),
            "impact": f"User focus: {focus_label}. Current logs in scope do not contain matching evidence.",
            "most_likely_root_cause": "Insufficient log evidence for the requested RCA focus.",
            "missing_data": [
                f"Logs matching focus terms: {', '.join(focus_terms)}.",
                "A wider time range or the correct affected source/service name.",
                "Metrics, topology, and change records for the impacted component.",
            ],
            "analyzed_events": len(events),
            "focus_terms": focus_terms,
        }
    )
    questions = analysis.get("rca_questions")
    if isinstance(questions, list):
        for item in questions:
            if not isinstance(item, dict):
                continue
            if item.get("id") == "incident":
                item["answer"] = analysis["summary"]
            elif item.get("id") == "most_likely_root_cause":
                item["answer"] = analysis["most_likely_root_cause"]
            elif item.get("id") == "missing_data":
                item["answer"] = analysis["missing_data"]
    return analysis


def _review_verdict(value: Any) -> str:
    verdict = str(value or "").strip().lower()
    if verdict in {"confirmed", "needs_verification", "insufficient_data", "contradicted"}:
        return verdict
    return "needs_verification"


def _merge_review_confidence(deterministic: int, llm_confidence: int, verdict: str) -> int:
    llm_confidence = max(0, min(95, llm_confidence))
    deterministic = max(0, min(95, deterministic))
    if verdict == "confirmed":
        return max(deterministic, min(llm_confidence, deterministic + 8, 95))
    if verdict == "needs_verification":
        return min(max(70, min(deterministic, llm_confidence)), 84)
    if verdict == "contradicted":
        return min(deterministic, llm_confidence, 69)
    return min(deterministic, llm_confidence, 69)


def _status_from_confidence(confidence: int, verdict: str) -> str:
    if verdict in {"insufficient_data", "contradicted"}:
        return "insufficient_data"
    return "confirmed" if confidence >= 85 else "need_verification" if confidence >= 70 else "insufficient_data"


def _review_text(value: Any, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return _short_message(value, limit)


def _review_list(value: Any, max_items: int, limit: int) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [str(item) for item in value if str(item).strip()]
    else:
        values = []
    return [_short_message(item, limit) for item in values[:max_items]]


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _refresh_question_answers_from_review(analysis: dict[str, Any]) -> None:
    questions = analysis.get("rca_questions")
    if not isinstance(questions, list):
        return
    review = analysis.get("llm_review") if isinstance(analysis.get("llm_review"), dict) else {}
    verdict = review.get("verdict", "-")
    confidence = _safe_int(analysis.get("confidence"), 0)
    status_text = "confirmed" if confidence >= 85 else "needs verification" if confidence >= 70 else "insufficient evidence"
    updates = {
        "most_likely_root_cause": f"{analysis.get('most_likely_root_cause') or '-'} RCA status: `{status_text}`. LLM review: `{verdict}`.",
        "evidence": list(analysis.get("evidence") or [])[:3],
        "confidence": f"`{confidence}%` after deterministic correlation plus LLM adjudication.",
        "missing_data": list(analysis.get("missing_data") or [])[:3],
    }
    actions = analysis.get("recommended_actions") if isinstance(analysis.get("recommended_actions"), dict) else {}
    action_items = _dedupe_text(
        list(actions.get("immediate_actions") or []) + list(actions.get("verification_actions") or [])
    )[:3]
    updates["actions"] = action_items
    for item in questions:
        if not isinstance(item, dict):
            continue
        question_id = item.get("id")
        if question_id in updates:
            item["answer"] = updates[question_id]


def _sort_events(events: list[LogEvent]) -> list[LogEvent]:
    return sorted(events, key=lambda event: (_timestamp_key(event.timestamp), event.source, event.line_number))


def _choose_anchor(events: list[LogEvent], focus_terms: list[str]) -> LogEvent | None:
    if not events:
        return None
    if focus_terms:
        return sorted(
            events,
            key=lambda event: (
                -_focus_score(event, focus_terms),
                SEVERITY_RANK.get(event.severity, 9),
                -_event_weight(event),
                _timestamp_key(event.timestamp),
            ),
        )[0]
    return sorted(
        events,
        key=lambda event: (
            SEVERITY_RANK.get(event.severity, 9),
            -_focus_score(event, focus_terms),
            -_event_weight(event),
            _timestamp_key(event.timestamp),
        ),
    )[0]


def _focus_candidate_events(
    alert_events: list[LogEvent],
    recent_events: list[LogEvent],
    focus_terms: list[str],
) -> list[LogEvent]:
    if not focus_terms:
        return alert_events or recent_events

    threshold = _focus_match_threshold(focus_terms)
    focused_alerts = [event for event in alert_events if _focus_score(event, focus_terms) >= threshold]
    if focused_alerts:
        return focused_alerts

    focused_events = [event for event in recent_events if _focus_score(event, focus_terms) >= threshold]
    return focused_events


def _related_events(anchor: LogEvent, events: list[LogEvent], focus_terms: list[str]) -> list[LogEvent]:
    related: list[LogEvent] = []
    for event in events:
        relation_score = _relation_score(event, anchor, focus_terms)
        if relation_score >= 30:
            related.append(event)
    if anchor not in related:
        related.append(anchor)
    return _sort_events(_dedupe_events(related))[-12:]


def _choose_root_candidate(anchor: LogEvent, cluster: list[LogEvent], focus_terms: list[str] | None = None) -> LogEvent:
    selected_focus_terms = focus_terms or []
    change_events = [
        event
        for event in cluster
        if _is_change_event(event) and _is_root_candidate_related(event, anchor, selected_focus_terms)
    ]
    if change_events:
        return sorted(
            change_events,
            key=lambda event: (
                -_relation_score(event, anchor, selected_focus_terms),
                _timestamp_key(event.timestamp),
                SEVERITY_RANK.get(event.severity, 9),
            ),
        )[0]
    typed = [event for event in cluster if event.event_type in ROOT_CAUSE_EVENT_TYPES]
    if typed:
        return sorted(
            typed,
            key=lambda event: (
                -_relation_score(event, anchor, selected_focus_terms),
                ROOT_CAUSE_PRIORITY.get(event.event_type, 9),
                _timestamp_key(event.timestamp),
                SEVERITY_RANK.get(event.severity, 9),
            ),
        )[0]
    return anchor


def _evidence(cluster: list[LogEvent], root_candidate: LogEvent) -> list[str]:
    evidence = [
        (
            f"Root candidate: [{root_candidate.severity.upper()}] "
            f"{root_candidate.source} {root_candidate.event_type} - {_short_message(root_candidate.message, 140)}"
        ),
    ]
    severity_counts = Counter(event.severity for event in cluster)
    event_counts = Counter(event.event_type for event in cluster)
    evidence.append(
        "Severity mix: "
        + ", ".join(f"{key}={value}" for key, value in sorted(severity_counts.items()))
    )
    evidence.append(
        "Repeated signals: "
        + ", ".join(f"{key}={value}" for key, value in event_counts.most_common(3))
    )
    for event in cluster:
        if event is root_candidate:
            continue
        if event.severity in {"critical", "error"}:
            evidence.append(f"{event.severity.upper()} after/near root: {event.source} {event.event_type}")
    return _dedupe_text(evidence)


def _confidence(
    cluster: list[LogEvent],
    root_candidate: LogEvent,
    evidence: list[str],
    focus_terms: list[str],
) -> int:
    score = 45
    score += min(len(evidence), 5) * 7
    score += min(len(cluster), 6) * 3
    if root_candidate.event_type in ROOT_CAUSE_EVENT_TYPES:
        score += 12
    if _is_change_event(root_candidate):
        score += 10
    if any(event.severity == "critical" for event in cluster):
        score += 8
    if focus_terms:
        focus_hits = sum(1 for event in cluster if _focus_score(event, focus_terms) > 0)
        if focus_hits:
            score += 8 + min(focus_hits, 3) * 4
    if len(cluster) < 2:
        score -= 15
    return max(0, min(95, score))


def _root_cause_text(root_candidate: LogEvent, anchor: LogEvent) -> str:
    if _is_change_event(root_candidate):
        return (
            f"Recent change/config event on {root_candidate.source} "
            f"({_short_message(root_candidate.message, 130)}) is the leading RCA candidate before {anchor.event_type}."
        )
    known = ROOT_CAUSE_EVENT_TYPES.get(root_candidate.event_type)
    if known:
        return f"{known} Evidence points to {root_candidate.source} / {root_candidate.event_type}."
    return f"{root_candidate.event_type} on {root_candidate.source} is the strongest RCA candidate in current logs."


def _summary(
    anchor: LogEvent,
    cause: str,
    cluster_size: int,
    lookback_hours: float,
    focus_text: str = "",
    window_label: str = "",
) -> str:
    scope = window_label or f"last {lookback_hours:g}h"
    focus = f" User impact/focus: {focus_text.strip()}." if focus_text.strip() else ""
    return (
        f"RCA analyzed {cluster_size} correlated events in {scope}. "
        f"Anchor alert is [{anchor.severity.upper()}] {anchor.domain}/{anchor.source} {anchor.event_type}. "
        f"{cause}{focus}"
    )


def _timeline_item(event: LogEvent, root_candidate: LogEvent) -> dict[str, str]:
    if event == root_candidate:
        event_type = "root_cause_candidate"
    elif _is_change_event(event):
        event_type = "change"
    elif event.severity in {"critical", "error"}:
        event_type = "impact"
    elif event.severity == "warning":
        event_type = "symptom"
    else:
        event_type = "evidence"
    return {
        "time": event.timestamp,
        "event": f"{event.event_type}: {event.message}",
        "source": f"{event.domain}/{event.source}",
        "type": event_type,
    }


def _symptoms(cluster: list[LogEvent], anchor: LogEvent) -> list[str]:
    items = [
        f"[{event.severity.upper()}] {event.source} {event.event_type}: {event.message}"
        for event in cluster
        if event.severity in {"critical", "error", "warning"}
    ]
    if not items:
        items.append(f"{anchor.source} {anchor.event_type}: {anchor.message}")
    return _dedupe_text(items)[:6]


def _impact(cluster: list[LogEvent], anchor: LogEvent) -> str:
    impacts = [event.impact for event in cluster if event.severity in {"critical", "error"} and event.impact]
    if impacts:
        return _dedupe_text(impacts)[0]
    return anchor.impact or "Impact requires verification from service owner or monitoring metrics."


def _contradicting_evidence(cluster: list[LogEvent]) -> list[str]:
    contradictions = []
    for event in cluster:
        text = event.message.lower()
        if any(term in text for term in ("normal", "recovered", "up", "success")) and event.severity == "info":
            contradictions.append(f"{event.source}: {event.message}")
    return contradictions[:3]


def _missing_data(cluster: list[LogEvent]) -> list[str]:
    missing = [
        "Metrics around the incident window for affected source(s).",
        "Recent change records from change management.",
        "Topology/dependency map for impacted service path.",
    ]
    if any(event.domain == "network" for event in cluster):
        missing.append("Interface counters, STP/LACP state, and packet loss for related network devices.")
    if any(event.domain in {"linux", "windows"} for event in cluster):
        missing.append("Process/service health and resource metrics from affected servers.")
    if any(event.domain == "vmware" for event in cluster):
        missing.append("vCenter task/event timeline and datastore/host metrics.")
    return _dedupe_text(missing)[:5]


def _verification_steps(root_candidate: LogEvent, anchor: LogEvent) -> list[str]:
    steps = [
        f"Verify current health of {anchor.source} and whether {anchor.event_type} is still active.",
        f"Inspect raw logs around {root_candidate.timestamp} for {root_candidate.source}.",
    ]
    if root_candidate.recommended_action:
        steps.append(root_candidate.recommended_action)
    steps.append("Compare with recent changes before applying disruptive remediation.")
    return _dedupe_text(steps)[:5]


def _immediate_actions(root_candidate: LogEvent, anchor: LogEvent, confidence: int) -> list[str]:
    if confidence < 70:
        return [
            "Do not run disruptive remediation yet; collect missing evidence first.",
            f"Preserve logs for {anchor.source} and related systems.",
        ]
    actions = [
        f"Prioritize investigation on {root_candidate.source} / {root_candidate.event_type}.",
        root_candidate.recommended_action,
        "Communicate potential impact to the affected service owner.",
    ]
    return _dedupe_text([action for action in actions if action])[:4]


def _prevention(root_candidate: LogEvent, anchor: LogEvent) -> list[str]:
    if root_candidate.event_type in {"switch_port_errdisable", "mac_flapping", "interface_down"}:
        return ["Standardize network change validation and enable loop/link protection where appropriate."]
    if root_candidate.event_type in {"capacity_warning", "storage_path_issue"}:
        return ["Add capacity trend forecasting and pre-threshold remediation alerts."]
    if root_candidate.event_type in {"service_failure", "application_crash"}:
        return ["Add deployment health checks and service dependency monitoring."]
    if root_candidate.event_type == "authentication_failure":
        return ["Tighten access exposure, MFA, rate limits, and brute-force detection."]
    return ["Add post-change monitoring and RCA evidence capture for this event class."]


def _rca_question_answers(
    anchor: LogEvent,
    cluster: list[LogEvent],
    root_candidate: LogEvent,
    cause: str,
    evidence: list[str],
    confidence: int,
    missing_data: list[str],
    recommended_actions: dict[str, list[str]],
    impact: str,
    focus_text: str = "",
) -> list[dict[str, Any]]:
    first_event = cluster[0] if cluster else anchor
    symptom_events = _symptom_event_summaries(cluster, root_candidate, anchor)
    consequence_events = _consequence_event_summaries(cluster, root_candidate, anchor)
    action_items = _dedupe_text(
        list(recommended_actions.get("immediate_actions") or [])
        + list(recommended_actions.get("verification_actions") or [])
    )[:3]
    status_text = "confirmed" if confidence >= 85 else "needs verification" if confidence >= 70 else "insufficient evidence"
    impact_focus = focus_text.strip() or impact

    return [
        {
            "id": "incident",
            "question": "1. Sự cố gì đang xảy ra?",
            "answer": (
                f"[{anchor.severity.upper()}] {anchor.domain}/{anchor.source} `{anchor.event_type}`. "
                f"Impact/focus: {_short_message(impact_focus, 160)}"
            ),
        },
        {
            "id": "start_time",
            "question": "2. Sự cố bắt đầu từ thời điểm nào?",
            "answer": f"Dấu hiệu đầu tiên trong log correlated xuất hiện lúc `{first_event.timestamp}`.",
        },
        {
            "id": "first_event",
            "question": "3. Event nào xảy ra đầu tiên?",
            "answer": _event_sentence(first_event),
        },
        {
            "id": "symptom_events",
            "question": "4. Event nào là triệu chứng?",
            "answer": symptom_events or ["Không thấy symptom event rõ ràng ngoài anchor alert trong log hiện tại."],
        },
        {
            "id": "consequence_events",
            "question": "5. Event nào là hậu quả?",
            "answer": consequence_events or ["Chưa thấy hậu quả downstream rõ ràng trong log hiện tại."],
        },
        {
            "id": "root_candidate_event",
            "question": "6. Event nào là root cause candidate?",
            "answer": _event_sentence(root_candidate),
        },
        {
            "id": "most_likely_root_cause",
            "question": "7. Root cause khả năng cao nhất là gì?",
            "answer": f"{cause} RCA status: `{status_text}`.",
        },
        {
            "id": "evidence",
            "question": "8. Bằng chứng là gì?",
            "answer": evidence[:3] or ["Chưa đủ bằng chứng log để kết luận."],
        },
        {
            "id": "confidence",
            "question": "9. Độ tin cậy bao nhiêu phần trăm?",
            "answer": f"`{confidence}%` dựa trên correlation, thứ tự thời gian, severity và focus match.",
        },
        {
            "id": "missing_data",
            "question": "10. Cần kiểm tra thêm dữ liệu gì?",
            "answer": (missing_data or ["Không có missing data được xác định."])[:3],
        },
        {
            "id": "actions",
            "question": "11. Nên xử lý ra sao?",
            "answer": action_items or ["Giữ nguyên hiện trạng, mở rộng log window và xác minh impact trước khi remediate."],
        },
    ]


def _empty_rca_question_answers(lookback_hours: float) -> list[dict[str, Any]]:
    return [
        {
            "id": "incident",
            "question": "1. Sự cố gì đang xảy ra?",
            "answer": f"Không có event nào trong cửa sổ {lookback_hours:g}h để xác định sự cố.",
        },
        {
            "id": "start_time",
            "question": "2. Sự cố bắt đầu từ thời điểm nào?",
            "answer": "Chưa xác định vì không có log trong cửa sổ phân tích.",
        },
        {
            "id": "first_event",
            "question": "3. Event nào xảy ra đầu tiên?",
            "answer": "Không có event.",
        },
        {
            "id": "symptom_events",
            "question": "4. Event nào là triệu chứng?",
            "answer": ["Không có symptom event."],
        },
        {
            "id": "consequence_events",
            "question": "5. Event nào là hậu quả?",
            "answer": ["Không có consequence event."],
        },
        {
            "id": "root_candidate_event",
            "question": "6. Event nào là root cause candidate?",
            "answer": "Không có root cause candidate.",
        },
        {
            "id": "most_likely_root_cause",
            "question": "7. Root cause khả năng cao nhất là gì?",
            "answer": "Chưa đủ dữ liệu log để đưa ra root cause.",
        },
        {
            "id": "evidence",
            "question": "8. Bằng chứng là gì?",
            "answer": ["Không có bằng chứng log."],
        },
        {
            "id": "confidence",
            "question": "9. Độ tin cậy bao nhiêu phần trăm?",
            "answer": "`0%`.",
        },
        {
            "id": "missing_data",
            "question": "10. Cần kiểm tra thêm dữ liệu gì?",
            "answer": ["Confirm log ingestion is active.", "Widen the RCA time window.", "Collect service and infrastructure metrics around the impact window."],
        },
        {
            "id": "actions",
            "question": "11. Nên xử lý ra sao?",
            "answer": ["Không remediate vội; bổ sung log/metrics và chạy lại RCA."],
        },
    ]


def _symptom_event_summaries(
    cluster: list[LogEvent],
    root_candidate: LogEvent,
    anchor: LogEvent,
) -> list[str]:
    symptoms = []
    for event in cluster:
        if event == root_candidate:
            continue
        if event.severity == "warning" or event.event_type in {
            "mac_flapping",
            "capacity_warning",
            "application_crash",
            "possible_syn_flood",
            "authentication_failure",
            "resource_pressure",
            "interface_down",
            "dns_timeout",
            "application_timeout",
            "vpn_tunnel_down",
            "wireless_ap_down",
            "monitoring_polling_failure",
            "monitoring_datasource_failure",
            "network_packet_loss",
            "file_integrity_change",
        }:
            symptoms.append(_event_sentence(event))
    if not symptoms and anchor != root_candidate:
        symptoms.append(_event_sentence(anchor))
    return _dedupe_text(symptoms)[:5]


def _consequence_event_summaries(
    cluster: list[LogEvent],
    root_candidate: LogEvent,
    anchor: LogEvent,
) -> list[str]:
    root_time = _timestamp_key(root_candidate.timestamp)
    consequence_types = {
        "service_failure",
        "routing_neighbor_down",
        "host_failure",
        "storage_path_issue",
        "application_timeout",
        "vm_unexpected_poweroff",
        "vm_migration_failed",
        "power_supply_failure",
        "vpn_tunnel_down",
        "wireless_ap_down",
        "wireless_gateway_failover",
        "search_cluster_red",
        "log_pipeline_blocked",
        "security_threat_detected",
    }
    consequences = []
    for event in cluster:
        if event == root_candidate:
            continue
        event_time = _timestamp_key(event.timestamp)
        if root_time and event_time and event_time < root_time:
            continue
        if event.severity == "critical" or event.event_type in consequence_types:
            consequences.append(_event_sentence(event))
    if not consequences and anchor != root_candidate:
        consequences.append(_event_sentence(anchor))
    return _dedupe_text(consequences)[:5]


def _event_sentence(event: LogEvent) -> str:
    return (
        f"`{event.timestamp}` [{event.severity.upper()}] "
        f"{event.domain}/{event.source} `{event.event_type}` - {_short_message(event.message)}"
    )


def _short_message(value: str, limit: int = 160) -> str:
    text = " ".join(str(value or "-").split())
    for pattern in (r'Message="([^"]+)"', r'msg="([^"]+)"'):
        match = re.search(pattern, text)
        if match:
            text = match.group(1)
            break
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _relation_score(event: LogEvent, anchor: LogEvent, focus_terms: list[str]) -> int:
    if event == anchor:
        return 100

    score = 0
    if event.source == anchor.source:
        score += 12 if focus_terms else 38
        if focus_terms and _is_change_event(event):
            score += 20
    if _shares_signal(event, anchor):
        score += 34

    focus_hits = _focus_score(event, focus_terms)
    if focus_hits >= _focus_match_threshold(focus_terms):
        score += 28 + min(focus_hits, 4) * 4
        if event.domain == anchor.domain:
            score += 6

    if not focus_terms:
        if event.domain == anchor.domain and event.severity in {"critical", "error", "warning"}:
            score += 10
        if event.domain == anchor.domain and _is_change_event(event):
            score += 8

    return score


def _is_root_candidate_related(event: LogEvent, anchor: LogEvent, focus_terms: list[str]) -> bool:
    return event == anchor or _relation_score(event, anchor, focus_terms) >= 30


def _shares_signal(event: LogEvent, anchor: LogEvent) -> bool:
    if event.event_type == anchor.event_type:
        return True
    if _event_signals(event) & _event_signals(anchor):
        return True
    pair = {event.event_type, anchor.event_type}
    strong_related_pairs = (
        {"switch_port_errdisable", "mac_flapping"},
        {"interface_down", "routing_neighbor_down"},
        {"capacity_warning", "storage_path_issue"},
        {"search_cluster_red", "log_pipeline_blocked"},
        {"wireless_ap_down", "wireless_gateway_failover"},
        {"possible_syn_flood", "resource_pressure"},
    )
    if any(pair <= related for related in strong_related_pairs):
        return True
    same_source_required_pairs = (
        {"service_failure", "application_crash"},
        {"monitoring_polling_failure", "monitoring_datasource_failure"},
        {"vpn_tunnel_down", "network_packet_loss"},
        {"authentication_failure", "security_threat_detected", "file_integrity_change"},
    )
    return event.source == anchor.source and any(pair <= related for related in same_source_required_pairs)


def _event_signals(event: LogEvent) -> set[str]:
    text = " ".join([event.source, event.event_type, event.message, event.raw]).lower()
    signals: set[str] = set()
    for pattern in SIGNAL_PATTERNS:
        for match in pattern.finditer(text):
            signals.add(_normalize_signal(match.group(0)))
    source_signal = _normalize_signal(event.source)
    return {signal for signal in signals if signal and signal != source_signal}


def _normalize_signal(value: str) -> str:
    signal = value.strip().lower()
    if signal.startswith("policy"):
        digits = re.sub(r"\D+", "", signal)
        return f"policy:{digits}" if digits else signal
    if signal.startswith("vlan"):
        digits = re.sub(r"\D+", "", signal)
        return f"vlan:{digits}" if digits else signal
    return (
        signal.replace("gigabitethernet", "gi")
        .replace("tengigabitethernet", "te")
        .replace("fastethernet", "fa")
        .replace(" ", "")
    )


def _is_change_event(event: LogEvent) -> bool:
    text = " ".join([event.event_type, event.message, event.raw]).lower()
    return any(pattern.search(text) for pattern in CHANGE_PATTERNS)


def _focus_terms(value: str) -> list[str]:
    normalized = value.lower()
    normalized = re.sub(r"[^a-z0-9_.-]+", " ", normalized)
    stopwords = {
        "rca",
        "root",
        "cause",
        "phan",
        "tich",
        "su",
        "co",
        "log",
        "logs",
        "trong",
        "last",
        "hours",
        "hour",
        "gio",
        "phut",
        "minutes",
        "minute",
        "qua",
        "gan",
        "nhat",
        "hien",
        "tai",
        "kiem",
        "tra",
        "check",
        "diagnose",
        "unknown",
        "outage",
        "issue",
        "problem",
        "incident",
    }
    terms = []
    for token in normalized.split():
        canonical = FOCUS_ALIASES.get(token, token)
        if len(canonical) < 3 or canonical in stopwords or canonical.isdigit():
            continue
        terms.append(canonical)
        if canonical != token and len(token) >= 3 and token not in stopwords and not token.isdigit():
            terms.append(token)
    return _dedupe_text(terms)[:10]


def _focus_score(event: LogEvent, focus_terms: list[str]) -> int:
    if not focus_terms:
        return 0
    text = " ".join(
        [
            event.domain,
            event.source,
            event.severity,
            event.event_type,
            event.message,
            event.probable_cause,
            event.impact,
            event.recommended_action,
        ]
    ).lower()
    word_text = re.sub(r"[^a-z0-9_.-]+", " ", text)
    return sum(1 for term in focus_terms if _focus_term_matches(term, text, word_text))


def _focus_match_threshold(focus_terms: list[str]) -> int:
    return 2 if len(focus_terms) >= 2 else 1


def _focus_term_matches(term: str, text: str, word_text: str) -> bool:
    candidates = {term, FOCUS_ALIASES.get(term, term)}
    for candidate in candidates:
        if candidate in text:
            return True
        if candidate.replace("_", " ") in word_text:
            return True
        if candidate.endswith("ing") and candidate[:-3] in text:
            return True
    return False


def _event_weight(event: LogEvent) -> int:
    weight = 0
    if event.event_type in ROOT_CAUSE_EVENT_TYPES:
        weight += 10
    if _is_change_event(event):
        weight += 8
    if event.severity == "critical":
        weight += 5
    return weight


def _incident_id(anchor: LogEvent) -> str:
    stamp = "".join(char for char in anchor.timestamp if char.isdigit())[:12] or "UNKNOWN"
    return f"LOG-RCA-{stamp}-{anchor.source.replace('.', '-').upper()}"


def _event_summary(event: LogEvent) -> dict[str, str]:
    return {
        "timestamp": event.timestamp,
        "domain": event.domain,
        "source": event.source,
        "severity": event.severity,
        "event_type": event.event_type,
        "message": event.message,
    }


def _timestamp_key(value: str) -> str:
    if not value or value == "unknown":
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value


def _dedupe_events(events: list[LogEvent]) -> list[LogEvent]:
    seen = set()
    result = []
    for event in events:
        key = (event.source_file, event.line_number, event.raw)
        if key in seen:
            continue
        seen.add(key)
        result.append(event)
    return result


def _dedupe_text(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
