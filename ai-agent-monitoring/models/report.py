"""Report model — structured output for each processed batch."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class InvestigationStatus(str, Enum):
    INVESTIGATED = "investigated"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    FAILED = "failed"


class Relevance(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Impact(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFORMATIONAL = "informational"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendedFix(BaseModel):
    immediate: list[str] = []
    long_term: list[str] = []
    need_human_approval: list[str] = []


class BatchReport(BaseModel):
    batch_id: str
    status: InvestigationStatus = InvestigationStatus.INVESTIGATED
    alerts: list[dict] = []
    summary: str = ""
    relevance: Relevance = Relevance.MEDIUM
    impact: Impact = Impact.MINOR
    relevance_reason: str = ""
    investigation_steps: list[dict] = []
    evidence: list[str] = []
    root_cause: str = ""
    confidence: Confidence = Confidence.MEDIUM
    recommended_fix: RecommendedFix = RecommendedFix()
    teams_report_sent: bool = False
    error: Optional[str] = None
