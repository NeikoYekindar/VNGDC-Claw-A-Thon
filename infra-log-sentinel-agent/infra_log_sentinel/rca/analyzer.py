from __future__ import annotations

from datetime import datetime
from typing import Any

from infra_log_sentinel.rca.synthetic import SCENARIOS


GENERIC_MISSING_DATA = (
    "Packet capture or flow sample for the incident window.",
    "Device configuration diff around the change time.",
    "Owner confirmation for whether the recent change was expected.",
)


def analyze_incident(incident: dict[str, Any]) -> dict[str, Any]:
    scenario_key, spec = _select_rule(incident)
    timeline = _build_timeline(incident, spec)
    supporting = _supporting_evidence(incident, spec)
    contradicting = _contradicting_evidence(incident, spec)
    confidence = _confidence(incident, supporting, contradicting)
    status = _status_for(confidence)
    missing_data = _missing_data(incident)
    hypothesis = spec["root_cause"] if spec else _generic_hypothesis(incident)

    return {
        "incident_id": str(incident.get("incident_id") or "RCA-UNKNOWN"),
        "severity": _alert_value(incident, "severity", default="warning"),
        "summary": _summary(incident, hypothesis, confidence),
        "timeline": timeline,
        "symptoms": _symptoms(incident, spec),
        "impact": str(incident.get("impact") or (spec or {}).get("impact") or "Impact requires verification."),
        "root_cause_hypotheses": [
            {
                "hypothesis": hypothesis,
                "confidence": confidence,
                "supporting_evidence": supporting,
                "contradicting_evidence": contradicting,
                "missing_data": missing_data,
                "verification_steps": list((spec or {}).get("verification", GENERIC_MISSING_DATA)),
            }
        ],
        "most_likely_root_cause": hypothesis if confidence >= 70 else "Insufficient evidence for a confirmed root cause.",
        "confidence": confidence,
        "evidence": supporting[:6],
        "recommended_actions": {
            "immediate_actions": _immediate_actions(spec, confidence),
            "verification_actions": list((spec or {}).get("verification", GENERIC_MISSING_DATA)),
            "long_term_prevention": _long_term_prevention(scenario_key),
        },
        "missing_data": missing_data,
        "status": status,
    }


def _select_rule(incident: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    scenario = str(incident.get("scenario") or "").strip().lower()
    if scenario in SCENARIOS:
        return scenario, SCENARIOS[scenario]

    text = _incident_text(incident)
    best_key = ""
    best_score = 0
    for key, spec in SCENARIOS.items():
        score = sum(1 for keyword in spec["keywords"] if keyword.lower() in text)
        if score > best_score:
            best_key = key
            best_score = score
    if best_key:
        return best_key, SCENARIOS[best_key]
    return "generic", None


def _build_timeline(incident: dict[str, Any], spec: dict[str, Any] | None) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for change in _list(incident.get("recent_changes")):
        items.append(
            {
                "time": str(change.get("time") or ""),
                "event": str(change.get("summary") or change.get("message") or "Recent change recorded."),
                "source": str(change.get("source") or "change"),
                "type": "change",
            }
        )
    for log in _list(incident.get("logs")):
        message = str(log.get("message") or "")
        items.append(
            {
                "time": str(log.get("time") or ""),
                "event": message,
                "source": str(log.get("source") or log.get("system") or "log"),
                "type": _timeline_type(message, spec),
            }
        )
    for metric in _list(incident.get("metrics")):
        name = str(metric.get("name") or "metric")
        value = metric.get("value", "")
        baseline = metric.get("baseline", "")
        unit = str(metric.get("unit") or "")
        items.append(
            {
                "time": str(metric.get("time") or ""),
                "event": f"{name}={value}{unit} baseline={baseline}{unit}",
                "source": str(metric.get("source") or "metric"),
                "type": "evidence" if str(metric.get("status") or "").lower() == "abnormal" else "symptom",
            }
        )
    alert = incident.get("alert") if isinstance(incident.get("alert"), dict) else {}
    if alert:
        items.append(
            {
                "time": str(alert.get("time") or ""),
                "event": str(alert.get("message") or "Primary alert."),
                "source": str(alert.get("source") or "alert"),
                "type": "impact",
            }
        )
    return sorted(items, key=lambda item: _sort_key(item["time"]))[:20]


def _timeline_type(message: str, spec: dict[str, Any] | None) -> str:
    lowered = message.lower()
    if spec and any(keyword.lower() in lowered for keyword in spec["keywords"]):
        return "root_cause_candidate"
    if any(term in lowered for term in ("timeout", "failed", "high", "full", "loss", "unreachable")):
        return "symptom"
    return "evidence"


def _supporting_evidence(incident: dict[str, Any], spec: dict[str, Any] | None) -> list[str]:
    if not spec:
        return _generic_evidence(incident)

    evidence: list[str] = []
    keywords = tuple(keyword.lower() for keyword in spec["keywords"])
    for change in _list(incident.get("recent_changes")):
        summary = str(change.get("summary") or change.get("message") or "")
        if summary:
            evidence.append(f"Recent change before alert: {summary}")
    for log in _list(incident.get("logs")):
        message = str(log.get("message") or "")
        if any(keyword in message.lower() for keyword in keywords):
            evidence.append(f"{log.get('source', 'log')}: {message}")
    for metric in _list(incident.get("metrics")):
        if str(metric.get("status") or "").lower() == "abnormal":
            evidence.append(
                f"{metric.get('source', 'metric')} {metric.get('name', 'metric')} "
                f"was {metric.get('value')} vs baseline {metric.get('baseline')} {metric.get('unit', '')}".strip()
            )
    return _dedupe(evidence)


def _contradicting_evidence(incident: dict[str, Any], spec: dict[str, Any] | None) -> list[str]:
    contradictions: list[str] = []
    for log in _list(incident.get("logs")):
        message = str(log.get("message") or "")
        lowered = message.lower()
        if any(term in lowered for term in ("no interface errors", "no deny log", "normal")):
            contradictions.append(f"{log.get('source', 'log')}: {message}")
    if not contradictions and spec:
        return []
    return contradictions


def _confidence(
    incident: dict[str, Any],
    supporting: list[str],
    contradicting: list[str],
) -> int:
    score = 45
    score += min(len(supporting), 5) * 10
    if _list(incident.get("recent_changes")):
        score += 10
    if incident.get("topology"):
        score += 5
    score -= min(len(contradicting), 3) * 8
    return max(0, min(95, score))


def _status_for(confidence: int) -> str:
    if confidence < 70:
        return "insufficient_data"
    if confidence >= 85:
        return "confirmed"
    return "need_verification"


def _missing_data(incident: dict[str, Any]) -> list[str]:
    missing = []
    if not _list(incident.get("metrics")):
        missing.append("Metrics for the affected source during the incident window.")
    if not _list(incident.get("logs")):
        missing.append("Raw logs around the alert time.")
    if not incident.get("topology"):
        missing.append("Topology relationships for affected devices and services.")
    if not _list(incident.get("recent_changes")):
        missing.append("Recent change history before the alert.")
    missing.extend(GENERIC_MISSING_DATA[:1])
    return _dedupe(missing)


def _symptoms(incident: dict[str, Any], spec: dict[str, Any] | None) -> list[str]:
    symptoms = []
    alert_message = _alert_value(incident, "message", default="")
    if alert_message:
        symptoms.append(alert_message)
    for metric in _list(incident.get("metrics")):
        if str(metric.get("status") or "").lower() == "abnormal":
            symptoms.append(
                f"{metric.get('name', 'metric')} deviated from baseline on {metric.get('source', 'unknown')}"
            )
    if not symptoms and spec:
        symptoms.append(spec["alert_message"])
    return _dedupe(symptoms)[:6]


def _summary(incident: dict[str, Any], hypothesis: str, confidence: int) -> str:
    alert = _alert_value(incident, "message", default="Incident alert received.")
    return f"{alert} Most likely RCA candidate: {hypothesis} Confidence {confidence}%."


def _immediate_actions(spec: dict[str, Any] | None, confidence: int) -> list[str]:
    if not spec:
        return ["Collect missing data before remediation.", "Keep changes reversible until RCA is verified."]
    actions = list(spec.get("actions", ()))
    if confidence < 70:
        return ["Do not perform disruptive remediation yet.", *list(spec.get("verification", ()))[:2]]
    return actions[:3]


def _long_term_prevention(scenario_key: str) -> list[str]:
    if scenario_key in {"broadcast_loop", "mac_flapping"}:
        return ["Enforce access-port loop protection and standard LACP/STP templates."]
    if scenario_key == "brute_force_wazuh":
        return ["Restrict administrative exposure and require MFA/key-based access."]
    if scenario_key in {"linux_disk_full", "vmware_datastore_full"}:
        return ["Add capacity forecasting and alert before critical storage thresholds."]
    if scenario_key == "routing_issue":
        return ["Require route-policy diff validation before network changes."]
    return ["Add pre-change validation and post-change monitoring for this failure mode."]


def _generic_hypothesis(incident: dict[str, Any]) -> str:
    if _list(incident.get("recent_changes")):
        return "Recent change is a root cause candidate, but more evidence is required."
    return "No high-confidence root cause candidate found from the provided data."


def _generic_evidence(incident: dict[str, Any]) -> list[str]:
    evidence = []
    for log in _list(incident.get("logs"))[:3]:
        evidence.append(f"{log.get('source', 'log')}: {log.get('message', '')}")
    for metric in _list(incident.get("metrics"))[:3]:
        evidence.append(f"{metric.get('source', 'metric')} {metric.get('name', 'metric')}={metric.get('value')}")
    return [item for item in evidence if item.strip()]


def _incident_text(incident: dict[str, Any]) -> str:
    parts = [str(incident.get("incident_id") or ""), str(incident.get("scenario") or "")]
    alert = incident.get("alert") if isinstance(incident.get("alert"), dict) else {}
    parts.extend(str(value) for value in alert.values())
    for collection_name in ("logs", "metrics", "recent_changes"):
        for item in _list(incident.get(collection_name)):
            parts.extend(str(value) for value in item.values())
    return " ".join(parts).lower()


def _alert_value(incident: dict[str, Any], key: str, default: str) -> str:
    alert = incident.get("alert") if isinstance(incident.get("alert"), dict) else {}
    return str(alert.get(key) or default)


def _list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _sort_key(value: str) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = value.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result
