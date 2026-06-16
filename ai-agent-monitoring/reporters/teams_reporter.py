"""
Microsoft Teams reporter — sends formatted report via incoming webhook.
Retries on failure, never sends duplicate reports for the same batch.
"""

import os
import time
from typing import Optional

import httpx

from config import config
from utils.logger import log_report_sent

_MAX_TEAMS_MESSAGE_LEN = 28000  # Teams message limit


class TeamsReporter:
    def __init__(self):
        self._webhook_url: Optional[str] = None
        self._sent_batches: set[str] = set()

    @property
    def webhook_url(self) -> str:
        if not self._webhook_url:
            env_key = config.teams.webhook_url_env
            self._webhook_url = os.environ.get(env_key, "")
        return self._webhook_url

    def send(self, markdown: str, batch_id: str = "", retries: int = 3) -> bool:
        """Send report to Teams. Returns True on success."""
        if batch_id and batch_id in self._sent_batches:
            return True  # already sent, skip

        if not self.webhook_url:
            log_report_sent(batch_id, False, "TEAMS_WEBHOOK_URL not set")
            return False

        # Truncate if too long
        if len(markdown) > _MAX_TEAMS_MESSAGE_LEN:
            markdown = markdown[:_MAX_TEAMS_MESSAGE_LEN] + "\n\n*[Report truncated]*"

        payload = {"text": markdown}

        for attempt in range(1, retries + 1):
            try:
                resp = httpx.post(self.webhook_url, json=payload, timeout=10)
                if resp.status_code == 200:
                    if batch_id:
                        self._sent_batches.add(batch_id)
                    log_report_sent(batch_id, True)
                    return True
                else:
                    if attempt < retries:
                        time.sleep(2 ** attempt)
            except Exception as exc:  # noqa: BLE001
                if attempt < retries:
                    time.sleep(2 ** attempt)
                else:
                    log_report_sent(batch_id, False, str(exc))
                    return False

        log_report_sent(batch_id, False, "All retries exhausted")
        return False
