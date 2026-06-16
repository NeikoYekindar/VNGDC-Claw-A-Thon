"""
Telegram reporter — sends RCA report via Telegram Bot API.
Uses sendMessage with MarkdownV2 parse mode.
Retries on failure, deduplicates per batch.
"""

import os
import time
from typing import Optional
import httpx

from utils.logger import log_report_sent

_MAX_TG_MSG_LEN = 4096  # Telegram hard limit per message
_MAX_TG_BODY_LEN = 3900  # leave room for part headers and avoid boundary issues


def escape_html(text: str) -> str:
    """Escape data values for Telegram HTML mode."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class TelegramReporter:
    def __init__(self):
        self._token: Optional[str] = None
        self._chat_id: Optional[str] = None
        self._sent_batches: set[str] = set()

    @property
    def token(self) -> str:
        if not self._token:
            self._token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        return self._token

    @property
    def chat_id(self) -> str:
        if not self._chat_id:
            self._chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
        return self._chat_id

    def send(self, markdown: str, batch_id: str = "", retries: int = 3) -> bool:
        """Send report to Telegram. Returns True on success."""
        if batch_id and batch_id in self._sent_batches:
            return True

        if not self.token or not self.chat_id:
            log_report_sent(batch_id, False, "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
            return False

        # Split into chunks if over 4096 chars
        chunks = self._split(markdown)
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"

        for i, chunk in enumerate(chunks):
            success = self._send_chunk(url, chunk, batch_id, retries, part=i + 1, total=len(chunks))
            if not success:
                return False

        if batch_id:
            self._sent_batches.add(batch_id)
        log_report_sent(batch_id, True)
        return True

    def _send_chunk(self, url: str, text: str, batch_id: str, retries: int,
                    part: int = 1, total: int = 1) -> bool:
        header = f"<b>[{part}/{total}]</b>\n" if total > 1 else ""
        payload = {
            "chat_id": self.chat_id,
            "text": header + text,
            "parse_mode": "HTML",
        }

        for attempt in range(1, retries + 1):
            try:
                resp = httpx.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    return True
                # If MarkdownV2 parse fails, retry as plain text
                if resp.status_code == 400 and "parse" in resp.text.lower():
                    plain = {"chat_id": self.chat_id, "text": (header + text)[:_MAX_TG_MSG_LEN]}
                    resp2 = httpx.post(url, json=plain, timeout=10)
                    return resp2.status_code == 200
                if attempt < retries:
                    time.sleep(2 ** attempt)
            except Exception as exc:  # noqa: BLE001
                if attempt < retries:
                    time.sleep(2 ** attempt)
                else:
                    log_report_sent(batch_id, False, str(exc))
                    return False

        return False

    @staticmethod
    def _split(text: str) -> list[str]:
        """Split text into chunks ≤ 4096 chars, breaking at newlines."""
        if len(text) <= _MAX_TG_BODY_LEN:
            return [text]
        chunks = []
        while text:
            if len(text) <= _MAX_TG_BODY_LEN:
                chunks.append(text)
                break
            split_at = text.rfind("\n", 0, _MAX_TG_BODY_LEN)
            if split_at == -1:
                split_at = _MAX_TG_BODY_LEN
            chunks.append(text[:split_at])
            text = text[split_at:].lstrip("\n")
        return chunks
