"""
Monitoring Client — query active alerts từ Alertmanager và CheckMK.

Alertmanager: luôn bật (dành cho server)
CheckMK:      bị tắt khi config.monitoring.network_monitoring_enabled = false
"""

import json
import os
import urllib.error
import urllib.request
from typing import Optional

from config import config, settings


# ── Alertmanager ──────────────────────────────────────────────────────────────

def query_alertmanager_active(
    filter_instance: Optional[str] = None,
    alertmanager_url: Optional[str] = None,
) -> list[dict]:
    """Lấy danh sách alert đang active từ Alertmanager.

    Returns list of dicts:
        alertname, instance, severity, summary, labels, starts_at
    Raises ConnectionError nếu không thể kết nối.
    """
    if settings.mock_mode:
        return _mock_alertmanager_alerts(filter_instance)

    base = (alertmanager_url or config.monitoring.alertmanager_url).rstrip("/")
    endpoint = f"{base}/api/v2/alerts?active=true&silenced=false&inhibited=false"

    try:
        req = urllib.request.Request(endpoint, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Không thể kết nối Alertmanager ({base}): {exc}") from exc
    except Exception as exc:
        raise ConnectionError(f"Lỗi khi query Alertmanager: {exc}") from exc

    alerts = []
    for a in data:
        status = a.get("status", {})
        # Alertmanager v2 trả về state = active / suppressed / inhibited
        if status.get("state") != "active":
            continue
        labels = a.get("labels", {})
        annotations = a.get("annotations", {})
        instance = labels.get("instance", labels.get("host", ""))
        if filter_instance and instance != filter_instance:
            continue
        alerts.append({
            "alertname": labels.get("alertname", "Unknown"),
            "instance": instance,
            "severity": labels.get("severity", "unknown"),
            "summary": annotations.get("summary", annotations.get("message", "")),
            "labels": labels,
            "starts_at": a.get("startsAt", ""),
        })
    return alerts


def format_alertmanager_summary(alerts: list[dict]) -> str:
    """Format danh sách alert thành text dễ đọc cho LLM."""
    if not alerts:
        return "✅ Không có alert nào đang active trên hệ thống."
    lines = [f"⚠️ Có {len(alerts)} alert đang active:\n"]
    for a in alerts:
        sev = a.get("severity", "unknown").upper()
        name = a.get("alertname", "Unknown")
        inst = a.get("instance", "N/A")
        summ = a.get("summary", "")
        lines.append(f"• [{sev}] {name} @ {inst}" + (f" — {summ}" if summ else ""))
    return "\n".join(lines)


# ── CheckMK (NETWORK_MONITORING_ENABLED = false) ──────────────────────────────

def query_checkmk_active(filter_host: Optional[str] = None) -> list[dict]:
    """Lấy danh sách host/service down từ CheckMK.

    Tắt hoàn toàn khi config.monitoring.network_monitoring_enabled = false.
    Dùng automation user: CHECKMK_URL, CHECKMK_USERNAME, CHECKMK_AUTOMATION_SECRET.
    """
    # ── Feature flag — comment này để bật khi cần ──────────────────────────
    if not config.monitoring.network_monitoring_enabled:
        return []   # Network monitoring disabled
    # ───────────────────────────────────────────────────────────────────────

    import base64
    base_url = os.environ.get(config.checkmk.url_env, "").rstrip("/")
    username = os.environ.get(config.checkmk.username_env, "automation")
    secret = os.environ.get(config.checkmk.secret_env, "")

    if not base_url or not secret:
        raise EnvironmentError(
            f"{config.checkmk.url_env} và {config.checkmk.secret_env} phải được cấu hình."
        )

    # CheckMK REST API — lấy hosts có state != UP (0)
    endpoint = f"{base_url}/check_mk/api/1.0/domain-types/host/collections/all"
    credentials = base64.b64encode(f"{username}:{secret}".encode()).decode()
    req = urllib.request.Request(
        endpoint,
        headers={
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Không thể kết nối CheckMK ({base_url}): {exc}") from exc

    alerts = []
    for item in data.get("value", []):
        ext = item.get("extensions", {})
        state = ext.get("state", 0)
        if state == 0:   # UP — bỏ qua
            continue
        hostname = ext.get("name", "")
        if filter_host and hostname != filter_host:
            continue
        alerts.append({
            "hostname": hostname,
            "state": "DOWN" if state == 1 else "UNREACHABLE",
            "plugin_output": ext.get("plugin_output", ""),
            "labels": ext.get("labels", {}),
        })
    return alerts


def format_checkmk_summary(alerts: list[dict]) -> str:
    """Format danh sách CheckMK alerts thành text."""
    if not alerts:
        return "✅ Tất cả thiết bị mạng đang UP."
    lines = [f"⚠️ Có {len(alerts)} thiết bị mạng DOWN/UNREACHABLE:\n"]
    for a in alerts:
        lines.append(f"• [{a['state']}] {a['hostname']} — {a.get('plugin_output', '')[:120]}")
    return "\n".join(lines)


# ── Mock data ─────────────────────────────────────────────────────────────────

def _mock_alertmanager_alerts(filter_instance: Optional[str]) -> list[dict]:
    alerts = [
        {
            "alertname": "HighCPUUsage",
            "instance": "10.0.0.1:9100",
            "severity": "warning",
            "summary": "CPU usage > 80% for 5 minutes",
            "labels": {"job": "node", "env": "prod"},
            "starts_at": "2026-06-15T08:00:00Z",
        },
        {
            "alertname": "DiskSpaceLow",
            "instance": "10.0.0.10:9100",
            "severity": "critical",
            "summary": "Disk /dev/sda1 usage > 90%",
            "labels": {"job": "node", "env": "prod"},
            "starts_at": "2026-06-15T07:30:00Z",
        },
    ]
    if filter_instance:
        alerts = [a for a in alerts if a["instance"] == filter_instance]
    return alerts
