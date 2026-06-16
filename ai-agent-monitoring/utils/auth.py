"""
Simple auth — users stored in data/users.json, sessions in memory.
Sessions reset on restart (acceptable for this use case).
"""

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

_DATA_DIR = Path(__file__).parent.parent / "data"
_USERS_FILE = _DATA_DIR / "users.json"
_SESSION_TTL_HOURS = 24

# In-memory: {token: {"username": str, "role": str, "expires": datetime}}
_sessions: dict[str, dict] = {}


# ── Password hashing ───────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(":", 1)
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest() == h
    except Exception:
        return False


# ── User store ─────────────────────────────────────────────────────────────────

def _load_users() -> dict:
    if not _USERS_FILE.exists():
        return {}
    try:
        return json.loads(_USERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_users(users: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _USERS_FILE.write_text(
        json.dumps(users, indent=2, ensure_ascii=False), encoding="utf-8"
    )


# ── Bootstrap ──────────────────────────────────────────────────────────────────

def ensure_default_admin() -> Optional[str]:
    """Create default admin on first run. Returns password if created (for logs)."""
    users = _load_users()
    if users:
        return None
    default_password = os.environ.get("ADMIN_DEFAULT_PASSWORD")
    users["admin"] = {
        "password_hash": _hash_password(default_password),
        "role": "admin",
        "created_at": datetime.utcnow().isoformat(),
    }
    _save_users(users)
    return default_password


# ── Auth ───────────────────────────────────────────────────────────────────────

def login(username: str, password: str) -> Optional[dict]:
    """Returns {token, username, role} if valid, else None."""
    users = _load_users()
    user = users.get(username)
    if not user or not _verify_password(password, user["password_hash"]):
        return None
    token = secrets.token_hex(32)
    _sessions[token] = {
        "username": username,
        "role": user["role"],
        "expires": datetime.utcnow() + timedelta(hours=_SESSION_TTL_HOURS),
    }
    return {"token": token, "username": username, "role": user["role"]}


def validate_token(token: str) -> Optional[dict]:
    """Returns {username, role} if token valid, else None."""
    if not token:
        return None
    session = _sessions.get(token)
    if not session:
        return None
    if datetime.utcnow() > session["expires"]:
        _sessions.pop(token, None)
        return None
    return {"username": session["username"], "role": session["role"]}


def logout(token: str) -> None:
    _sessions.pop(token, None)


# ── User management (admin only) ───────────────────────────────────────────────

def create_user(username: str, password: str, role: str = "user") -> dict:
    if role not in ("admin", "user"):
        raise ValueError("Role phải là 'admin' hoặc 'user'")
    if not username or not password:
        raise ValueError("Username và password không được để trống")
    users = _load_users()
    if username in users:
        raise ValueError(f"Username '{username}' đã tồn tại")
    users[username] = {
        "password_hash": _hash_password(password),
        "role": role,
        "created_at": datetime.utcnow().isoformat(),
    }
    _save_users(users)
    return {"username": username, "role": role}


def delete_user(username: str) -> bool:
    users = _load_users()
    if username not in users:
        return False
    # Không cho xóa admin cuối cùng
    admins = [u for u, d in users.items() if d["role"] == "admin"]
    if users[username]["role"] == "admin" and len(admins) <= 1:
        raise ValueError("Không thể xóa admin duy nhất")
    del users[username]
    _save_users(users)
    # Revoke sessions của user bị xóa
    to_remove = [t for t, s in _sessions.items() if s["username"] == username]
    for t in to_remove:
        _sessions.pop(t, None)
    return True


def list_users() -> list[dict]:
    users = _load_users()
    return [
        {
            "username": u,
            "role": d["role"],
            "created_at": d.get("created_at", ""),
        }
        for u, d in users.items()
    ]


def change_password(username: str, new_password: str) -> bool:
    users = _load_users()
    if username not in users:
        return False
    users[username]["password_hash"] = _hash_password(new_password)
    _save_users(users)
    return True
