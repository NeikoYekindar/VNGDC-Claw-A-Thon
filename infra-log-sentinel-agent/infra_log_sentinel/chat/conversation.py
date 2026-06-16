from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import time


@dataclass(frozen=True)
class ConversationSnapshot:
    channel: str
    last_user_message: str
    last_agent_message: str
    last_intent: str
    last_action: str
    last_artifact_path: str
    updated_at_ts: int


EMPTY_CONVERSATION = ConversationSnapshot(
    channel="",
    last_user_message="",
    last_agent_message="",
    last_intent="",
    last_action="",
    last_artifact_path="",
    updated_at_ts=0,
)


class ConversationStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def get(self, channel: str) -> ConversationSnapshot:
        self._ensure_schema()
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT channel, last_user_message, last_agent_message, last_intent,
                       last_action, last_artifact_path, updated_at_ts
                FROM conversation_state
                WHERE channel = ?
                """,
                (channel,),
            ).fetchone()
        if row is None:
            return EMPTY_CONVERSATION
        return ConversationSnapshot(
            channel=row[0] or "",
            last_user_message=row[1] or "",
            last_agent_message=row[2] or "",
            last_intent=row[3] or "",
            last_action=row[4] or "",
            last_artifact_path=row[5] or "",
            updated_at_ts=int(row[6] or 0),
        )

    def update(
        self,
        channel: str,
        user_message: str,
        agent_message: str,
        intent: str,
        action: str = "",
        artifact_path: str = "",
    ) -> None:
        self._ensure_schema()
        now_ts = int(time.time())
        with closing(self._connect()) as connection:
            connection.execute(
                """
                INSERT INTO conversation_state (
                    channel, last_user_message, last_agent_message, last_intent,
                    last_action, last_artifact_path, updated_at_ts
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(channel) DO UPDATE SET
                    last_user_message = excluded.last_user_message,
                    last_agent_message = excluded.last_agent_message,
                    last_intent = excluded.last_intent,
                    last_action = excluded.last_action,
                    last_artifact_path = excluded.last_artifact_path,
                    updated_at_ts = excluded.updated_at_ts
                """,
                (
                    channel,
                    user_message,
                    agent_message,
                    intent,
                    action,
                    artifact_path,
                    now_ts,
                ),
            )
            connection.commit()

    def clear(self, channel: str) -> None:
        self._ensure_schema()
        with closing(self._connect()) as connection:
            connection.execute("DELETE FROM conversation_state WHERE channel = ?", (channel,))
            connection.commit()

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_state (
                    channel TEXT PRIMARY KEY,
                    last_user_message TEXT NOT NULL DEFAULT '',
                    last_agent_message TEXT NOT NULL DEFAULT '',
                    last_intent TEXT NOT NULL DEFAULT '',
                    last_action TEXT NOT NULL DEFAULT '',
                    last_artifact_path TEXT NOT NULL DEFAULT '',
                    updated_at_ts INTEGER NOT NULL
                )
                """
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, timeout=10)
