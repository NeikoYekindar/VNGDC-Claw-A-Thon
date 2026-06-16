from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RawLogLine:
    domain: str
    source_file: Path
    line_number: int
    text: str


@dataclass(frozen=True)
class LogEvent:
    timestamp: str
    domain: str
    source: str
    severity: str
    event_type: str
    message: str
    raw: str
    source_file: Path
    line_number: int
    probable_cause: str
    impact: str
    recommended_action: str
