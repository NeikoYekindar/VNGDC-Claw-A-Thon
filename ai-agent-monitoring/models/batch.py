"""Batch model — groups related alerts within a 10-minute window."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

from models.alert import Alert


class BatchStatus(str, Enum):
    PENDING = "pending"       # waiting for batch window to close
    PROCESSING = "processing" # being analyzed
    DONE = "done"             # report sent
    FAILED = "failed"         # processing failed


class AlertBatch(BaseModel):
    batch_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: BatchStatus = BatchStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    window_closes_at: Optional[datetime] = None
    alerts: list[Alert] = []

    def add_alert(self, alert: Alert) -> None:
        self.alerts.append(alert)

    def is_related(self, alert: Alert) -> bool:
        """Check if an alert belongs to this batch (grouping rules)."""
        if not self.alerts:
            return False
        for existing in self.alerts:
            if (
                alert.instance and alert.instance == existing.instance
                or alert.service and alert.service == existing.service
                or alert.labels.get("cluster") and alert.labels.get("cluster") == existing.labels.get("cluster")
                or alert.labels.get("fingerprint") and alert.labels.get("fingerprint") == existing.labels.get("fingerprint")
            ):
                return True
        return False
