from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
import re
from zoneinfo import ZoneInfo

from infra_log_sentinel.models import LogEvent


LINUX_SYSLOG_FORMAT = "%b %d %H:%M:%S"
DATETIME_FORMATS = (
    "%H:%M:%S %d/%m/%Y",
    "%H:%M %d/%m/%Y",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%H:%M:%S %d-%m-%Y",
    "%H:%M %d-%m-%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
)
TIME_ONLY_FORMATS = ("%H:%M:%S", "%H:%M")


def filter_events_by_lookback(
    events: list[LogEvent],
    lookback_hours: float,
    reference_time: datetime | None = None,
) -> list[LogEvent]:
    reference_time = reference_time or datetime.now().astimezone()
    start_time = reference_time - timedelta(hours=lookback_hours)
    return [
        event
        for event in events
        if _event_in_window(event, start_time=start_time, end_time=reference_time)
    ]


def filter_events_by_time_range(
    events: list[LogEvent],
    start_time: datetime,
    end_time: datetime,
) -> list[LogEvent]:
    if end_time < start_time:
        start_time, end_time = end_time, start_time
    return [
        event
        for event in events
        if _event_in_window(event, start_time=start_time, end_time=end_time)
    ]


def parse_user_datetime(
    value: str,
    timezone_name: str = "Asia/Ho_Chi_Minh",
    reference_time: datetime | None = None,
) -> datetime | None:
    text = _clean_datetime_text(value)
    if not text:
        return None
    tz = _timezone(timezone_name)
    reference_time = reference_time or datetime.now(tz)

    for fmt in DATETIME_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=tz) if parsed.tzinfo is None else parsed.astimezone(tz)
        except ValueError:
            continue

    for fmt in TIME_ONLY_FORMATS:
        try:
            parsed_time = datetime.strptime(text, fmt).time()
            return datetime.combine(reference_time.date(), parsed_time, tzinfo=tz)
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=tz) if parsed.tzinfo is None else parsed.astimezone(tz)
    except ValueError:
        return None


def extract_time_range_from_text(
    value: str,
    timezone_name: str = "Asia/Ho_Chi_Minh",
) -> tuple[datetime, datetime] | None:
    text = str(value or "")
    match = re.search(r"(?:\btừ\b|\btu\b|\bfrom\b)\s+(.+?)\s+(?:\bđến\b|\bden\b|\bto\b)\s+(.+)", text, re.IGNORECASE)
    if not match:
        return None
    raw_start = _trim_range_part(match.group(1))
    raw_end = _trim_range_part(match.group(2))
    end_time = parse_user_datetime(raw_end, timezone_name=timezone_name)
    start_time = parse_user_datetime(raw_start, timezone_name=timezone_name, reference_time=end_time)
    if start_time is None or end_time is None:
        return None
    if end_time < start_time:
        start_time, end_time = end_time, start_time
    return start_time, end_time


def format_time_range_label(start_time: datetime, end_time: datetime) -> str:
    return (
        f"from {start_time.strftime('%H:%M:%S %d/%m/%Y')} "
        f"to {end_time.strftime('%H:%M:%S %d/%m/%Y')}"
    )


def parse_event_timestamp(event: LogEvent, reference_time: datetime | None = None) -> datetime | None:
    reference_time = reference_time or datetime.now().astimezone()
    timestamp = event.timestamp.strip()
    if not timestamp or timestamp == "unknown":
        return None

    try:
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None and reference_time.tzinfo is not None:
            parsed = parsed.replace(tzinfo=reference_time.tzinfo)
        return parsed
    except ValueError:
        pass

    try:
        parsed = datetime.strptime(timestamp, LINUX_SYSLOG_FORMAT)
        parsed = parsed.replace(year=reference_time.year)
        if reference_time.tzinfo is not None:
            parsed = parsed.replace(tzinfo=reference_time.tzinfo)
        return parsed
    except ValueError:
        return None


def _clean_datetime_text(value: str) -> str:
    text = str(value or "").strip()
    text = text.strip("`'\"()[]{}.,;")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\b(\d{1,2})h(\d{2})(?::?(\d{2}))?\b", _replace_hour_token, text, flags=re.IGNORECASE)
    return text


def _trim_range_part(value: str) -> str:
    text = str(value or "").strip()
    text = re.split(r"\s+(?:roi|rồi|va|và|de|để|phan|phân|analyze|analyse|rca)\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    return text.strip("`'\"()[]{}.,; ")


def _replace_hour_token(match: re.Match[str]) -> str:
    seconds = match.group(3)
    return f"{match.group(1)}:{match.group(2)}" + (f":{seconds}" if seconds else "")


def _timezone(timezone_name: str) -> tzinfo:
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        if timezone_name in {"Asia/Ho_Chi_Minh", "Asia/Saigon"}:
            return timezone(timedelta(hours=7))
        return datetime.now().astimezone().tzinfo or timezone.utc


def _event_in_window(event: LogEvent, start_time: datetime, end_time: datetime) -> bool:
    event_time = parse_event_timestamp(event, reference_time=end_time)
    if event_time is None:
        return False

    if start_time.tzinfo is not None and event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=start_time.tzinfo)
    if start_time.tzinfo is None and event_time.tzinfo is not None:
        start_time = start_time.replace(tzinfo=event_time.tzinfo)
        end_time = end_time.replace(tzinfo=event_time.tzinfo)

    return start_time <= event_time <= end_time
