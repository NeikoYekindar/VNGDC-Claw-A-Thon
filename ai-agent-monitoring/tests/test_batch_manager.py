"""Unit tests for BatchManager."""

import time
import pytest
from models.alert import Alert, Severity, Environment
from models.batch import BatchStatus
from batching.batch_manager import BatchManager


def make_alert(alert_id: str, instance: str = "app-01", service: str = "payment-api") -> Alert:
    return Alert(
        alert_id=alert_id,
        alert_name="HighCPUUsage",
        severity=Severity.WARNING,
        instance=instance,
        service=service,
        environment=Environment.PROD,
        description="CPU high",
    )


def test_alert_creates_batch():
    bm = BatchManager()
    alert = make_alert("a-001")
    batch_id = bm.receive_alert(alert)
    batch = bm.get_batch(batch_id)
    assert batch is not None
    assert len(batch.alerts) == 1
    assert batch.status == BatchStatus.PENDING
    bm.shutdown()


def test_related_alerts_grouped_into_same_batch():
    bm = BatchManager()
    a1 = make_alert("a-001", instance="app-01")
    a2 = make_alert("a-002", instance="app-01")  # same instance → same batch
    id1 = bm.receive_alert(a1)
    id2 = bm.receive_alert(a2)
    assert id1 == id2
    batch = bm.get_batch(id1)
    assert len(batch.alerts) == 2
    bm.shutdown()


def test_unrelated_alerts_go_to_different_batches():
    bm = BatchManager()
    a1 = make_alert("a-001", instance="app-01", service="payment-api")
    a2 = make_alert("a-002", instance="db-01", service="mysql")
    id1 = bm.receive_alert(a1)
    id2 = bm.receive_alert(a2)
    assert id1 != id2
    bm.shutdown()


def test_batch_fires_handler_after_window(monkeypatch):
    fired = []

    def handler(batch):
        fired.append(batch.batch_id)

    # Use 1-second window for fast testing
    monkeypatch.setattr("config.config.agent.batch_window_minutes", 1 / 60)

    bm = BatchManager(on_batch_ready=handler)
    # Override window to 1 second
    bm._window_minutes = 1 / 60

    alert = make_alert("a-001")
    batch_id = bm.receive_alert(alert)
    # Manually call fire to simulate window expiry
    bm._fire_batch(batch_id)
    assert batch_id in fired
    bm.shutdown()
