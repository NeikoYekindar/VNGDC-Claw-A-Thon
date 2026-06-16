from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


CONTROL_TELEGRAM_ALERTS = "telegram_alerts"
CONTROL_EMAIL_REPORTS = "email_reports"
CONTROL_LOG_GENERATION = "log_generation"
CONTROL_INCIDENT_GENERATION = "incident_generation"
VALUE_DEMO_LOG_INTERVAL_SECONDS = "demo_log_interval_seconds"
VALUE_INCIDENT_LOG_INTERVAL_SECONDS = "incident_log_interval_seconds"
VALUE_REPORT_TIME = "report_time"
VALUE_SCAN_INTERVAL_SECONDS = "scan_interval_seconds"


@dataclass(frozen=True)
class PauseState:
    name: str
    paused: bool
    paused_until: datetime | None

    def as_text(self) -> str:
        if not self.paused or self.paused_until is None:
            return f"{self.name}: running"
        if self.paused_until.year >= 9999:
            return f"{self.name}: off until enabled again"
        return f"{self.name}: paused until {self.paused_until:%Y-%m-%d %H:%M:%S}"


class RuntimeControlStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def pause_until(self, name: str, paused_until: datetime) -> None:
        paused_until = ensure_app_timezone(paused_until)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runtime_controls(name, paused_until, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    paused_until = excluded.paused_until,
                    updated_at = excluded.updated_at
                """,
                (name, paused_until.isoformat(), now_in_app_timezone().isoformat()),
            )

    def resume(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runtime_controls(name, paused_until, updated_at)
                VALUES (?, NULL, ?)
                ON CONFLICT(name) DO UPDATE SET
                    paused_until = NULL,
                    updated_at = excluded.updated_at
                """,
                (name, now_in_app_timezone().isoformat()),
            )

    def pause_state(self, name: str, now: datetime | None = None) -> PauseState:
        now = ensure_app_timezone(now) if now is not None else now_in_app_timezone()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT paused_until FROM runtime_controls WHERE name = ?",
                (name,),
            ).fetchone()
        if row is None or row["paused_until"] is None:
            return PauseState(name=name, paused=False, paused_until=None)

        paused_until = ensure_app_timezone(datetime.fromisoformat(str(row["paused_until"])))
        if paused_until <= now:
            self.resume(name)
            return PauseState(name=name, paused=False, paused_until=None)
        return PauseState(name=name, paused=True, paused_until=paused_until)

    def set_value(self, name: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runtime_control_values(name, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (name, value, now_in_app_timezone().isoformat()),
            )

    def get_value(self, name: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value FROM runtime_control_values WHERE name = ?",
                (name,),
            ).fetchone()
        if row is None:
            return None
        return str(row["value"])

    def get_float_value(self, name: str, default: float) -> float:
        value = self.get_value(name)
        if value is None:
            return default
        try:
            return float(value)
        except ValueError:
            return default

    def snapshot(self) -> dict[str, object]:
        controls = [
            CONTROL_TELEGRAM_ALERTS,
            CONTROL_EMAIL_REPORTS,
            CONTROL_LOG_GENERATION,
            CONTROL_INCIDENT_GENERATION,
        ]
        return {
            "pauses": {
                name: {
                    "paused": state.paused,
                    "paused_until": None if state.paused_until is None else state.paused_until.isoformat(),
                    "manual_off": bool(state.paused_until and state.paused_until.year >= 9999),
                }
                for name in controls
                for state in [self.pause_state(name)]
            },
            "values": {
                VALUE_DEMO_LOG_INTERVAL_SECONDS: self.get_value(VALUE_DEMO_LOG_INTERVAL_SECONDS),
                VALUE_INCIDENT_LOG_INTERVAL_SECONDS: self.get_value(VALUE_INCIDENT_LOG_INTERVAL_SECONDS),
                VALUE_REPORT_TIME: self.get_value(VALUE_REPORT_TIME),
                VALUE_SCAN_INTERVAL_SECONDS: self.get_value(VALUE_SCAN_INTERVAL_SECONDS),
            },
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_controls (
                    name TEXT PRIMARY KEY,
                    paused_until TEXT,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runtime_control_values (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )


def now_in_app_timezone() -> datetime:
    return datetime.now(app_timezone())


def ensure_app_timezone(value: datetime) -> datetime:
    tz = app_timezone()
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def app_timezone():
    name = os.getenv("APP_TIMEZONE", "Asia/Ho_Chi_Minh")
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=7))
