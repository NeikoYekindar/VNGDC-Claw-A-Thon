"""
Batch Manager — groups related alerts within a 10-minute window
using APScheduler before triggering analysis.
"""

import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from config import config
from models.alert import Alert
from models.batch import AlertBatch, BatchStatus
from utils.logger import log_alert_received, log_batch_created, log_batch_processing


class BatchManager:
    """
    In-memory batch manager with APScheduler-based window timer.

    Flow:
      1. alert arrives → find or create a batch
      2. on first alert → schedule a job to fire after batch_window_minutes
      3. on fire → mark batch PROCESSING and call the registered handler
    """

    def __init__(self, on_batch_ready: Optional[Callable[[AlertBatch], None]] = None):
        self._batches: dict[str, AlertBatch] = {}
        self._lock = threading.Lock()
        self._on_batch_ready = on_batch_ready
        self._window_minutes = config.agent.batch_window_minutes
        self._max_per_batch = config.agent.max_alerts_per_batch

        self._scheduler = BackgroundScheduler(daemon=True)
        self._scheduler.start()

    def register_handler(self, handler: Callable[[AlertBatch], None]) -> None:
        self._on_batch_ready = handler

    def receive_alert(self, alert: Alert) -> str:
        """Accept an alert, assign to a batch, return batch_id."""
        log_alert_received(alert.alert_id, alert.alert_name, alert.instance)

        with self._lock:
            batch = self._find_batch_for(alert)
            if batch is None:
                batch = self._create_batch(alert)
            elif len(batch.alerts) < self._max_per_batch:
                batch.add_alert(alert)
            else:
                # Batch is full — start a new one
                batch = self._create_batch(alert)

        return batch.batch_id

    def get_batch(self, batch_id: str) -> Optional[AlertBatch]:
        return self._batches.get(batch_id)

    def list_batches(self) -> list[AlertBatch]:
        return list(self._batches.values())

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_batch_for(self, alert: Alert) -> Optional[AlertBatch]:
        for batch in self._batches.values():
            if batch.status == BatchStatus.PENDING and batch.is_related(alert):
                return batch
        return None

    def _create_batch(self, alert: Alert) -> AlertBatch:
        batch = AlertBatch(
            window_closes_at=datetime.utcnow() + timedelta(minutes=self._window_minutes),
        )
        batch.add_alert(alert)
        self._batches[batch.batch_id] = batch

        log_batch_created(batch.batch_id, [a.alert_id for a in batch.alerts])

        # Schedule the window-close job
        self._scheduler.add_job(
            func=self._fire_batch,
            trigger="date",
            run_date=batch.window_closes_at,
            args=[batch.batch_id],
            id=f"batch_{batch.batch_id}",
            replace_existing=True,
        )
        return batch

    def _fire_batch(self, batch_id: str) -> None:
        with self._lock:
            batch = self._batches.get(batch_id)
            if batch is None or batch.status != BatchStatus.PENDING:
                return
            batch.status = BatchStatus.PROCESSING

        log_batch_processing(batch_id, len(batch.alerts))

        if self._on_batch_ready:
            try:
                self._on_batch_ready(batch)
            except Exception as exc:  # noqa: BLE001
                batch.status = BatchStatus.FAILED
                from utils.logger import log_error
                log_error(batch_id, str(exc))
