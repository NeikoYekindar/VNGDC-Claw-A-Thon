from __future__ import annotations

import re

from infra_log_sentinel.analysis.rule_analyzer import (
    classify_severity,
    detect_event_type,
    explain_event,
)
from infra_log_sentinel.models import LogEvent, RawLogLine


ISO_LINE_RE = re.compile(r"^(?P<timestamp>\S+)\s+(?P<source>\S+)\s+(?P<message>.+)$")
LINUX_SYSLOG_RE = re.compile(
    r"^(?P<timestamp>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<source>\S+)\s+(?P<message>.+)$"
)


def parse_raw_line(raw: RawLogLine) -> LogEvent:
    timestamp, source, message = _split_line(raw)
    severity = classify_severity(raw.text, raw.domain)
    event_type = detect_event_type(raw.text, raw.domain)
    probable_cause, impact, recommended_action = explain_event(event_type, severity, source)

    return LogEvent(
        timestamp=timestamp,
        domain=raw.domain,
        source=source,
        severity=severity,
        event_type=event_type,
        message=message,
        raw=raw.text,
        source_file=raw.source_file,
        line_number=raw.line_number,
        probable_cause=probable_cause,
        impact=impact,
        recommended_action=recommended_action,
    )


def parse_raw_lines(raw_lines: list[RawLogLine]) -> list[LogEvent]:
    return [parse_raw_line(raw) for raw in raw_lines]


def _split_line(raw: RawLogLine) -> tuple[str, str, str]:
    if raw.domain in {"linux", "syslog"}:
        match = LINUX_SYSLOG_RE.match(raw.text)
    else:
        match = ISO_LINE_RE.match(raw.text)

    if not match:
        return "unknown", raw.source_file.stem, raw.text

    return (
        match.group("timestamp"),
        match.group("source"),
        match.group("message"),
    )
