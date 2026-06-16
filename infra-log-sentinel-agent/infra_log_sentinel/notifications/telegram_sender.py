from __future__ import annotations

from dataclasses import dataclass
from html import escape
import threading
import time

import requests
from requests import Response
from requests import exceptions as requests_exceptions

from infra_log_sentinel.analysis.runbook import recommend_commands
from infra_log_sentinel.config import Settings
from infra_log_sentinel.models import LogEvent
from infra_log_sentinel.state.alert_store import build_alert_id


TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_TIMEOUT = (10, 45)
TELEGRAM_RETRIES = 2
_GET_UPDATES_LOCK = threading.Lock()
PLACEHOLDER_VALUES = {
    "",
    "replace_with_telegram_bot_token",
    "replace_with_telegram_chat_id",
}
SEVERITY_ORDER = {"critical": 0, "error": 1, "warning": 2, "info": 3}
SEVERITY_BADGE = {
    "critical": "🔴 CRITICAL",
    "error": "🟠 ERROR",
    "warning": "🟡 WARNING",
    "info": "🔵 INFO",
}
DOMAIN_BADGE = {
    "network": "🌐 Network",
    "linux": "🐧 Linux",
    "windows": "🪟 Windows",
    "vmware": "🧱 VMware",
}


class TelegramConfigError(ValueError):
    """Raised when required Telegram settings are missing or invalid."""


class TelegramSendError(RuntimeError):
    """Raised when Telegram accepts config but cannot send the message."""


@dataclass(frozen=True)
class TelegramSendResult:
    sent_count: int
    dry_run: bool
    message: str


@dataclass(frozen=True)
class TelegramUpdate:
    update_id: int
    message_date_ts: int
    text: str
    message_id: int | None = None
    reply_to_message_id: int | None = None


def check_telegram_health(settings: Settings) -> str:
    token = settings.telegram_bot_token.strip()
    chat_id = settings.telegram_chat_id.strip()
    config_errors = _config_errors(token, chat_id)
    if config_errors:
        raise TelegramConfigError("Invalid Telegram configuration: " + ", ".join(config_errors))

    response = _telegram_post(
        token=token,
        method="getMe",
        json_payload={},
    )
    if not response.ok:
        raise TelegramSendError(_telegram_error("Telegram getMe failed", response))

    payload = response.json()
    bot = payload.get("result", {})
    username = bot.get("username", "<unknown>")

    response = _telegram_post(
        token=token,
        method="sendMessage",
        json_payload={
            "chat_id": chat_id,
            "text": "✅ Telegram health check OK from Infrastructure Log Sentinel Agent.",
            "disable_web_page_preview": True,
        },
    )
    if not response.ok:
        raise TelegramSendError(_telegram_error("Telegram health message failed", response))

    return f"Telegram health check OK. Bot @{username} can send messages to the configured chat."


def send_telegram_message(
    settings: Settings,
    text: str,
    parse_mode: str | None = None,
) -> int | None:
    token = settings.telegram_bot_token.strip()
    chat_id = settings.telegram_chat_id.strip()
    config_errors = _config_errors(token, chat_id)
    if config_errors:
        raise TelegramConfigError("Invalid Telegram configuration: " + ", ".join(config_errors))
    return _send_message(token=token, chat_id=chat_id, text=text, parse_mode=parse_mode)


def fetch_telegram_updates(
    settings: Settings,
    offset: int | None = None,
    timeout_seconds: int = 0,
) -> list[TelegramUpdate]:
    token = settings.telegram_bot_token.strip()
    chat_id = settings.telegram_chat_id.strip()
    config_errors = _config_errors(token, chat_id)
    if config_errors:
        raise TelegramConfigError("Invalid Telegram configuration: " + ", ".join(config_errors))
    return _fetch_updates(
        token=token,
        chat_id=chat_id,
        offset=offset,
        timeout_seconds=timeout_seconds,
    )


def send_telegram_alerts(
    settings: Settings,
    events: list[LogEvent],
    dry_run: bool = False,
    max_alerts: int | None = None,
) -> TelegramSendResult:
    token = settings.telegram_bot_token.strip()
    chat_id = settings.telegram_chat_id.strip()
    config_errors = _config_errors(token, chat_id)
    if config_errors and not dry_run:
        raise TelegramConfigError("Invalid Telegram configuration: " + ", ".join(config_errors))

    alert_events = select_alert_events(events, settings.severity_alert_levels)
    if max_alerts is not None:
        alert_events = alert_events[:max_alerts]

    if dry_run:
        preview = "\n\n".join(
            format_alert_message(event, index, len(alert_events), build_alert_id(event))
            for index, event in enumerate(alert_events[:3], start=1)
        )
        warning_text = f" Config warnings: {', '.join(config_errors)}." if config_errors else ""
        return TelegramSendResult(
            sent_count=0,
            dry_run=True,
            message=(
                f"Telegram dry run OK. Would send {len(alert_events)} alert message(s)."
                f"{warning_text}\n\nPreview:\n{preview}"
            ),
        )

    sent_count = 0
    for index, event in enumerate(alert_events, start=1):
        alert_id = build_alert_id(event)
        _send_message(
            token=token,
            chat_id=chat_id,
            text=format_alert_message(event, index, len(alert_events), alert_id),
        )
        sent_count += 1

    return TelegramSendResult(
        sent_count=sent_count,
        dry_run=False,
        message=f"Telegram alert delivery complete. Sent {sent_count} alert message(s).",
    )


def select_alert_events(events: list[LogEvent], alert_levels: tuple[str, ...]) -> list[LogEvent]:
    alert_set = set(alert_levels)
    return sorted(
        [event for event in events if event.severity in alert_set],
        key=lambda event: (SEVERITY_ORDER.get(event.severity, 99), event.domain, event.source),
    )


def format_alert_message(event: LogEvent, index: int, total: int, alert_id: str) -> str:
    commands = recommend_commands(event)[:3]
    command_lines = [
        f"{idx}. <b>{escape(item.phase)}</b>: <code>{escape(item.command)}</code>\n   {escape(item.purpose)}"
        for idx, item in enumerate(commands, start=1)
    ]
    severity_badge = SEVERITY_BADGE.get(event.severity, event.severity.upper())
    domain_badge = DOMAIN_BADGE.get(event.domain, event.domain)
    return "\n".join(
        [
            f"🚨 <b>INFRA-LOG-SENTINEL Alert {index}/{total}</b>",
            f"<b>Alert ID:</b> <code>{escape(alert_id)}</code>",
            f"<b>Severity:</b> {severity_badge}",
            f"<b>Domain:</b> {domain_badge}",
            f"<b>Source:</b> <code>{escape(event.source)}</code>",
            f"<b>Type:</b> <code>{escape(event.event_type)}</code>",
            f"<b>Timestamp:</b> {escape(event.timestamp)}",
            "",
            f"📌 <b>Summary</b>\n{escape(_trim(event.message, 650))}",
            f"🧠 <b>Analysis</b>\n{escape(event.probable_cause)}",
            f"💥 <b>Impact</b>\n{escape(event.impact)}",
            f"🛠 <b>Solution</b>\n{escape(event.recommended_action)}",
            "",
            "🔎 <b>Commands to run</b>",
            *command_lines,
        ]
    )


def _send_message(
    token: str,
    chat_id: str,
    text: str,
    parse_mode: str | None = "HTML",
) -> int | None:
    payload: dict[str, object] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode

    response = _telegram_post(
        token=token,
        method="sendMessage",
        json_payload=payload,
    )
    if response.ok:
        try:
            payload = response.json()
        except ValueError:
            return None
        result = payload.get("result", {})
        message_id = result.get("message_id")
        return int(message_id) if message_id is not None else None

    raise TelegramSendError(_telegram_error("Telegram API failed", response))


def _fetch_updates(
    token: str,
    chat_id: str,
    offset: int | None,
    timeout_seconds: int = 0,
) -> list[TelegramUpdate]:
    payload: dict[str, object] = {
        "timeout": max(timeout_seconds, 0),
        "allowed_updates": ["message", "channel_post"],
    }
    if offset is not None:
        payload["offset"] = offset

    with _GET_UPDATES_LOCK:
        response = _telegram_post(token=token, method="getUpdates", json_payload=payload)
    if not response.ok:
        raise TelegramSendError(_telegram_error("Telegram getUpdates failed", response))

    payload = response.json()
    updates: list[TelegramUpdate] = []
    for item in payload.get("result", []):
        message = item.get("message") or item.get("channel_post")
        if not message:
            continue
        message_chat = message.get("chat", {})
        if str(message_chat.get("id")) != str(chat_id):
            continue
        text = str(message.get("text") or message.get("caption") or "").strip()
        if not text:
            continue
        reply_to_message = message.get("reply_to_message") or {}
        updates.append(
            TelegramUpdate(
                update_id=int(item["update_id"]),
                message_date_ts=int(message.get("date", 0)),
                text=text,
                message_id=_optional_int(message.get("message_id")),
                reply_to_message_id=_optional_int(reply_to_message.get("message_id")),
            )
        )
    return updates


def _optional_int(value: object) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _config_errors(token: str, chat_id: str) -> list[str]:
    errors = []
    if token in PLACEHOLDER_VALUES:
        errors.append("TELEGRAM_BOT_TOKEN is missing")
    elif ":" not in token:
        errors.append("TELEGRAM_BOT_TOKEN does not look like a bot token")

    if chat_id in PLACEHOLDER_VALUES:
        errors.append("TELEGRAM_CHAT_ID is missing")

    return errors


def _telegram_post(token: str, method: str, json_payload: dict[str, object]) -> Response:
    url = f"{TELEGRAM_API_BASE}/bot{token}/{method}"
    last_error: Exception | None = None
    for attempt in range(1, TELEGRAM_RETRIES + 2):
        try:
            return requests.post(url, json=json_payload, timeout=TELEGRAM_TIMEOUT)
        except requests_exceptions.Timeout as exc:
            last_error = exc
        except requests_exceptions.ConnectionError as exc:
            last_error = exc
        except requests_exceptions.RequestException as exc:
            last_error = exc

        if attempt <= TELEGRAM_RETRIES:
            time.sleep(attempt * 2)

    raise TelegramSendError(
        "Telegram network connection failed after retries. "
        "The workstation could not complete HTTPS/TLS connection to api.telegram.org. "
        "Check corporate proxy/firewall/VPN, then retry. "
        f"Last error: {last_error}"
    )


def _telegram_error(prefix: str, response: Response) -> str:
    try:
        error_payload = response.json()
        description = error_payload.get("description", response.text)
    except ValueError:
        description = response.text
    return f"{prefix} with HTTP {response.status_code}: {description}"


def _trim(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."
