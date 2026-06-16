import base64
import html
import json
import logging
import re
import uuid
import urllib.request
from typing import Any

try:
    from langchain_core.tools import tool
except ModuleNotFoundError:
    def tool(func):
        return func

from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from src.tools.teams import _build_card

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org/bot"
TELEGRAM_MESSAGE_LIMIT = 3900


def _configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)


def _split_text(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    value = text.strip() or "No content."
    chunks: list[str] = []
    while value:
        if len(value) <= limit:
            chunks.append(value)
            break
        split_at = value.rfind("\n", 0, limit)
        if split_at < limit // 2:
            split_at = limit
        chunks.append(value[:split_at].strip())
        value = value[split_at:].strip()
    return chunks


def _format_inline(text: str) -> str:
    parts = re.split(r"(`[^`]+`|\*\*[^*]+\*\*)", text)
    rendered: list[str] = []
    for part in parts:
        if not part:
            continue
        if part.startswith("`") and part.endswith("`") and len(part) >= 2:
            rendered.append(f"<code>{html.escape(part[1:-1])}</code>")
        elif part.startswith("**") and part.endswith("**") and len(part) >= 4:
            rendered.append(f"<b>{html.escape(part[2:-2])}</b>")
        else:
            rendered.append(html.escape(part))
    return "".join(rendered)


def _is_table_separator(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped.startswith("|") and re.fullmatch(r"[\s|:\-]+", stripped))


def _format_table_row(line: str) -> str:
    cells = [cell.strip() for cell in line.strip().strip("|").split("|") if cell.strip()]
    if not cells:
        return ""
    if len(cells) == 2:
        return f"• <b>{html.escape(cells[0])}</b>: {_format_inline(cells[1])}"
    if len(cells) >= 3:
        return f"• <b>{html.escape(cells[0])}</b>: {_format_inline(' | '.join(cells[1:]))}"
    return f"• {_format_inline(cells[0])}"


def _telegram_html(text: str) -> str:
    """Convert the agent's lightweight Markdown into Telegram-safe HTML."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output: list[str] = []
    code_lines: list[str] = []
    in_code = False

    for raw_line in lines:
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            if in_code:
                output.append(f"<pre>{html.escape(chr(10).join(code_lines))}</pre>")
                code_lines = []
                in_code = False
            else:
                in_code = True
                code_lines = []
            continue

        if in_code:
            code_lines.append(line)
            continue

        stripped = line.strip()
        if not stripped:
            output.append("")
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            output.append(f"<b>{html.escape(heading.group(2).strip())}</b>")
            continue

        if _is_table_separator(stripped):
            continue

        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            formatted_row = _format_table_row(stripped)
            if formatted_row:
                output.append(formatted_row)
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet:
            output.append(f"• {_format_inline(bullet.group(1))}")
            continue

        numbered = re.match(r"^(\d+)[.)]\s+(.+)$", stripped)
        if numbered:
            output.append(f"{numbered.group(1)}. {_format_inline(numbered.group(2))}")
            continue

        quote = re.match(r"^>\s+(.+)$", stripped)
        if quote:
            output.append(f"│ {_format_inline(quote.group(1))}")
            continue

        output.append(_format_inline(stripped))

    if in_code:
        output.append(f"<pre>{html.escape(chr(10).join(code_lines))}</pre>")

    rendered = "\n".join(output).strip()
    rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered or "No content."


def _telegram_json(method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{TELEGRAM_API_BASE}{TELEGRAM_BOT_TOKEN}/{method}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _telegram_multipart(method: str, fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> dict[str, Any]:
    boundary = f"----vngdc-{uuid.uuid4().hex}"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for name, (filename, content, content_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(content)
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode())
    url = f"{TELEGRAM_API_BASE}{TELEGRAM_BOT_TOKEN}/{method}"
    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())


def _send_message(chat_id: str, text: str, reply_to_message_id: int | None = None) -> None:
    for chunk in _split_text(text):
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": _telegram_html(chunk),
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_to_message_id:
            payload["reply_to_message_id"] = reply_to_message_id
            payload["allow_sending_without_reply"] = True
        _telegram_json("sendMessage", payload)


def _send_chat_action(chat_id: str, action: str = "typing") -> None:
    _telegram_json("sendChatAction", {"chat_id": chat_id, "action": action})


def _send_document(chat_id: str, filename: str, content: bytes, caption: str = "") -> None:
    fields = {"chat_id": chat_id}
    if caption:
        fields["caption"] = caption[:1024]
    _telegram_multipart(
        "sendDocument",
        fields=fields,
        files={
            "document": (
                filename,
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )


def _send_report(title: str, sections: list, chat_id: str | None = None) -> bool:
    """Send a structured security report to Telegram. Raises on API failure."""
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat_id:
        logger.warning("Telegram bot token/chat id not configured; notification skipped.")
        return False

    card = _build_card(title, sections)
    _send_message(str(target_chat_id), card.get("text") or title)

    attachment = card.get("attachments", [None])[0]
    if isinstance(attachment, dict) and attachment.get("contentBase64"):
        content = base64.b64decode(attachment["contentBase64"])
        _send_document(
            str(target_chat_id),
            attachment.get("name") or "security-report.xlsx",
            content,
            caption="Security report evidence",
        )
    return True


@tool
def send_telegram_notification(message: str, title: str = "Security Alert") -> str:
    """
    Send a security notification to Telegram via Telegram Bot API.

    Args:
        message: Notification body.
        title: Message title.

    Returns:
        Confirmation or error message.
    """
    try:
        if not _configured():
            return "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured."
        _send_message(TELEGRAM_CHAT_ID, f"{title}\n\n{message}")
        return "Notification sent to Telegram."
    except Exception as exc:
        logger.error("Failed to send Telegram notification: %s", exc)
        return f"Failed to send Telegram notification: {exc}"
