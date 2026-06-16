from __future__ import annotations

from pathlib import Path
from typing import Iterable

from infra_log_sentinel.models import RawLogLine
from infra_log_sentinel.state.log_cursor import LogCursorStore


SUPPORTED_EXTENSIONS = {".log", ".txt", ".csv"}
KNOWN_DOMAINS = {
    "network",
    "fortigate",
    "juniper",
    "aruba",
    "linux",
    "windows",
    "vmware",
    "checkmk",
    "cacti",
    "prometheus",
    "grafana",
    "elk",
    "wazuh",
    "syslog",
}


def iter_log_lines(log_root_path: Path) -> Iterable[RawLogLine]:
    """Read log lines from a local or Google Drive synced folder."""
    root = log_root_path.expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Log root path does not exist: {root}")

    for domain, path in iter_log_files(root):
        yield from _iter_file_lines(root=root, path=path, domain=domain, start_after_line=0)


def iter_new_log_lines(
    log_root_path: Path,
    cursor_store: LogCursorStore,
    update_cursor: bool = True,
) -> Iterable[RawLogLine]:
    """Read only log lines added since the last cursor update."""
    root = log_root_path.expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Log root path does not exist: {root}")

    for domain, path in iter_log_files(root):
        stat = path.stat()
        cursor = cursor_store.get_cursor(path)
        start_after_line = 0
        if cursor is not None:
            file_was_truncated = stat.st_size < cursor.file_size
            start_after_line = 0 if file_was_truncated else cursor.last_line_number

        last_seen_line = start_after_line
        for raw_line in _iter_file_lines(root=root, path=path, domain=domain, start_after_line=start_after_line):
            last_seen_line = raw_line.line_number
            yield raw_line

        if update_cursor:
            cursor_store.upsert_cursor(
                path=path,
                last_line_number=last_seen_line,
                file_size=stat.st_size,
                file_mtime=stat.st_mtime,
            )


def initialize_log_cursors(log_root_path: Path, cursor_store: LogCursorStore) -> int:
    """Mark the current folder content as already consumed for realtime alerting."""
    root = log_root_path.expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Log root path does not exist: {root}")

    file_count = 0
    for _, path in iter_log_files(root):
        line_count = _count_lines(path)
        cursor_store.mark_file_consumed(path=path, line_count=line_count)
        file_count += 1
    return file_count


def iter_log_files(root: Path) -> Iterable[tuple[str, Path]]:
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        domain = _domain_from_path(root, path)
        yield domain, path


def _iter_file_lines(root: Path, path: Path, domain: str, start_after_line: int) -> Iterable[RawLogLine]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            if line_number <= start_after_line:
                continue
            text = line.strip().lstrip("\ufeff")
            if not text:
                continue
            yield RawLogLine(
                domain=domain,
                source_file=path,
                line_number=line_number,
                text=text,
            )


def _count_lines(path: Path) -> int:
    count = 0
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for _ in handle:
            count += 1
    return count


def _domain_from_path(root: Path, path: Path) -> str:
    relative_parts = path.relative_to(root).parts
    if relative_parts and relative_parts[0].lower() in KNOWN_DOMAINS:
        return relative_parts[0].lower()
    parent = path.parent.name.lower()
    if parent in KNOWN_DOMAINS:
        return parent
    return "unknown"
