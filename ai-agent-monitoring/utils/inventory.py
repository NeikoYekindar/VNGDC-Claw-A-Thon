"""
Inventory — quản lý danh sách server và thiết bị mạng từ data/list.csv.

Fields: hostname, ip, type (server|network), monitoring_source (prometheus|checkmk|cacti)
"""

import csv
import io
from pathlib import Path
from typing import Optional

_CSV_PATH = Path(__file__).parent.parent / "data" / "list.csv"
_REQUIRED_FIELDS = {"hostname", "ip", "type", "monitoring_source"}


def load_inventory(filter_type: Optional[str] = None) -> list[dict]:
    """Load danh sách từ CSV. Tuỳ chọn filter theo type ('server' hoặc 'network')."""
    if not _CSV_PATH.exists():
        return []
    try:
        with open(_CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not _REQUIRED_FIELDS.issubset(set(reader.fieldnames)):
                return []
            rows = []
            for row in reader:
                entry = {
                    "hostname": row.get("hostname", "").strip(),
                    "ip": row.get("ip", "").strip(),
                    "type": row.get("type", "").strip().lower(),
                    "monitoring_source": row.get("monitoring_source", "").strip().lower(),
                }
                if not entry["hostname"] or not entry["ip"]:
                    continue
                if filter_type and entry["type"] != filter_type.lower():
                    continue
                rows.append(entry)
        return rows
    except Exception as exc:
        print(f"[inventory] Lỗi đọc {_CSV_PATH}: {exc}", flush=True)
        return []


def save_inventory(rows: list[dict]) -> None:
    """Ghi inventory ra CSV."""
    _CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["hostname", "ip", "type", "monitoring_source"]
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "hostname": row.get("hostname", ""),
                "ip": row.get("ip", ""),
                "type": row.get("type", ""),
                "monitoring_source": row.get("monitoring_source", ""),
            })


def import_csv(content: str) -> tuple[int, str]:
    """Parse và lưu CSV content từ upload.

    Returns:
        (row_count, error_message) — error_message rỗng nếu thành công.
    """
    reader = csv.DictReader(io.StringIO(content))
    fieldnames = set(reader.fieldnames or [])
    missing = _REQUIRED_FIELDS - fieldnames
    if missing:
        return 0, f"CSV thiếu các cột bắt buộc: {', '.join(sorted(missing))}"

    rows = []
    for i, row in enumerate(reader, 1):
        hostname = row.get("hostname", "").strip()
        ip = row.get("ip", "").strip()
        if not hostname or not ip:
            return 0, f"Dòng {i}: 'hostname' và 'ip' không được để trống."
        dev_type = row.get("type", "").strip().lower()
        if dev_type not in ("server", "network"):
            return 0, f"Dòng {i}: 'type' phải là 'server' hoặc 'network', nhận được '{dev_type}'."
        rows.append({
            "hostname": hostname,
            "ip": ip,
            "type": dev_type,
            "monitoring_source": row.get("monitoring_source", "").strip().lower(),
        })

    if not rows:
        return 0, "File CSV không có dòng dữ liệu nào."

    save_inventory(rows)
    return len(rows), ""


def get_servers() -> list[dict]:
    """Trả về danh sách server (type=server)."""
    return load_inventory(filter_type="server")


def get_network_devices() -> list[dict]:
    """Trả về danh sách thiết bị mạng (type=network)."""
    return load_inventory(filter_type="network")


def get_inventory_summary() -> dict:
    """Tóm tắt inventory cho context."""
    all_entries = load_inventory()
    servers = [e for e in all_entries if e["type"] == "server"]
    networks = [e for e in all_entries if e["type"] == "network"]
    return {
        "total": len(all_entries),
        "servers": len(servers),
        "network_devices": len(networks),
        "server_list": [f"{s['hostname']} ({s['ip']})" for s in servers],
        "network_list": [f"{n['hostname']} ({n['ip']})" for n in networks],
    }
