"""
Alert suppression / maintenance window manager.
Suppressed instances have their alerts silently dropped during processing.
Data persisted in data/suppressions.json.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"
_SUPP_FILE = _DATA_DIR / "suppressions.json"


# ── Store helpers ──────────────────────────────────────────────────────────────

def _load() -> dict:
    if not _SUPP_FILE.exists():
        return {}
    try:
        return json.loads(_SUPP_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _SUPP_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Public API ─────────────────────────────────────────────────────────────────

def suppress(instance: str, hours: float, reason: str = "") -> dict:
    """Suppress alerts from `instance` for `hours` hours. Returns the entry."""
    if hours <= 0 or hours > 168:  # max 7 days
        raise ValueError("hours phải từ 0 đến 168 (7 ngày)")
    data = _load()
    until = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
    data[instance] = {
        "until": until,
        "reason": reason or "Maintenance",
        "created_at": datetime.utcnow().isoformat(),
        "created_by": "",  # filled by caller if needed
    }
    _save(data)
    return {"instance": instance, "until": until, "reason": data[instance]["reason"]}


def remove(instance: str) -> bool:
    """Remove suppression for `instance`. Returns False if not found."""
    data = _load()
    if instance not in data:
        return False
    del data[instance]
    _save(data)
    return True


def is_suppressed(instance: str) -> bool:
    """Return True if `instance` is currently under active suppression."""
    if not instance:
        return False
    data = _load()
    entry = data.get(instance)
    if not entry:
        return False
    now = datetime.utcnow().isoformat()
    if entry["until"] > now:
        return True
    # Expired — clean up lazily
    del data[instance]
    _save(data)
    return False


def list_suppressions() -> list[dict]:
    """Return all currently active suppressions (expired ones are pruned)."""
    data = _load()
    now = datetime.utcnow().isoformat()
    active, expired = [], []
    for instance, entry in data.items():
        if entry["until"] > now:
            active.append({"instance": instance, **entry})
        else:
            expired.append(instance)
    if expired:
        for k in expired:
            del data[k]
        _save(data)
    return active
