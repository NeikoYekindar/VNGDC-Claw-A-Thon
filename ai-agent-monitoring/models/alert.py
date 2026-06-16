"""Alert payload schema — normalized from any monitoring source."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Environment(str, Enum):
    PROD = "prod"
    STAGING = "staging"
    DEV = "dev"
    UNKNOWN = "unknown"


class Alert(BaseModel):
    alert_id: str
    alert_name: str
    severity: Severity = Severity.WARNING
    instance: str = ""
    service: str = ""
    environment: Environment = Environment.UNKNOWN
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    description: str = ""
    labels: dict[str, Any] = {}
    annotations: dict[str, Any] = {}
    metrics_url: Optional[str] = None

    @classmethod
    def from_raw(cls, data: dict) -> "Alert":
        """Normalize raw alert payload to Alert schema."""
        import uuid
        normalized = dict(data)
        if "alert_id" not in normalized:
            normalized["alert_id"] = str(uuid.uuid4())
        return cls(**normalized)

    @classmethod
    def from_alertmanager(cls, am_alert: dict) -> "Alert":
        """
        Normalize a single alert from Alertmanager webhook payload.

        Alertmanager format:
        {
          "status": "firing",
          "labels": {"alertname": "HighCPU", "instance": "10.0.0.5:9100", "severity": "warning"},
          "annotations": {"summary": "...", "description": "..."},
          "startsAt": "2026-06-13T06:00:00Z"
        }
        """
        import uuid
        labels = am_alert.get("labels", {})
        annotations = am_alert.get("annotations", {})

        alert_name = labels.get("alertname", "UnknownAlert")
        # Strip port from instance (e.g. "10.0.0.5:9100" → "10.0.0.5")
        instance = labels.get("instance", "").split(":")[0]
        severity_raw = labels.get("severity", "warning").lower()
        env_raw = labels.get("env", labels.get("environment", "unknown")).lower()

        severity_map = {"critical": Severity.CRITICAL, "warning": Severity.WARNING, "info": Severity.INFO}
        env_map = {"prod": Environment.PROD, "production": Environment.PROD,
                   "staging": Environment.STAGING, "dev": Environment.DEV}

        description = annotations.get("description") or annotations.get("summary") or alert_name

        # Parse timestamp
        starts_at = am_alert.get("startsAt", "")
        try:
            ts = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
        except Exception:
            ts = datetime.utcnow()

        return cls(
            alert_id=str(uuid.uuid4()),
            alert_name=alert_name,
            severity=severity_map.get(severity_raw, Severity.WARNING),
            instance=instance,
            service=labels.get("job", labels.get("service", "")),
            environment=env_map.get(env_raw, Environment.UNKNOWN),
            timestamp=ts,
            description=description,
            labels=labels,
            annotations=annotations,
        )
