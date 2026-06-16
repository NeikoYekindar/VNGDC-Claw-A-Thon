from __future__ import annotations

from pathlib import Path
import json
import sqlite3
import time
from typing import Any


class RcaIncidentStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def save(self, incident: dict[str, Any], analysis: dict[str, Any]) -> None:
        incident_id = str(analysis.get("incident_id") or incident.get("incident_id") or "")
        if not incident_id:
            raise ValueError("RCA incident_id is required")
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO rca_incidents (
                    incident_id, severity, status, confidence, incident_json,
                    analysis_json, created_at_ts
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    severity = excluded.severity,
                    status = excluded.status,
                    confidence = excluded.confidence,
                    incident_json = excluded.incident_json,
                    analysis_json = excluded.analysis_json,
                    created_at_ts = excluded.created_at_ts
                """,
                (
                    incident_id,
                    str(analysis.get("severity") or ""),
                    str(analysis.get("status") or ""),
                    int(analysis.get("confidence") or 0),
                    json.dumps(incident, ensure_ascii=False, sort_keys=True),
                    json.dumps(analysis, ensure_ascii=False, sort_keys=True),
                    int(time.time()),
                ),
            )

    def latest(self) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT incident_json, analysis_json
                FROM rca_incidents
                ORDER BY created_at_ts DESC, incident_id DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return {
            "incident": json.loads(str(row["incident_json"])),
            "analysis": json.loads(str(row["analysis_json"])),
        }

    def get(self, incident_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT incident_json, analysis_json
                FROM rca_incidents
                WHERE incident_id = ?
                """,
                (incident_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "incident": json.loads(str(row["incident_json"])),
            "analysis": json.loads(str(row["analysis_json"])),
        }

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS rca_incidents (
                    incident_id TEXT PRIMARY KEY,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confidence INTEGER NOT NULL,
                    incident_json TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    created_at_ts INTEGER NOT NULL
                )
                """
            )
