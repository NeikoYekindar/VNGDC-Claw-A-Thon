from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
import time


@dataclass(frozen=True)
class LogCursor:
    path: str
    last_line_number: int
    file_size: int
    file_mtime: float


class LogCursorStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_cursor(self, path: Path) -> LogCursor | None:
        normalized_path = _normalize_path(path)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT path, last_line_number, file_size, file_mtime
                FROM log_cursors
                WHERE path = ?
                """,
                (normalized_path,),
            ).fetchone()
        if row is None:
            return None
        return LogCursor(
            path=row["path"],
            last_line_number=int(row["last_line_number"]),
            file_size=int(row["file_size"]),
            file_mtime=float(row["file_mtime"]),
        )

    def upsert_cursor(
        self,
        path: Path,
        last_line_number: int,
        file_size: int,
        file_mtime: float,
    ) -> None:
        normalized_path = _normalize_path(path)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO log_cursors (path, last_line_number, file_size, file_mtime, updated_at_ts)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    last_line_number = excluded.last_line_number,
                    file_size = excluded.file_size,
                    file_mtime = excluded.file_mtime,
                    updated_at_ts = excluded.updated_at_ts
                """,
                (normalized_path, last_line_number, file_size, file_mtime, int(time.time())),
            )

    def mark_file_consumed(self, path: Path, line_count: int) -> None:
        stat = path.stat()
        self.upsert_cursor(
            path=path,
            last_line_number=line_count,
            file_size=stat.st_size,
            file_mtime=stat.st_mtime,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS log_cursors (
                    path TEXT PRIMARY KEY,
                    last_line_number INTEGER NOT NULL,
                    file_size INTEGER NOT NULL,
                    file_mtime REAL NOT NULL,
                    updated_at_ts INTEGER NOT NULL
                )
                """
            )


def _normalize_path(path: Path) -> str:
    return str(path.resolve()).lower()
