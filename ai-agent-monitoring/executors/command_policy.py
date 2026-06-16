"""
Command allowlist and policy enforcement.
Only commands matching the allowlist are executed on remote hosts.
"""

import re
from config import config

# Blocklist — these are NEVER allowed regardless of allowlist
_BLOCKED_PATTERNS = [
    re.compile(r'\brm\s+-rf\b'),
    re.compile(r'\bmkfs\b'),
    re.compile(r'\bdd\s+if='),
    re.compile(r'\breboot\b'),
    re.compile(r'\bshutdown\b'),
    re.compile(r'\bkill\s+-9\b'),
    re.compile(r'\biptables\s+(-F|--flush)\b'),
    re.compile(r'>\s*/dev/sd'),
    re.compile(r'\bformat\s+c:'),
    re.compile(r'\bpasswd\b'),
    re.compile(r'\bchmod\s+777\b'),
    re.compile(r';\s*(rm|dd|mkfs|reboot|shutdown)'),  # chained dangerous commands
    re.compile(r'\|\s*(rm|dd|mkfs|reboot|shutdown)'),
]


class CommandPolicy:
    """Stateless policy enforcer. Can be instantiated for dependency injection."""

    def is_allowed(self, command: str) -> bool:
        return is_allowed(command)

    def get_commands_for_check_type(self, check_type: str) -> list[str]:
        return get_commands_for_check_type(check_type)


def _base_cmd(s: str) -> str:
    """Extract the executable name (first word, strip leading path)."""
    first = s.strip().lower().split()[0] if s.strip() else ""
    return first.split("/")[-1]  # /usr/bin/top -> top


def _has_path_arg(cmd: str) -> bool:
    """Return True if the command contains path arguments (args starting with '/')."""
    parts = cmd.strip().split()
    return any(p.startswith("/") for p in parts[1:])


def is_allowed(command: str) -> bool:
    """Return True if command is in allowlist and not blocked.

    Matching rules (evaluated in order, first match wins):
    1. Blocklist check -- always first; any match -> denied.
    2. Full prefix match: allowlist entry is a prefix of the command.
       e.g. "top -b -n 1" matches "top -b -n 1 | head -30"
    3. Base-executable match (flags-only entries only):
       When an allowlist entry has NO path arguments (only flags),
       any invocation of that executable with different flags is allowed.
       e.g. "top -b -n 1" (no paths) -> "top -bn1 | head -5" is allowed.
       SKIPPED for path-specific entries like "cat /etc/os-release" to prevent
       "cat /etc/shadow" from slipping through via base match.
    """
    # 1. Blocklist
    for pattern in _BLOCKED_PATTERNS:
        if pattern.search(command):
            return False

    cmd_lower = command.strip().lower()
    cmd_base = _base_cmd(cmd_lower)

    for allowed in config.ssh.allowed_commands:
        allowed_lower = allowed.lower().strip()

        # 2. Full prefix match
        if cmd_lower.startswith(allowed_lower):
            return True

        # 3. Base-executable match -- only for flag-only allowlist entries
        if (
            cmd_base
            and cmd_base == _base_cmd(allowed_lower)
            and not _has_path_arg(allowed_lower)
        ):
            return True

    return False


def get_commands_for_check_type(check_type: str) -> list[str]:
    """Map check_type (from chat intent) to safe diagnostic commands."""
    return get_commands_for_alert_type(check_type)


def get_commands_for_alert_type(alert_name: str) -> list[str]:
    """Map alert type to the relevant diagnostic commands."""
    name_lower = alert_name.lower()

    if any(k in name_lower for k in ["cpu", "load", "processor"]):
        return [
            "top -b -n 1 | head -n 30",
            "ps aux --sort=-%cpu | head -n 15",
            "uptime",
            "mpstat 1 3",
        ]
    elif any(k in name_lower for k in ["mem", "memory", "swap", "oom"]):
        return [
            "free -m",
            "vmstat 1 3",
            "ps aux --sort=-%mem | head -n 15",
            "dmesg | tail -n 30",
        ]
    elif any(k in name_lower for k in ["disk", "storage", "filesystem", "inode", "volume"]):
        return [
            "df -h",
            "df -ih",
            "du -sh /var/log/* 2>/dev/null | sort -h | tail -n 20",
            "lsblk",
        ]
    elif any(k in name_lower for k in ["network", "net", "latency", "connection", "tcp", "socket"]):
        return [
            "ss -tulpen",
            "ss -s",
            "ip addr",
            "ip route",
            "ping -c 4 8.8.8.8",
        ]
    elif any(k in name_lower for k in ["service", "down", "unavailable", "restart", "process"]):
        return [
            "systemctl status --no-pager",
            "journalctl -n 100 --no-pager",
            "ps aux",
        ]
    elif any(k in name_lower for k in ["error", "exception", "application", "app", "log"]):
        return [
            "ls -lh /var/log",
            "journalctl -n 100 --no-pager",
            "tail -n 100 /var/log/syslog",
            "tail -n 100 /var/log/auth.log",
        ]
    elif any(k in name_lower for k in ["os", "system", "version", "kernel", "info"]):
        return [
            "cat /etc/os-release",
            "uname -a",
            "uptime",
            "hostname",
        ]
    elif any(k in name_lower for k in ["port", "open port", "listen", "socket", "firewall"]):
        return [
            "ss -tuln",
            "ss -tulpen",
            "ip addr",
        ]
    elif any(k in name_lower for k in ["general", "overview", "all", "tổng quan"]):
        return [
            "cat /etc/os-release",
            "uname -a",
            "uptime",
            "free -h",
            "df -h",
            "ss -tuln",
            "ps aux --sort=-%cpu | head -n 15",
        ]
    else:
        # Generic fallback
        return [
            "uptime",
            "free -h",
            "df -h",
            "ps aux | head -n 20",
            "ss -tuln",
        ]
