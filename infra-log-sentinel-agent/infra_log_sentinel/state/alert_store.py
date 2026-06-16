from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import sqlite3

from infra_log_sentinel.models import LogEvent


TELEGRAM_LEGACY_CURSOR_KEY = "telegram_last_update_id"
TELEGRAM_CHAT_CURSOR_KEY = "telegram_chat_last_update_id"
TELEGRAM_ACK_CURSOR_KEY = "telegram_ack_last_update_id"


@dataclass(frozen=True)
class AlertRecord:
    alert_id: str
    severity: str
    domain: str
    source: str
    event_type: str
    timestamp: str
    message: str
    probable_cause: str
    impact: str
    recommended_action: str
    telegram_message_id: int | None
    sent_at_ts: int
    due_at_ts: int


class AlertStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def upsert_pending_alert(
        self,
        event: LogEvent,
        telegram_message_id: int | None,
        sent_at_ts: int,
        due_at_ts: int,
    ) -> str:
        alert_id = build_alert_id(event)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO alerts (
                    alert_id, severity, domain, source, event_type, timestamp,
                    message, probable_cause, impact, recommended_action,
                    telegram_message_id, sent_at_ts, due_at_ts, status,
                    ack_text, acked_at_ts, escalated_at_ts, escalation_message_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', NULL, NULL, NULL, NULL)
                ON CONFLICT(alert_id) DO UPDATE SET
                    severity = excluded.severity,
                    domain = excluded.domain,
                    source = excluded.source,
                    event_type = excluded.event_type,
                    timestamp = excluded.timestamp,
                    message = excluded.message,
                    probable_cause = excluded.probable_cause,
                    impact = excluded.impact,
                    recommended_action = excluded.recommended_action,
                    telegram_message_id = excluded.telegram_message_id,
                    sent_at_ts = excluded.sent_at_ts,
                    due_at_ts = excluded.due_at_ts,
                    status = 'pending',
                    ack_text = NULL,
                    acked_at_ts = NULL,
                    escalated_at_ts = NULL,
                    escalation_message_id = NULL
                """,
                (
                    alert_id,
                    event.severity,
                    event.domain,
                    event.source,
                    event.event_type,
                    event.timestamp,
                    event.message,
                    event.probable_cause,
                    event.impact,
                    event.recommended_action,
                    telegram_message_id,
                    sent_at_ts,
                    due_at_ts,
                ),
            )
        return alert_id

    def list_pending_alerts(self) -> list[AlertRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT alert_id, severity, domain, source, event_type, timestamp,
                       message, probable_cause, impact, recommended_action,
                       telegram_message_id, sent_at_ts, due_at_ts
                FROM alerts
                WHERE status = 'pending'
                ORDER BY due_at_ts ASC, severity ASC, alert_id ASC
                """
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def get_alert_status(self, alert_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM alerts WHERE alert_id = ?",
                (alert_id,),
            ).fetchone()
        return None if row is None else str(row["status"])

    def status_counts(self, since_ts: int | None = None) -> dict[str, int]:
        with self._connect() as connection:
            if since_ts is None:
                rows = connection.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM alerts
                    GROUP BY status
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM alerts
                    WHERE sent_at_ts >= ?
                    GROUP BY status
                    """,
                    (since_ts,),
                ).fetchall()
        counts = {str(row["status"]): int(row["count"]) for row in rows}
        sent_total = sum(counts.values())
        return {
            "sent_total": sent_total,
            "pending": counts.get("pending", 0),
            "acknowledged": counts.get("acknowledged", 0),
            "escalated": counts.get("escalated", 0),
        }

    def reset_alerts(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM alerts").fetchone()
            deleted_count = 0 if row is None else int(row["count"])
            connection.execute("DELETE FROM alerts")
        return deleted_count

    def mark_acknowledged(
        self,
        alert_id: str,
        ack_text: str,
        acked_at_ts: int,
        update_id: int,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE alerts
                SET status = 'acknowledged',
                    ack_text = ?,
                    acked_at_ts = ?,
                    ack_update_id = ?
                WHERE alert_id = ? AND status = 'pending'
                """,
                (ack_text, acked_at_ts, update_id, alert_id),
            )

    def mark_escalated(
        self,
        alert_id: str,
        escalated_at_ts: int,
        escalation_message_id: int | None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE alerts
                SET status = 'escalated',
                    escalated_at_ts = ?,
                    escalation_message_id = ?
                WHERE alert_id = ? AND status = 'pending'
                """,
                (escalated_at_ts, escalation_message_id, alert_id),
            )

    def get_last_update_id(self) -> int | None:
        return self.get_chat_update_id()

    def set_last_update_id(self, update_id: int) -> None:
        self.set_chat_update_id(update_id)

    def get_chat_update_id(self) -> int | None:
        return self._get_update_id(TELEGRAM_CHAT_CURSOR_KEY)

    def set_chat_update_id(self, update_id: int) -> None:
        self.set_metadata(TELEGRAM_CHAT_CURSOR_KEY, str(update_id))

    def get_ack_update_id(self) -> int | None:
        return self._get_update_id(TELEGRAM_ACK_CURSOR_KEY)

    def set_ack_update_id(self, update_id: int) -> None:
        self.set_metadata(TELEGRAM_ACK_CURSOR_KEY, str(update_id))

    def _get_update_id(self, key: str) -> int | None:
        value = self.get_metadata(key)
        if value is None:
            value = self.get_metadata(TELEGRAM_LEGACY_CURSOR_KEY)
        return int(value) if value is not None else None

    def get_metadata(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def set_metadata(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO metadata (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    alert_id TEXT PRIMARY KEY,
                    severity TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    source TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    message TEXT NOT NULL,
                    probable_cause TEXT NOT NULL,
                    impact TEXT NOT NULL,
                    recommended_action TEXT NOT NULL,
                    telegram_message_id INTEGER,
                    sent_at_ts INTEGER NOT NULL,
                    due_at_ts INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    ack_text TEXT,
                    acked_at_ts INTEGER,
                    ack_update_id INTEGER,
                    escalated_at_ts INTEGER,
                    escalation_message_id INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )


def build_alert_id(event: LogEvent) -> str:
    fingerprint = "|".join(
        [
            event.timestamp,
            event.domain,
            event.source,
            event.severity,
            event.event_type,
            event.message,
            str(event.source_file),
            str(event.line_number),
        ]
    )
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:12].upper()
    return f"ALS-{digest}"


def _record_from_row(row: sqlite3.Row) -> AlertRecord:
    return AlertRecord(
        alert_id=row["alert_id"],
        severity=row["severity"],
        domain=row["domain"],
        source=row["source"],
        event_type=row["event_type"],
        timestamp=row["timestamp"],
        message=row["message"],
        probable_cause=row["probable_cause"],
        impact=row["impact"],
        recommended_action=row["recommended_action"],
        telegram_message_id=row["telegram_message_id"],
        sent_at_ts=row["sent_at_ts"],
        due_at_ts=row["due_at_ts"],
    )
