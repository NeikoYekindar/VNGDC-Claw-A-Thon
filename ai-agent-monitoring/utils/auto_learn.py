"""
Knowledge Auto-Learn - propose knowledge entries from successful RCAs.

Flow:
  1. After RCA with HIGH/MEDIUM confidence, LLM extracts a knowledge entry.
  2. Entry is stored in memory with a 48h token.
  3. Telegram message is sent with a save link.
  4. The user confirms the link and the file is saved to knowledge/.
"""

import secrets
from datetime import datetime, timedelta
from pathlib import Path

_PENDING: dict[str, dict] = {}
_CONSUMED: dict[str, dict] = {}
_TTL_HOURS = 48
_KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


def _now() -> str:
    return datetime.utcnow().isoformat()


def _prune() -> None:
    now = _now()
    for token in [t for t, entry in _PENDING.items() if entry["expires"] < now]:
        _PENDING.pop(token, None)
    for token in [t for t, entry in _CONSUMED.items() if entry["expires"] < now]:
        _CONSUMED.pop(token, None)


def store_pending(content: str, alert_name: str) -> str:
    """Store a proposed knowledge entry. Returns a one-time save token."""
    _prune()

    token = secrets.token_urlsafe(24)
    _PENDING[token] = {
        "content": content,
        "alert_name": alert_name,
        "created_at": _now(),
        "expires": (datetime.utcnow() + timedelta(hours=_TTL_HOURS)).isoformat(),
    }
    return token


def confirm_save(token: str) -> tuple[bool, str]:
    """
    Save a pending knowledge file.

    Repeated calls with a consumed token return success with the same filename.
    This avoids a false error when Telegram/browser previews touch the link
    before the user sees the final page.
    """
    _prune()

    consumed = _CONSUMED.get(token)
    if consumed:
        return True, consumed["filename"]

    entry = _PENDING.get(token)
    if not entry:
        return False, "Token khong hop le hoac da het han."
    if _now() > entry["expires"]:
        _PENDING.pop(token, None)
        return False, "Token da het han qua 48 gio."

    safe = entry["alert_name"].lower()
    for ch in " /\\:*?\"<>|":
        safe = safe.replace(ch, "_")
    safe = safe[:30]
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    filename = f"auto_{safe}_{ts}.md"

    _KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    (_KNOWLEDGE_DIR / filename).write_text(entry["content"], encoding="utf-8")

    _PENDING.pop(token, None)
    _CONSUMED[token] = {
        "filename": filename,
        "expires": entry["expires"],
    }

    try:
        from utils.knowledge_loader import get_relevant_knowledge
        get_relevant_knowledge.cache_clear()
    except Exception:
        pass

    return True, filename
