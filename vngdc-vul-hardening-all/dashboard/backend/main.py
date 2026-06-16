import asyncio
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import asynccontextmanager
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from io import BytesIO
from ipaddress import ip_address
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, init_db
from database import SessionLocal
from models import AppSetting, AgentChatMessage, CheckTask, Report, Server, VulnerabilityEnrichment, VulnerabilityScan
from parser import parse_output

AGENT_URL = os.environ.get("AGENT_URL", "").rstrip("/")
AGENT_INVOCATIONS_URL = (
    AGENT_URL if AGENT_URL.endswith("/invocations") else f"{AGENT_URL}/invocations"
) if AGENT_URL else ""
LOCAL_AGENT_ENABLED = os.environ.get("LOCAL_AGENT_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
AGENT_AVAILABLE = bool(AGENT_INVOCATIONS_URL or LOCAL_AGENT_ENABLED)
VULN_REFRESH_INTERVAL_SECONDS = int(os.environ.get("VULN_REFRESH_INTERVAL_SECONDS", "900"))
VULN_REFRESH_INCLUDE_ANALYSIS = os.environ.get("VULN_REFRESH_INCLUDE_ANALYSIS", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
VULN_REFRESH_SEND_REPORT = os.environ.get("VULN_REFRESH_SEND_REPORT", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
VULN_ENRICHMENT_ENABLED = os.environ.get("VULN_ENRICHMENT_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
VULN_ENRICHMENT_TTL_HOURS = int(os.environ.get("VULN_ENRICHMENT_TTL_HOURS", "24"))
VULN_ENRICHMENT_MAX_CVES = int(os.environ.get("VULN_ENRICHMENT_MAX_CVES", "150"))
VULN_ENRICHMENT_OSV_MAX_CVES = int(os.environ.get("VULN_ENRICHMENT_OSV_MAX_CVES", "30"))
EMERGING_CVE_CACHE_TTL_SECONDS = int(os.environ.get("EMERGING_CVE_CACHE_TTL_SECONDS", "3600"))
NVD_API_KEY = os.environ.get("NVD_API_KEY", "")
VULNERABILITY_SCHEDULE_KEY = "vulnerability_schedule"

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_URL = "https://api.first.org/data/v1/epss"
NVD_CVES_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
OSV_VULNS_URL = "https://api.osv.dev/v1/vulns"


_EMERGING_CVE_SOURCE_CACHE: dict[str, Any] = {
    "fetched_at": None,
    "days": None,
    "items": [],
    "errors": [],
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = None
    if AGENT_AVAILABLE:
        task = asyncio.create_task(_vulnerability_refresh_loop())
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(title="Hardening Dashboard API", lifespan=lifespan)


@app.get("/ping")
@app.post("/ping")
@app.get("/health")
async def ping():
    return {"status": "healthy"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ──────────────────────────────────────────────────────────────────

class ServerCreate(BaseModel):
    name: str
    host: str
    port: int = 22
    username: str
    password: str | None = None
    ssh_key: str | None = None
    os_type: str = "ubuntu"


class ServerResponse(BaseModel):
    id: str
    name: str
    host: str
    port: int
    username: str
    os_type: str
    created_at: datetime
    last_checked_at: datetime | None
    last_status: str | None

    model_config = {"from_attributes": True}


class ReportResponse(BaseModel):
    id: str
    server_id: str
    checked_at: datetime
    status: str | None
    sections: Any
    error: str | None
    duration_seconds: int | None
    analysis: str | None

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: str
    server_id: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    report_id: str | None
    error: str | None

    model_config = {"from_attributes": True}


class VulnerabilityScanResponse(BaseModel):
    id: str
    scanned_at: datetime
    status: str | None
    source: str | None
    agent_filter: str | None
    total: int | None
    fetched: int | None
    critical: int | None
    high: int | None
    medium: int | None
    low: int | None
    summary: Any
    items: Any
    analysis: str | None
    error: str | None
    duration_seconds: int | None

    model_config = {"from_attributes": True}


class VulnerabilityRefreshRequest(BaseModel):
    agent_name: str = ""
    include_analysis: bool = True
    send_report: bool = False


class VulnerabilityScheduleUpdate(BaseModel):
    enabled: bool
    interval_seconds: int = 900
    include_analysis: bool = True
    send_report: bool = True
    agent_name: str = ""


class VulnerabilityScheduleResponse(BaseModel):
    enabled: bool
    interval_seconds: int
    include_analysis: bool
    send_report: bool
    agent_name: str
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_status: str | None
    last_error: str | None
    updated_at: datetime | None


class VulnerabilitySummaryResponse(BaseModel):
    latest_scan_id: str | None
    scanned_at: datetime | None
    status: str
    source: str | None
    total: int
    fetched: int
    critical: int
    high: int
    medium: int
    low: int
    analysis: str | None
    error: str | None
    items: list[Any]


class VulnerabilityAssetResponse(BaseModel):
    server: ServerResponse
    latest_scan_id: str | None
    scanned_at: datetime | None
    status: str
    source: str | None
    total: int
    critical: int
    high: int
    medium: int
    low: int
    items: list[Any]
    assessment: Any
    error: str | None


class EmergingCveResponse(BaseModel):
    generated_at: datetime
    latest_scan_id: str | None
    scanned_at: datetime | None
    days: int
    total: int
    sources: list[str]
    errors: list[str]
    items: list[Any]


class AgentChatMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


def _clean_xml_text(value: Any) -> str:
    text = "" if value is None else str(value)
    return "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)


def _col_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_cell(row_index: int, col_index: int, value: Any) -> str:
    ref = f"{_col_name(col_index)}{row_index}"
    text = escape(_clean_xml_text(value))
    return f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>'


def _build_xlsx(rows: list[list[Any]], sheet_name: str = "Security Report") -> bytes:
    safe_sheet_name = "".join("_" if ch in "[]:*?/\\'" else ch for ch in sheet_name).strip()[:31] or "Report"
    safe_sheet_name = escape(safe_sheet_name)
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = "".join(_xlsx_cell(row_index, col_index, value) for col_index, value in enumerate(row, start=1))
        sheet_rows.append(f'<row r="{row_index}">{cells}</row>')

    worksheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>'
        f'{"".join(sheet_rows)}'
        '</sheetData>'
        '</worksheet>'
    )

    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""")
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        z.writestr("xl/workbook.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="{safe_sheet_name}" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""")
        z.writestr("xl/_rels/workbook.xml.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""")
        z.writestr("xl/worksheets/sheet1.xml", worksheet)
    return out.getvalue()


def _report_rows(server: Server, report: Report) -> list[list[Any]]:
    sections = report.sections or []
    rows: list[list[Any]] = [
        ["Hardening Report"],
        ["Server", f"{server.username}@{server.host}:{server.port}"],
        ["Server name", server.name],
        ["OS", server.os_type],
        ["Report ID", report.id],
        ["Checked at", report.checked_at.isoformat() if report.checked_at else ""],
        ["Status", report.status or ""],
        ["Duration seconds", report.duration_seconds or ""],
        [],
    ]

    if report.error:
        rows.extend([["Error"], [report.error], []])
    if report.analysis:
        rows.extend([["AI Analysis"], [report.analysis], []])

    rows.append(["Section", "Section status", "Pass", "Fail", "Warn", "Info", "Check level", "Check message"])
    for section in sections:
        if not isinstance(section, dict):
            rows.append(["Raw section", "", "", "", "", "", "", section])
            continue
        checks = section.get("checks") or []
        if not checks:
            rows.append([
                section.get("name", ""),
                section.get("status", ""),
                section.get("pass_count", 0),
                section.get("fail_count", 0),
                section.get("warn_count", 0),
                section.get("info_count", 0),
                "",
                "",
            ])
            continue
        for check in checks:
            rows.append([
                section.get("name", ""),
                section.get("status", ""),
                section.get("pass_count", 0),
                section.get("fail_count", 0),
                section.get("warn_count", 0),
                section.get("info_count", 0),
                check.get("level", "") if isinstance(check, dict) else "",
                check.get("message", check) if isinstance(check, dict) else check,
            ])
    return rows


def _ensure_report_parsed(report: Report) -> bool:
    if report.error or not report.raw_output:
        return False

    sections = report.sections or []
    if sections and report.status not in (None, "none"):
        return False

    parsed = parse_output(report.raw_output)
    if not parsed.get("sections"):
        return False

    report.sections = parsed["sections"]
    report.status = parsed["status"]
    return True


async def _sync_server_statuses(db: AsyncSession, servers: list[Server]) -> None:
    changed = False
    for server in servers:
        latest = (
            await db.execute(
                select(Report).where(Report.server_id == server.id).order_by(Report.checked_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        if not latest:
            continue

        changed = _ensure_report_parsed(latest) or changed
        if latest.status and server.last_status != latest.status:
            server.last_status = latest.status
            changed = True
        if latest.checked_at and server.last_checked_at != latest.checked_at:
            server.last_checked_at = latest.checked_at
            changed = True

    if changed:
        await db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run_check_bg(task_id: str, server_id: str):
    from database import SessionLocal
    from ssh_checker import run_check

    async with SessionLocal() as db:
        # Mark running
        task = await db.get(CheckTask, task_id)
        server = await db.get(Server, server_id)
        if not task or not server:
            return
        task.status = "running"
        await db.commit()

        started = time.time()
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: run_check(
                    server.host, server.port, server.username,
                    server.password, server.ssh_key, server.os_type,
                ),
            )
            report = Report(
                server_id=server_id,
                status=result["status"],
                sections=result["sections"],
                raw_output=result["raw_output"],
                duration_seconds=result["duration_seconds"],
                analysis=result.get("analysis"),
            )
            db.add(report)
            await db.flush()

            server.last_checked_at = datetime.now(timezone.utc)
            server.last_status = result["status"]
            task.status = "completed"
            task.completed_at = datetime.now(timezone.utc)
            task.report_id = report.id
        except Exception as exc:
            report = Report(
                server_id=server_id,
                status="error",
                sections=[],
                raw_output="",
                error=str(exc),
                duration_seconds=int(time.time() - started),
            )
            db.add(report)
            await db.flush()

            server.last_checked_at = datetime.now(timezone.utc)
            server.last_status = "error"
            task.status = "failed"
            task.error = str(exc)
            task.completed_at = datetime.now(timezone.utc)
            task.report_id = report.id

        await db.commit()


def _scan_counts(result: dict[str, Any]) -> dict[str, int]:
    summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
    return {
        "critical": _int_value(summary.get("Critical") or summary.get("critical")),
        "high": _int_value(summary.get("High") or summary.get("high")),
        "medium": _int_value(summary.get("Medium") or summary.get("medium")),
        "low": _int_value(summary.get("Low") or summary.get("low")),
    }


def _scan_items(result: dict[str, Any]) -> list[Any]:
    items = result.get("items")
    if isinstance(items, list):
        return items
    merged: list[Any] = []
    for key in ("critical", "high"):
        value = result.get(key)
        if isinstance(value, list):
            merged.extend(value)
    return merged


def _cve_id(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text.startswith("CVE-") and len(text.split("-")) >= 3:
        return text
    return ""


def _batched(values: list[str], size: int) -> list[list[str]]:
    safe_size = max(1, size)
    return [values[index:index + safe_size] for index in range(0, len(values), safe_size)]


def _json_request_public(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = 12,
) -> dict[str, Any]:
    request_headers = {"Accept": "application/json", "User-Agent": "vngdc-security-agent/1.0"}
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, headers=request_headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        # External intel is best-effort. Wazuh scan persistence must not fail
        # because one enrichment source throttled, missed a CVE, or returned 5xx.
        if exc.code not in {404, 429}:
            print(f"[vuln-enrichment] {url} failed with HTTP {exc.code}")
        return {}
    except Exception as exc:
        print(f"[vuln-enrichment] {url} failed: {exc}")
        return {}


def _unique_cves(items: list[Any], limit: int) -> list[str]:
    cves: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        cve = _cve_id(item.get("cve"))
        if cve and cve not in cves:
            cves.append(cve)
        if len(cves) >= max(1, limit):
            break
    return cves


def _url_list(raw: Any) -> list[str]:
    values: list[Any]
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, dict):
        values = list(raw.values())
    elif isinstance(raw, str):
        values = raw.replace(",", " ").split()
    else:
        values = []

    urls: list[str] = []
    for value in values:
        if isinstance(value, dict):
            value = value.get("url") or value.get("href") or ""
        text = str(value or "").strip().strip(",;")
        if text.startswith(("http://", "https://")) and text not in urls:
            urls.append(text)
    return urls


def _fetch_cisa_kev() -> dict[str, dict[str, Any]]:
    data = _json_request_public(CISA_KEV_URL, timeout=20)
    rows = data.get("vulnerabilities") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return {}

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        cve = _cve_id(row.get("cveID") or row.get("cve"))
        if cve:
            result[cve] = {
                "cve": cve,
                "vendor_project": row.get("vendorProject"),
                "product": row.get("product"),
                "name": row.get("vulnerabilityName"),
                "date_added": row.get("dateAdded"),
                "due_date": row.get("dueDate"),
                "required_action": row.get("requiredAction"),
                "notes": row.get("notes"),
                "catalog_url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
            }
    return result


def _fetch_epss(cves: list[str]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for batch in _batched(cves, 100):
        query = urllib.parse.urlencode({"cve": ",".join(batch)}, safe=",")
        data = _json_request_public(f"{EPSS_URL}?{query}", timeout=15)
        rows = data.get("data") if isinstance(data, dict) else []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            cve = _cve_id(row.get("cve"))
            if not cve:
                continue
            try:
                epss = float(row.get("epss") or 0)
            except (TypeError, ValueError):
                epss = 0.0
            try:
                percentile = float(row.get("percentile") or 0)
            except (TypeError, ValueError):
                percentile = 0.0
            result[cve] = {"epss": epss, "percentile": percentile}
    return result


def _english_description(cve: dict[str, Any]) -> str:
    descriptions = cve.get("descriptions")
    if isinstance(descriptions, list):
        for item in descriptions:
            if isinstance(item, dict) and str(item.get("lang", "")).lower() == "en":
                return str(item.get("value") or "")
    return ""


def _extract_cvss(cve: dict[str, Any]) -> dict[str, Any]:
    metrics = cve.get("metrics") if isinstance(cve.get("metrics"), dict) else {}
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        values = metrics.get(key)
        if not isinstance(values, list) or not values:
            continue
        first = values[0] if isinstance(values[0], dict) else {}
        data = first.get("cvssData") if isinstance(first.get("cvssData"), dict) else {}
        if not data:
            continue
        return {
            "version": data.get("version") or key,
            "score": data.get("baseScore"),
            "severity": data.get("baseSeverity") or first.get("baseSeverity"),
            "vector": data.get("vectorString"),
        }
    return {}


def _extract_references(cve: dict[str, Any]) -> list[str]:
    refs = cve.get("references")
    if isinstance(refs, dict):
        refs = refs.get("referenceData")
    if not isinstance(refs, list):
        return []
    return _url_list(refs)


def _extract_weaknesses(cve: dict[str, Any]) -> list[str]:
    values: list[str] = []
    weaknesses = cve.get("weaknesses")
    if not isinstance(weaknesses, list):
        return values
    for weakness in weaknesses:
        if not isinstance(weakness, dict):
            continue
        descriptions = weakness.get("description")
        if not isinstance(descriptions, list):
            continue
        for desc in descriptions:
            if not isinstance(desc, dict):
                continue
            value = str(desc.get("value") or "").strip()
            if value and value not in values:
                values.append(value)
    return values


def _fetch_nvd(cves: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    headers = {"apiKey": NVD_API_KEY} if NVD_API_KEY else None
    for batch in _batched(cves, 100):
        query = urllib.parse.urlencode({"cveIds": ",".join(batch)}, safe=",")
        data = _json_request_public(f"{NVD_CVES_URL}?{query}", headers=headers, timeout=25)
        vulnerabilities = data.get("vulnerabilities") if isinstance(data, dict) else []
        if not isinstance(vulnerabilities, list):
            continue
        for entry in vulnerabilities:
            cve = entry.get("cve") if isinstance(entry, dict) else {}
            if not isinstance(cve, dict):
                continue
            cve_id = _cve_id(cve.get("id"))
            if not cve_id:
                continue
            cvss = _extract_cvss(cve)
            result[cve_id] = {
                "description": _english_description(cve),
                "published": cve.get("published"),
                "last_modified": cve.get("lastModified"),
                "cvss": cvss,
                "weaknesses": _extract_weaknesses(cve),
                "references": _extract_references(cve),
                "known_exploited": bool(cve.get("cisaExploitAdd")),
                "cisa": {
                    "date_added": cve.get("cisaExploitAdd"),
                    "required_action": cve.get("cisaRequiredAction"),
                    "vulnerability_name": cve.get("cisaVulnerabilityName"),
                } if cve.get("cisaExploitAdd") else None,
            }
    return result


def _extract_osv_fixed_versions(data: dict[str, Any]) -> list[str]:
    fixed: list[str] = []
    affected = data.get("affected")
    if not isinstance(affected, list):
        return fixed
    for record in affected:
        if not isinstance(record, dict):
            continue
        ranges = record.get("ranges")
        if not isinstance(ranges, list):
            continue
        for item in ranges:
            if not isinstance(item, dict):
                continue
            events = item.get("events")
            if not isinstance(events, list):
                continue
            for event in events:
                if isinstance(event, dict) and event.get("fixed"):
                    value = str(event.get("fixed") or "").strip()
                    if value and value not in fixed:
                        fixed.append(value)
    return fixed


def _fetch_osv(cves: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for cve in cves[: max(0, VULN_ENRICHMENT_OSV_MAX_CVES)]:
        data = _json_request_public(f"{OSV_VULNS_URL}/{urllib.parse.quote(cve, safe='-')}", timeout=15)
        if not data:
            continue
        refs = data.get("references") if isinstance(data.get("references"), list) else []
        result[cve] = {
            "summary": data.get("summary"),
            "details": data.get("details"),
            "modified": data.get("modified"),
            "published": data.get("published"),
            "aliases": data.get("aliases") if isinstance(data.get("aliases"), list) else [],
            "fixed_versions": _extract_osv_fixed_versions(data),
            "references": _url_list(refs),
        }
    return result


def _fetch_live_enrichment(cves: list[str]) -> dict[str, dict[str, Any]]:
    if not cves:
        return {}

    kev = _fetch_cisa_kev()
    epss = _fetch_epss(cves)
    nvd = _fetch_nvd(cves)
    osv = _fetch_osv(cves)

    result: dict[str, dict[str, Any]] = {}
    for cve in cves:
        result[cve] = {
            "cve": cve,
            "kev": kev.get(cve),
            "epss": epss.get(cve),
            "nvd": nvd.get(cve),
            "osv": osv.get(cve),
        }
    return result


def _parse_date_value(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        normalized = text.replace("Z", "+00:00")
        if len(normalized) == 10:
            normalized = f"{normalized}T00:00:00+00:00"
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _recent_nvd_candidates(days: int, max_results: int = 120) -> tuple[list[dict[str, Any]], str | None]:
    now = _utc_now()
    start = now - timedelta(days=max(1, min(days, 120)))
    query = urllib.parse.urlencode({
        "pubStartDate": start.strftime("%Y-%m-%dT%H:%M:%S.000"),
        "pubEndDate": now.strftime("%Y-%m-%dT%H:%M:%S.000"),
        "resultsPerPage": str(max(1, min(max_results, 2000))),
    })
    data = _json_request_public(
        f"{NVD_CVES_URL}?{query}",
        headers={"apiKey": NVD_API_KEY} if NVD_API_KEY else None,
        timeout=25,
    )
    rows = data.get("vulnerabilities") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        return [], "Không lấy được dữ liệu NVD recent CVE"

    items: list[dict[str, Any]] = []
    for entry in rows:
        cve = entry.get("cve") if isinstance(entry, dict) else {}
        if not isinstance(cve, dict):
            continue
        cve_id = _cve_id(cve.get("id"))
        if not cve_id:
            continue
        cvss = _extract_cvss(cve)
        severity = _severity_label(cvss.get("severity"))
        if severity not in {"Critical", "High"}:
            continue
        items.append({
            "cve": cve_id,
            "severity": severity,
            "cvss": _score_value(cvss.get("score")),
            "title": cve.get("cisaVulnerabilityName") or _english_description(cve)[:220],
            "description": _english_description(cve),
            "published": cve.get("published"),
            "last_modified": cve.get("lastModified"),
            "known_exploited": bool(cve.get("cisaExploitAdd")),
            "date_added": cve.get("cisaExploitAdd"),
            "source": "NVD",
            "references": _extract_references(cve),
            "vendor_project": "",
            "product": "",
        })
    return items, None


def _kev_candidates(limit: int = 120) -> tuple[list[dict[str, Any]], str | None]:
    kev = _fetch_cisa_kev()
    if not kev:
        return [], "Không lấy được dữ liệu CISA KEV"
    rows = sorted(
        kev.values(),
        key=lambda item: _parse_date_value(item.get("date_added")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:max(1, limit)]
    return [
        {
            "cve": item.get("cve"),
            "severity": "Critical",
            "cvss": 0,
            "title": item.get("name") or item.get("cve"),
            "description": item.get("required_action") or item.get("notes") or "",
            "published": None,
            "last_modified": None,
            "known_exploited": True,
            "date_added": item.get("date_added"),
            "due_date": item.get("due_date"),
            "source": "CISA KEV",
            "references": [item.get("catalog_url")] if item.get("catalog_url") else [],
            "vendor_project": item.get("vendor_project") or "",
            "product": item.get("product") or "",
        }
        for item in rows
        if item.get("cve")
    ], None


def _emerging_source_candidates(days: int) -> tuple[list[dict[str, Any]], list[str]]:
    now = _utc_now()
    fetched_at = _EMERGING_CVE_SOURCE_CACHE.get("fetched_at")
    if (
        isinstance(fetched_at, datetime)
        and _EMERGING_CVE_SOURCE_CACHE.get("days") == days
        and fetched_at >= now - timedelta(seconds=max(60, EMERGING_CVE_CACHE_TTL_SECONDS))
    ):
        return list(_EMERGING_CVE_SOURCE_CACHE.get("items") or []), list(_EMERGING_CVE_SOURCE_CACHE.get("errors") or [])

    errors: list[str] = []
    kev_items, kev_error = _kev_candidates()
    if kev_error:
        errors.append(kev_error)
    nvd_items, nvd_error = _recent_nvd_candidates(days)
    if nvd_error:
        errors.append(nvd_error)

    merged: dict[str, dict[str, Any]] = {}
    for item in [*kev_items, *nvd_items]:
        cve = _cve_id(item.get("cve"))
        if not cve:
            continue
        current = merged.get(cve, {})
        combined = {**current, **item}
        combined["known_exploited"] = bool(current.get("known_exploited") or item.get("known_exploited"))
        combined["source"] = ", ".join(dict.fromkeys(
            source for source in [_text(current.get("source")), _text(item.get("source"))] if source
        ))
        combined["references"] = list(dict.fromkeys([
            *(_url_list(current.get("references")) if current else []),
            *_url_list(item.get("references")),
        ]))
        merged[cve] = combined

    cves = list(merged.keys())[:100]
    epss = _fetch_epss(cves)
    for cve, data in epss.items():
        if cve in merged:
            merged[cve]["epss"] = data.get("epss", 0)
            merged[cve]["epss_percentile"] = data.get("percentile", 0)

    items = list(merged.values())
    _EMERGING_CVE_SOURCE_CACHE.update({
        "fetched_at": now,
        "days": days,
        "items": items,
        "errors": errors,
    })
    return items, errors


def _server_os_terms(servers: list[Server]) -> set[str]:
    terms: set[str] = set()
    for server in servers:
        os_text = _lower(server.os_type)
        if os_text:
            terms.add(os_text)
        if "ubuntu" in os_text:
            terms.update({"linux", "ubuntu", "debian"})
        if "windows" in os_text:
            terms.update({"windows", "microsoft"})
        if "junos" in os_text:
            terms.update({"junos", "juniper"})
    return terms


def _candidate_relevance(candidate: dict[str, Any], scan_items: list[Any], servers: list[Server]) -> dict[str, Any]:
    cve = _cve_id(candidate.get("cve"))
    matched_items = [
        item for item in scan_items
        if isinstance(item, dict) and _cve_id(item.get("cve")) == cve
    ]
    if matched_items:
        assets = sorted({
            _text(item.get("agent") or item.get("host") or item.get("hostname") or item.get("agent_id"))
            for item in matched_items
            if _text(item.get("agent") or item.get("host") or item.get("hostname") or item.get("agent_id"))
        })
        packages = sorted({
            _text(item.get("package"))
            for item in matched_items
            if _text(item.get("package"))
        })
        return {
            "relation": "direct",
            "relation_label": "Đang xuất hiện trong hệ thống",
            "affected_assets": assets,
            "matched_packages": packages,
            "analysis": (
                f"CVE này đang có trong latest Wazuh scan trên {len(assets) or len(matched_items)} asset. "
                "Cần ưu tiên kiểm tra bản vá và chạy lại scan sau xử lý."
            ),
        }

    text = _lower(" ".join([
        _text(candidate.get("title")),
        _text(candidate.get("description")),
        _text(candidate.get("vendor_project")),
        _text(candidate.get("product")),
    ]))
    os_hits = sorted(term for term in _server_os_terms(servers) if len(term) >= 4 and term in text)
    package_terms = {
        _lower(item.get("package"))
        for item in scan_items
        if isinstance(item, dict) and len(_lower(item.get("package"))) >= 4
    }
    package_hits = sorted(package for package in package_terms if package and package in text)[:8]
    if os_hits or package_hits:
        detail = []
        if os_hits:
            detail.append(f"OS liên quan: {', '.join(os_hits[:4])}")
        if package_hits:
            detail.append(f"package trùng ngữ cảnh: {', '.join(package_hits)}")
        return {
            "relation": "possible",
            "relation_label": "Có khả năng liên quan",
            "affected_assets": [],
            "matched_packages": package_hits,
            "analysis": (
                "Chưa thấy CVE này trong latest Wazuh finding, nhưng có tín hiệu trùng với inventory/ngữ cảnh hệ thống "
                f"({'; '.join(detail)}). Cần xác minh bằng Wazuh package inventory hoặc vendor advisory."
            ),
        }

    return {
        "relation": "not_seen",
        "relation_label": "Chưa thấy bằng chứng liên quan",
        "affected_assets": [],
        "matched_packages": [],
        "analysis": (
            "Chưa thấy CVE này trong latest Wazuh finding và chưa có tín hiệu khớp rõ với OS/package hiện có. "
            "Tiếp tục theo dõi feed và xác minh nếu hệ thống có sản phẩm/vendor tương ứng."
        ),
    }


def _emerging_risk_score(candidate: dict[str, Any], relevance: dict[str, Any]) -> int:
    severity = _severity_label(candidate.get("severity"))
    severity_points = {"Critical": 40, "High": 30, "Medium": 15, "Low": 5}[severity]
    cvss = _score_value(candidate.get("cvss"))
    epss = _score_value(candidate.get("epss"))
    relation_bonus = {"direct": 25, "possible": 10, "not_seen": 0}.get(_text(relevance.get("relation")), 0)
    total = (
        severity_points
        + min(cvss, 10.0) * 2.5
        + min(max(epss, 0.0), 1.0) * 20.0
        + (25 if candidate.get("known_exploited") else 0)
        + relation_bonus
    )
    return max(0, min(100, int(round(total))))


def _emerging_cve_items(
    candidates: list[dict[str, Any]],
    scan_items: list[Any],
    servers: list[Server],
    limit: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        relevance = _candidate_relevance(candidate, scan_items, servers)
        risk_score = _emerging_risk_score(candidate, relevance)
        epss = _score_value(candidate.get("epss"))
        rows.append({
            **candidate,
            "severity": _severity_label(candidate.get("severity")),
            "risk_score": risk_score,
            "risk_label": _risk_label(risk_score),
            "epss": epss,
            "epss_percentile": _score_value(candidate.get("epss_percentile")),
            "exploit_likelihood": _exploit_likelihood_from_values(bool(candidate.get("known_exploited")), epss),
            "recommendation": (
                "Ưu tiên xử lý ngay vì CVE đã xuất hiện trong Wazuh scan."
                if relevance["relation"] == "direct"
                else "Theo dõi sát và xác minh package/vendor trong hệ thống trước khi mở change vá."
                if relevance["relation"] == "possible"
                else "Theo dõi feed; chưa cần hành động vá nếu không có sản phẩm/package liên quan."
            ),
            **relevance,
        })

    rows.sort(
        key=lambda item: (
            {"direct": 3, "possible": 2, "not_seen": 1}.get(item.get("relation"), 0),
            bool(item.get("known_exploited")),
            _int_value(item.get("risk_score")),
            _score_value(item.get("cvss")),
            _parse_date_value(item.get("date_added") or item.get("published")) or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return rows[:max(1, min(limit, 50))]


def _is_fresh_enrichment(row: VulnerabilityEnrichment, now: datetime) -> bool:
    fetched_at = row.fetched_at
    if not fetched_at:
        return False
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    ttl = timedelta(hours=max(1, VULN_ENRICHMENT_TTL_HOURS))
    return fetched_at >= now - ttl


def _host_is_public(host: Any) -> bool:
    try:
        parsed = ip_address(str(host or "").strip())
    except ValueError:
        return False
    return not (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_multicast
        or parsed.is_reserved
        or parsed.is_unspecified
    )


def _asset_criticality_points(server: Server | None) -> int:
    if not server:
        return 0
    name = _lower(server.name)
    points = 0
    if any(token in name for token in ("prod", "production", "db", "database", "edge", "gateway", "public")):
        points += 10
    if server.last_status in {"none", "error"}:
        points += 8
    elif server.last_status == "partial":
        points += 4
    elif server.last_status == "hardened":
        points += 1
    return points


def _public_exposure_points(server: Server | None) -> int:
    return 12 if server and _host_is_public(server.host) else 0


def _exploit_likelihood_from_values(known_exploited: bool, epss: float) -> str:
    if known_exploited:
        return "Known exploited"
    if epss >= 0.5:
        return "High"
    if epss >= 0.1:
        return "Medium"
    if epss > 0:
        return "Low"
    return "Unknown"


def _exploit_likelihood_vi(value: Any) -> str:
    text = _text(value)
    return {
        "Known exploited": "Đã ghi nhận khai thác",
        "High": "Cao",
        "Medium": "Trung bình",
        "Low": "Thấp",
        "Unknown": "Chưa xác định",
        "": "Chưa xác định",
    }.get(text, text)


def _severity_vi(value: Any) -> str:
    return {
        "Critical": "Nghiêm trọng",
        "High": "Cao",
        "Medium": "Trung bình",
        "Low": "Thấp",
    }[_severity_label(value)]


def _risk_label(score: int) -> str:
    if score >= 85:
        return "Critical"
    if score >= 65:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def _patch_sla(severity: str, known_exploited: bool, epss: float, risk_score: int) -> tuple[str, int]:
    if known_exploited or risk_score >= 85:
        return "24h", 24
    if severity == "Critical":
        return "48h", 48
    if severity == "High" or epss >= 0.1 or risk_score >= 65:
        return "72h", 72
    if severity == "Medium":
        return "14d", 336
    return "30d", 720


def _risk_score(item: dict[str, Any], server: Server | None = None) -> int:
    severity = _severity_label(item.get("severity"))
    severity_points = {"Critical": 40, "High": 28, "Medium": 14, "Low": 5}[severity]
    score = _score_value(item.get("nvd_cvss_score") or item.get("score"))
    epss = _score_value(item.get("epss"))
    known_exploited = bool(item.get("known_exploited"))
    total = (
        severity_points
        + min(score, 10.0) * 2.0
        + min(max(epss, 0.0), 1.0) * 25.0
        + (25 if known_exploited else 0)
        + _asset_criticality_points(server)
        + _public_exposure_points(server)
    )
    return max(0, min(100, int(round(total))))


def _patch_plan_for_item(item: dict[str, Any], server: Server | None = None) -> list[str]:
    package = _text(item.get("package")) or "package bị ảnh hưởng"
    fixed_version = _text(item.get("fixed_version"))
    os_text = _lower(item.get("os") or (server.os_type if server else ""))
    cve = _text(item.get("cve")) or "CVE này"

    if "ubuntu" in os_text or "debian" in os_text:
        target = f"{package}={fixed_version}" if fixed_version and fixed_version != "Vendor advisory required" else package
        return [
            f"Xác nhận `{package}` thuộc dịch vụ nào và đánh giá tác động vận hành trước khi vá.",
            "Chạy `sudo apt update` rồi kiểm tra phiên bản ứng viên bằng `apt-cache policy {}`.".format(package),
            f"Vá bằng `sudo apt install --only-upgrade {target}` hoặc bản vá đã được phê duyệt từ repository/vendor nội bộ.",
            "Khởi động lại dịch vụ bị ảnh hưởng nếu bản cập nhật yêu cầu, sau đó kiểm tra health check ứng dụng.",
            f"Chạy lại Wazuh vulnerability scan và xác nhận `{cve}` không còn xuất hiện trên asset.",
        ]
    if "windows" in os_text:
        return [
            f"Mở advisory MSRC cho `{cve}` và xác định KB hoặc product update cần cài.",
            "Triển khai bản cập nhật qua Windows Update, WSUS/SCCM hoặc nền tảng patch management đã được phê duyệt.",
            "Khởi động lại host nếu cần và xác minh bằng `Get-HotFix` hoặc công cụ inventory của vendor.",
            f"Chạy lại Wazuh vulnerability scan và xác nhận `{cve}` không còn xuất hiện trên asset.",
        ]
    return [
        f"Rà soát vendor advisory và release notes bản vá cho `{package}`.",
        "Nâng cấp package bị ảnh hưởng qua package manager hoặc kênh vendor được hỗ trợ.",
        "Khởi động lại dịch vụ phụ thuộc nếu cần và xác minh trạng thái dịch vụ.",
        f"Chạy lại Wazuh vulnerability scan và xác nhận `{cve}` đã được xử lý.",
    ]


def _merge_vulnerability_intel(
    item: Any,
    intel: dict[str, Any] | None = None,
    server: Server | None = None,
) -> dict[str, Any]:
    row = dict(item) if isinstance(item, dict) else {"raw": item}
    intel = intel or {}
    nvd = intel.get("nvd") if isinstance(intel.get("nvd"), dict) else {}
    osv = intel.get("osv") if isinstance(intel.get("osv"), dict) else {}
    epss_data = intel.get("epss") if isinstance(intel.get("epss"), dict) else {}
    kev = intel.get("kev") if isinstance(intel.get("kev"), dict) else None

    cve = _cve_id(row.get("cve")) or _text(row.get("cve")) or "N/A"
    severity = _severity_label(row.get("severity") or nvd.get("cvss", {}).get("severity"))
    cvss = nvd.get("cvss") if isinstance(nvd.get("cvss"), dict) else {}
    nvd_score = _score_value(cvss.get("score"))
    epss_score = _score_value(epss_data.get("epss") if epss_data else row.get("epss"))
    epss_percentile = _score_value(epss_data.get("percentile") if epss_data else row.get("epss_percentile"))
    known_exploited = bool(kev or nvd.get("known_exploited") or row.get("known_exploited"))

    references = _url_list(row.get("reference"))
    for source_urls in (nvd.get("references"), osv.get("references")):
        for url in _url_list(source_urls):
            if url not in references:
                references.append(url)
    if kev and kev.get("catalog_url") and kev["catalog_url"] not in references:
        references.append(kev["catalog_url"])

    fixed_versions = []
    if isinstance(osv.get("fixed_versions"), list):
        fixed_versions = [str(value) for value in osv["fixed_versions"] if value]
    fixed_version = fixed_versions[0] if fixed_versions else _text(row.get("fixed_version")) or "Vendor advisory required"

    row["cve"] = cve
    row["severity"] = severity
    row["score"] = row.get("score") or (nvd_score if nvd_score else "")
    row["description"] = row.get("description") or row.get("title") or nvd.get("description") or osv.get("summary") or ""
    row["title"] = row.get("title") or nvd.get("description") or osv.get("summary") or ""
    row["reference"] = references
    row["known_exploited"] = known_exploited
    row["kev"] = kev
    row["epss"] = epss_score
    row["epss_percentile"] = epss_percentile
    row["exploit_likelihood"] = _exploit_likelihood_from_values(known_exploited, epss_score)
    row["nvd_cvss_score"] = nvd_score or row.get("nvd_cvss_score") or ""
    row["nvd_cvss_vector"] = cvss.get("vector") or row.get("nvd_cvss_vector") or ""
    row["nvd_severity"] = cvss.get("severity") or row.get("nvd_severity") or ""
    row["cwe"] = nvd.get("weaknesses") if isinstance(nvd.get("weaknesses"), list) else row.get("cwe") or []
    row["fixed_versions"] = fixed_versions
    row["fixed_version"] = fixed_version
    row["risk_score"] = _risk_score(row, server)
    row["risk_label"] = _risk_label(_int_value(row.get("risk_score")))
    sla, sla_hours = _patch_sla(severity, known_exploited, epss_score, _int_value(row.get("risk_score")))
    row["patch_sla"] = sla
    row["patch_sla_hours"] = sla_hours
    row["patch_plan"] = _patch_plan_for_item(row, server)
    return row


async def _enrich_scan_items(db: AsyncSession, items: list[Any]) -> list[dict[str, Any]]:
    normalized = [dict(item) if isinstance(item, dict) else {"raw": item} for item in items]
    if not normalized:
        return []

    cves = _unique_cves(normalized, VULN_ENRICHMENT_MAX_CVES)
    if not VULN_ENRICHMENT_ENABLED or not cves:
        return [_merge_vulnerability_intel(item) for item in normalized]

    now = datetime.now(timezone.utc)
    cached_rows = (
        await db.execute(select(VulnerabilityEnrichment).where(VulnerabilityEnrichment.cve.in_(cves)))
    ).scalars().all()
    cached = {row.cve: row for row in cached_rows}

    enrichment: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for cve in cves:
        row = cached.get(cve)
        if row and _is_fresh_enrichment(row, now) and isinstance(row.data, dict):
            enrichment[cve] = row.data
        else:
            missing.append(cve)

    if missing:
        fetched = await asyncio.get_event_loop().run_in_executor(None, lambda: _fetch_live_enrichment(missing))
        for cve, data in fetched.items():
            if not isinstance(data, dict):
                continue
            data["fetched_at"] = now.isoformat()
            enrichment[cve] = data
            row = cached.get(cve)
            if row:
                row.fetched_at = now
                row.data = data
            else:
                db.add(VulnerabilityEnrichment(cve=cve, fetched_at=now, data=data))
        await db.flush()

    return [
        _merge_vulnerability_intel(item, enrichment.get(_cve_id(item.get("cve")) or ""))
        for item in normalized
    ]


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _severity_label(value: Any) -> str:
    text = _text(value).capitalize()
    return text if text in {"Critical", "High", "Medium", "Low"} else "Low"


def _severity_rank(value: Any) -> int:
    return {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}.get(_severity_label(value), 0)


def _score_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int_value(value: Any, default: int = 0) -> int:
    if value in (None, ""):
        return default
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _item_matches_server(item: Any, server: Server) -> bool:
    if not isinstance(item, dict):
        return False

    server_name = _lower(server.name)
    server_host = _lower(server.host)
    candidates = {
        _lower(item.get("agent")),
        _lower(item.get("agent_id")),
        _lower(item.get("host")),
        _lower(item.get("hostname")),
    }
    candidates.discard("")

    if server_name in candidates or server_host in candidates:
        return True

    # Wazuh agent names are often FQDNs while dashboard names are short names.
    # Match only exact names or FQDN boundaries to avoid SERVER2 inheriting
    # SERVER findings.
    return any(
        len(candidate) >= 4 and (candidate.startswith(f"{server_name}.") or server_name.startswith(f"{candidate}."))
        for candidate in candidates
    )


def _recommendation_for_item(item: dict[str, Any]) -> str:
    cve = _text(item.get("cve")) or "CVE"
    package = _text(item.get("package")) or "affected package"
    severity = _severity_label(item.get("severity"))

    prefix = {
        "Critical": "Xử lý ngay trong vòng 24 giờ nếu asset đang phục vụ production hoặc có bề mặt truy cập mạng.",
        "High": "Ưu tiên xử lý trong chu kỳ vá gần nhất, không nên để quá 72 giờ với asset quan trọng.",
        "Medium": "Đưa vào lịch vá định kỳ và kiểm tra điều kiện khai thác trước khi chấp nhận rủi ro.",
        "Low": "Theo dõi và xử lý cùng đợt cập nhật hệ thống tiếp theo.",
    }[severity]

    return (
        f"{prefix} Cập nhật package `{package}` lên bản vá mới nhất từ repository/vendor, "
        f"sau đó kiểm thử dịch vụ phụ thuộc và chạy lại Wazuh scan để xác nhận `{cve}` không còn xuất hiện. "
        "Nếu chưa có bản vá, ghi nhận exception có thời hạn, giảm exposure bằng firewall/segmentation và theo dõi advisory chính thức."
    )


def _enrich_vulnerability_item(item: Any) -> dict[str, Any]:
    row = dict(item) if isinstance(item, dict) else {"raw": item}
    severity = _severity_label(row.get("severity"))
    score = _score_value(row.get("score"))
    cve = _text(row.get("cve")) or "N/A"
    package = _text(row.get("package")) or "unknown"
    version = _text(row.get("version")) or "unknown"

    row["severity"] = severity
    row["risk_priority"] = "P1" if severity == "Critical" else "P2" if severity == "High" else "P3"
    row["agent_assessment"] = (
        f"{row['risk_priority']} - {severity} vulnerability `{cve}` ảnh hưởng package `{package}` "
        f"phiên bản `{version}`"
        + (f", CVSS {score:g}" if score else "")
        + "."
    )
    row["recommendation"] = _recommendation_for_item(row)
    return row


def _asset_vulnerability_assessment(server: Server, items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    packages: dict[str, int] = {}
    for item in items:
        severity = _severity_label(item.get("severity"))
        counts[severity] += 1
        package = _text(item.get("package")) or "unknown"
        packages[package] = packages.get(package, 0) + 1

    if counts["Critical"] > 0:
        priority = "P1"
        verdict = "Cần xử lý ngay"
        summary = (
            f"{server.name} có {counts['Critical']} CVE Critical và {counts['High']} CVE High. "
            "Đây là asset cần ưu tiên vá trước trong danh sách hiện tại."
        )
    elif counts["High"] > 0:
        priority = "P2"
        verdict = "Cần rà soát và vá sớm"
        summary = (
            f"{server.name} không có Critical trong dữ liệu hiện tại nhưng có {counts['High']} CVE High. "
            "Cần kiểm tra exposure và lên lịch vá sớm."
        )
    elif counts["Medium"] > 0 or counts["Low"] > 0:
        priority = "P3"
        verdict = "Theo dõi trong chu kỳ vá định kỳ"
        summary = (
            f"{server.name} chỉ có CVE Medium/Low trong dữ liệu hiện tại. "
            "Có thể xử lý theo lịch bảo trì nếu asset không public-facing."
        )
    else:
        priority = "OK"
        verdict = "Chưa ghi nhận CVE trên asset này"
        summary = f"Chưa có CVE nào gắn với {server.name} trong latest Wazuh scan được lưu ở dashboard."

    top_packages = sorted(packages.items(), key=lambda item: item[1], reverse=True)[:8]
    next_steps = [
        "Xử lý CVE Critical/High trước, ưu tiên package đang chạy trên dịch vụ public hoặc production.",
        "Cập nhật package bằng repository/vendor chính thức; tránh sửa version thủ công ngoài package manager.",
        "Sau khi vá, restart dịch vụ liên quan nếu cần và chạy lại Wazuh vulnerability scan.",
        "Nếu chưa có bản vá, tạo exception có hạn, giảm exposure bằng firewall/segmentation và theo dõi advisory.",
    ]

    return {
        "priority": priority,
        "verdict": verdict,
        "summary": summary,
        "counts": {
            "critical": counts["Critical"],
            "high": counts["High"],
            "medium": counts["Medium"],
            "low": counts["Low"],
        },
        "top_packages": [{"package": name, "count": count} for name, count in top_packages],
        "next_steps": next_steps,
    }


def _recommendation_for_item_v2(item: dict[str, Any]) -> str:
    cve = _text(item.get("cve")) or "CVE"
    package = _text(item.get("package")) or "package bị ảnh hưởng"
    severity = _severity_label(item.get("severity"))
    fixed_version = _text(item.get("fixed_version"))
    patch_sla = _text(item.get("patch_sla"))
    exploit = _text(item.get("exploit_likelihood"))

    prefix = {
        "Critical": "Cần xử lý như hạng mục ưu tiên cao, đặc biệt nếu asset phục vụ production hoặc có exposure qua mạng quản trị/VPN.",
        "High": "Ưu tiên vá trong cửa sổ thay đổi gần nhất và không nên để quá SLA đã định với asset quan trọng.",
        "Medium": "Đưa vào chu kỳ vá định kỳ và xác minh package/dịch vụ có thực sự được sử dụng hoặc reachable hay không.",
        "Low": "Theo dõi và xử lý cùng đợt cập nhật hệ thống kế tiếp, trừ khi asset criticality làm tăng rủi ro.",
    }[severity]

    fixed_text = (
        f" Phiên bản/bản vá mục tiêu: `{fixed_version}`."
        if fixed_version and fixed_version != "Vendor advisory required"
        else " Cần xác minh fixed version từ vendor advisory trước khi chốt lệnh vá."
    )
    sla_text = f" SLA vá khuyến nghị: {patch_sla}." if patch_sla else ""
    exploit_text = f" Khả năng khai thác: {_exploit_likelihood_vi(exploit)}." if exploit else ""
    return (
        f"{prefix} Cập nhật `{package}` qua repository/vendor channel được hỗ trợ, ưu tiên repo/proxy nội bộ nếu máy không có Internet outbound, "
        f"sau đó chạy lại Wazuh để xác nhận `{cve}` đã hết xuất hiện."
        f"{fixed_text}{sla_text}{exploit_text} Nếu chưa có bản vá, tạo exception có thời hạn, giảm exposure bằng firewall/segmentation "
        "và tiếp tục theo dõi advisory chính thức."
    )


def _enrich_vulnerability_item_v2(item: Any, server: Server | None = None) -> dict[str, Any]:
    row = _merge_vulnerability_intel(item, server=server)
    severity = _severity_label(row.get("severity"))
    score = _score_value(row.get("nvd_cvss_score") or row.get("score"))
    cve = _text(row.get("cve")) or "N/A"
    package = _text(row.get("package")) or "unknown"
    version = _text(row.get("version")) or "unknown"
    risk_score = _int_value(row.get("risk_score"))
    exploit = _text(row.get("exploit_likelihood")) or "Unknown"
    patch_sla = _text(row.get("patch_sla")) or "N/A"

    if row.get("known_exploited") or risk_score >= 85 or severity == "Critical":
        row["risk_priority"] = "P1"
    elif risk_score >= 65 or severity == "High":
        row["risk_priority"] = "P2"
    else:
        row["risk_priority"] = "P3"

    row["severity"] = severity
    row["agent_assessment"] = (
        f"{row['risk_priority']} - CVE mức {_severity_vi(severity)} `{cve}` ảnh hưởng package `{package}` "
        f"phiên bản `{version}`"
        + (f", CVSS {score:g}" if score else "")
        + f". Điểm rủi ro: {risk_score}/100. Khả năng khai thác: {_exploit_likelihood_vi(exploit)}. SLA vá: {patch_sla}."
    )
    row["recommendation"] = _recommendation_for_item_v2(row)
    return row


def _asset_vulnerability_assessment_v2(server: Server, items: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    packages: dict[str, int] = {}
    known_exploited = 0
    max_risk_score = 0
    max_epss = 0.0
    exploit_likelihoods: dict[str, int] = {}
    sla_counts: dict[str, int] = {}

    for item in items:
        severity = _severity_label(item.get("severity"))
        counts[severity] += 1
        package = _text(item.get("package")) or "unknown"
        packages[package] = packages.get(package, 0) + 1
        if item.get("known_exploited"):
            known_exploited += 1
        max_risk_score = max(max_risk_score, _int_value(item.get("risk_score")))
        max_epss = max(max_epss, _score_value(item.get("epss")))
        likelihood = _text(item.get("exploit_likelihood")) or "Unknown"
        exploit_likelihoods[likelihood] = exploit_likelihoods.get(likelihood, 0) + 1
        sla = _text(item.get("patch_sla")) or "N/A"
        sla_counts[sla] = sla_counts.get(sla, 0) + 1

    if known_exploited or max_risk_score >= 85 or counts["Critical"] > 0:
        priority = "P1"
        verdict = "Cần xử lý ngay"
        summary = (
            f"{server.name} có mức phơi nhiễm lỗ hổng cao: {counts['Critical']} CVE nghiêm trọng, "
            f"{counts['High']} CVE cao, {known_exploited} CVE đã ghi nhận khai thác, điểm rủi ro cao nhất {max_risk_score}/100."
        )
    elif counts["High"] > 0 or max_risk_score >= 65:
        priority = "P2"
        verdict = "Cần vá sớm và xác minh exposure"
        summary = (
            f"{server.name} chưa ghi nhận CVE Critical/known-exploited trong dữ liệu hiện tại, "
            f"nhưng có {counts['High']} CVE mức cao và điểm rủi ro cao nhất {max_risk_score}/100."
        )
    elif counts["Medium"] > 0 or counts["Low"] > 0:
        priority = "P3"
        verdict = "Theo dõi trong chu kỳ vá định kỳ"
        summary = (
            f"{server.name} hiện chỉ có CVE mức Trung bình/Thấp. Duy trì chu kỳ vá định kỳ "
            "và quét lại sau khi cập nhật package."
        )
    else:
        priority = "OK"
        verdict = "Chưa ghi nhận CVE khớp với asset"
        summary = f"Chưa có CVE nào được map với {server.name} trong lần scan mới nhất của dashboard."

    top_packages = sorted(packages.items(), key=lambda item: item[1], reverse=True)[:8]
    next_steps = [
        "Ưu tiên vá P1 trước: CVE đã bị khai thác, Critical hoặc risk score >= 85.",
        "Dùng vendor advisory để xác nhận fixed version; OSV/NVD/CISA/EPSS chỉ là nguồn hỗ trợ đánh giá.",
        "Áp dụng cập nhật qua package manager hoặc nền tảng patch được phê duyệt, sau đó restart dịch vụ bị ảnh hưởng nếu cần.",
        "Chạy lại Wazuh vulnerability scan và lưu file Excel làm bằng chứng cho change record.",
    ]

    return {
        "priority": priority,
        "verdict": verdict,
        "summary": summary,
        "counts": {
            "critical": counts["Critical"],
            "high": counts["High"],
            "medium": counts["Medium"],
            "low": counts["Low"],
        },
        "known_exploited": known_exploited,
        "max_risk_score": max_risk_score,
        "max_epss": max_epss,
        "exploit_likelihoods": exploit_likelihoods,
        "sla_counts": sla_counts,
        "top_packages": [{"package": name, "count": count} for name, count in top_packages],
        "next_steps": next_steps,
    }


def _build_vulnerability_scan(result: dict[str, Any], duration_seconds: int, agent_name: str = "") -> VulnerabilityScan:
    status = str(result.get("status") or "failed")
    counts = _scan_counts(result)
    items = _scan_items(result)
    error = result.get("message") or result.get("error")
    return VulnerabilityScan(
        status=status,
        source=result.get("source"),
        agent_filter=agent_name or None,
        total=_int_value(result.get("total"), len(items)),
        fetched=_int_value(result.get("fetched"), len(items)),
        critical=counts["critical"],
        high=counts["high"],
        medium=counts["medium"],
        low=counts["low"],
        summary=result.get("summary") if isinstance(result.get("summary"), dict) else counts,
        items=items,
        analysis=result.get("analysis") or None,
        error=str(error) if error else None,
        duration_seconds=duration_seconds,
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _default_vulnerability_schedule() -> dict[str, Any]:
    enabled = bool(AGENT_AVAILABLE and VULN_REFRESH_INTERVAL_SECONDS > 0)
    interval = max(60, int(VULN_REFRESH_INTERVAL_SECONDS or 900))
    now = _utc_now()
    return {
        "enabled": enabled,
        "interval_seconds": interval,
        "include_analysis": VULN_REFRESH_INCLUDE_ANALYSIS,
        "send_report": VULN_REFRESH_SEND_REPORT,
        "agent_name": "",
        "last_run_at": None,
        "next_run_at": _iso_utc(now + timedelta(seconds=30 if enabled else interval)) if enabled else None,
        "last_status": None,
        "last_error": None,
    }


def _normalize_vulnerability_schedule(raw: Any) -> dict[str, Any]:
    base = _default_vulnerability_schedule()
    if isinstance(raw, dict):
        base.update({key: raw.get(key, base[key]) for key in base})

    try:
        interval = int(base.get("interval_seconds") or 900)
    except (TypeError, ValueError):
        interval = 900
    base["interval_seconds"] = max(60, min(interval, 604800))
    base["enabled"] = bool(base.get("enabled"))
    base["include_analysis"] = bool(base.get("include_analysis"))
    base["send_report"] = bool(base.get("send_report"))
    base["agent_name"] = str(base.get("agent_name") or "").strip()
    base["last_status"] = str(base.get("last_status") or "") or None
    base["last_error"] = str(base.get("last_error") or "") or None
    base["last_run_at"] = _iso_utc(_parse_utc(base.get("last_run_at")))
    base["next_run_at"] = _iso_utc(_parse_utc(base.get("next_run_at"))) if base["enabled"] else None
    return base


async def _get_vulnerability_schedule_row(db: AsyncSession) -> AppSetting:
    row = await db.get(AppSetting, VULNERABILITY_SCHEDULE_KEY)
    if row:
        return row

    row = AppSetting(
        key=VULNERABILITY_SCHEDULE_KEY,
        value=_default_vulnerability_schedule(),
        updated_at=_utc_now(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def _get_vulnerability_schedule(db: AsyncSession) -> tuple[dict[str, Any], datetime | None]:
    row = await _get_vulnerability_schedule_row(db)
    schedule = _normalize_vulnerability_schedule(row.value)
    if schedule != row.value:
        row.value = schedule
        row.updated_at = _utc_now()
        await db.commit()
        await db.refresh(row)
    return schedule, row.updated_at


async def _save_vulnerability_schedule(db: AsyncSession, schedule: dict[str, Any]) -> tuple[dict[str, Any], datetime | None]:
    row = await _get_vulnerability_schedule_row(db)
    row.value = _normalize_vulnerability_schedule(schedule)
    row.updated_at = _utc_now()
    await db.commit()
    await db.refresh(row)
    return row.value, row.updated_at


def _schedule_response(schedule: dict[str, Any], updated_at: datetime | None) -> VulnerabilityScheduleResponse:
    return VulnerabilityScheduleResponse(
        enabled=bool(schedule.get("enabled")),
        interval_seconds=int(schedule.get("interval_seconds") or 900),
        include_analysis=bool(schedule.get("include_analysis")),
        send_report=bool(schedule.get("send_report")),
        agent_name=str(schedule.get("agent_name") or ""),
        last_run_at=_parse_utc(schedule.get("last_run_at")),
        next_run_at=_parse_utc(schedule.get("next_run_at")),
        last_status=schedule.get("last_status"),
        last_error=schedule.get("last_error"),
        updated_at=updated_at,
    )


async def _refresh_vulnerabilities_from_agent(
    *,
    db: AsyncSession,
    agent_name: str = "",
    include_analysis: bool = True,
    send_report: bool = False,
) -> VulnerabilityScan:
    if not AGENT_AVAILABLE:
        raise HTTPException(503, "Agent runtime is not configured")

    payload = {
        "action": "vulnerability_scan",
        "agent_name": agent_name,
        "include_analysis": include_analysis,
        "send_report": send_report,
    }
    started = time.time()
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: _call_agent(
                payload,
                f"vulnerability-refresh-{uuid.uuid4().hex[:8]}",
                user_id="dashboard-system",
                timeout=240,
            ),
        )
        result = response.get("result") if isinstance(response.get("result"), dict) else response
        if isinstance(result, dict):
            enriched_items = await _enrich_scan_items(db, _scan_items(result))
            result = dict(result)
            result["items"] = enriched_items
            result["critical"] = [item for item in enriched_items if _severity_label(item.get("severity")) == "Critical"][:50]
            result["high"] = [item for item in enriched_items if _severity_label(item.get("severity")) == "High"][:100]
        scan = _build_vulnerability_scan(result, int(time.time() - started), agent_name)
    except Exception as exc:
        scan = VulnerabilityScan(
            status="failed",
            agent_filter=agent_name or None,
            summary={},
            items=[],
            error=str(exc),
            duration_seconds=int(time.time() - started),
        )

    db.add(scan)
    await db.commit()
    await db.refresh(scan)
    return scan


async def _vulnerability_refresh_loop() -> None:
    await asyncio.sleep(10)
    while True:
        sleep_for = 60
        try:
            async with SessionLocal() as db:
                schedule, _updated_at = await _get_vulnerability_schedule(db)
                if not schedule.get("enabled"):
                    await asyncio.sleep(sleep_for)
                    continue

                now = _utc_now()
                next_run_at = _parse_utc(schedule.get("next_run_at"))
                if next_run_at is None:
                    schedule["next_run_at"] = _iso_utc(now + timedelta(seconds=int(schedule["interval_seconds"])))
                    await _save_vulnerability_schedule(db, schedule)
                    await asyncio.sleep(sleep_for)
                    continue

                if now >= next_run_at:
                    scan = await _refresh_vulnerabilities_from_agent(
                        db=db,
                        agent_name=str(schedule.get("agent_name") or ""),
                        include_analysis=bool(schedule.get("include_analysis")),
                        send_report=bool(schedule.get("send_report")),
                    )
                    completed_at = _utc_now()
                    schedule["last_run_at"] = _iso_utc(completed_at)
                    schedule["next_run_at"] = _iso_utc(
                        completed_at + timedelta(seconds=int(schedule["interval_seconds"]))
                    )
                    schedule["last_status"] = scan.status or "unknown"
                    schedule["last_error"] = scan.error
                    await _save_vulnerability_schedule(db, schedule)

                next_run_at = _parse_utc(schedule.get("next_run_at"))
                if next_run_at:
                    sleep_for = min(60, max(10, int((next_run_at - _utc_now()).total_seconds())))
        except Exception:
            sleep_for = 60
        await asyncio.sleep(sleep_for)


# ── Routes ────────────────────────────────────────────────────────────────────

def _join_export_list(value: Any, separator: str = "\n") -> str:
    if isinstance(value, list):
        return separator.join(_text(item) for item in value if _text(item))
    if isinstance(value, dict):
        return separator.join(f"{key}: {_text(val)}" for key, val in value.items() if _text(val))
    return _text(value)


def _export_server_for_item(item: Any, servers: list[Server]) -> Server | None:
    for server in servers:
        if _item_matches_server(item, server):
            return server
    return None


def _sort_vulnerability_items(items: list[dict[str, Any]]) -> None:
    items.sort(
        key=lambda item: (
            _int_value(item.get("risk_score")),
            _severity_rank(item.get("severity")),
            _score_value(item.get("nvd_cvss_score") or item.get("score")),
            _text(item.get("detected_at")),
        ),
        reverse=True,
    )


def _matched_vulnerability_items(items: list[Any], server: Server) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for item in items:
        try:
            if _item_matches_server(item, server):
                matched.append(_enrich_vulnerability_item_v2(item, server))
        except Exception as exc:
            cve = item.get("cve") if isinstance(item, dict) else type(item).__name__
            print(f"[vulnerability-detail] skipped malformed finding for {server.name}: {cve}: {exc}")
    return matched


def _vulnerability_export_columns() -> list[str]:
    return [
        "Mức độ",
        "CVE",
        "Ưu tiên rủi ro",
        "Điểm rủi ro",
        "Nhãn rủi ro",
        "CVSS",
        "Mức độ NVD",
        "EPSS",
        "EPSS Percentile",
        "Khả năng khai thác",
        "CISA KEV",
        "SLA vá",
        "Phiên bản/bản vá",
        "Asset",
        "Agent ID",
        "Hệ điều hành",
        "Package",
        "Phiên bản đang cài",
        "Thời điểm phát hiện",
        "Thời điểm công bố",
        "Trạng thái",
        "Tiêu đề/Mô tả nguồn",
        "Đánh giá của agent",
        "Khuyến nghị xử lý",
        "Kế hoạch vá",
        "Nguồn tham khảo",
    ]


def _vulnerability_export_row(item: dict[str, Any]) -> list[Any]:
    return [
        item.get("severity", ""),
        item.get("cve", ""),
        item.get("risk_priority", ""),
        item.get("risk_score", ""),
        item.get("risk_label", ""),
        item.get("nvd_cvss_score") or item.get("score", ""),
        item.get("nvd_severity", ""),
        item.get("epss", ""),
        item.get("epss_percentile", ""),
        item.get("exploit_likelihood", ""),
        "Có" if item.get("known_exploited") else "Không",
        item.get("patch_sla", ""),
        item.get("fixed_version", ""),
        item.get("agent", ""),
        item.get("agent_id", ""),
        item.get("os", ""),
        item.get("package", ""),
        item.get("version", ""),
        item.get("detected_at", ""),
        item.get("published_at", ""),
        item.get("status", ""),
        item.get("title", ""),
        item.get("agent_assessment", ""),
        item.get("recommendation", ""),
        _join_export_list(item.get("patch_plan")),
        _join_export_list(item.get("reference")),
    ]


def _latest_vulnerability_export_rows(scan: VulnerabilityScan, servers: list[Server]) -> list[list[Any]]:
    items = scan.items if isinstance(scan.items, list) else []
    enriched_items: list[dict[str, Any]] = []
    for item in items:
        try:
            enriched_items.append(_enrich_vulnerability_item_v2(item, _export_server_for_item(item, servers)))
        except Exception as exc:
            cve = item.get("cve") if isinstance(item, dict) else type(item).__name__
            print(f"[vulnerability-export] skipped malformed finding: {cve}: {exc}")
    _sort_vulnerability_items(enriched_items)

    rows: list[list[Any]] = [
        ["Báo cáo lỗ hổng bảo mật"],
        ["Phạm vi", "Toàn bộ finding Wazuh"],
        ["Scan ID", scan.id],
        ["Thời điểm scan", scan.scanned_at.isoformat() if scan.scanned_at else ""],
        ["Trạng thái", scan.status or ""],
        ["Nguồn", scan.source or ""],
        ["Tổng số", scan.total or 0],
        ["Đã lấy", scan.fetched or 0],
        ["Nghiêm trọng", scan.critical or 0],
        ["Cao", scan.high or 0],
        ["Trung bình", scan.medium or 0],
        ["Thấp", scan.low or 0],
        ["Phân tích", scan.analysis or ""],
        ["Lỗi", scan.error or ""],
        [],
        _vulnerability_export_columns(),
    ]
    rows.extend(_vulnerability_export_row(item) for item in enriched_items[:5000])
    return rows


def _asset_vulnerability_export_rows(
    *,
    server: Server,
    scan: VulnerabilityScan | None,
    items: list[dict[str, Any]],
    assessment: dict[str, Any],
) -> list[list[Any]]:
    rows: list[list[Any]] = [
        ["Chi tiết CVE và hướng xử lý theo asset"],
        ["Server", server.name],
        ["Địa chỉ", f"{server.host}:{server.port}"],
        ["Hệ điều hành", server.os_type],
        ["Scan ID", scan.id if scan else ""],
        ["Thời điểm scan", scan.scanned_at.isoformat() if scan and scan.scanned_at else ""],
        ["Trạng thái", scan.status if scan else "pending"],
        ["Nguồn", scan.source if scan else ""],
        [],
        ["Đánh giá của agent"],
        ["Ưu tiên", assessment.get("priority", "")],
        ["Kết luận", assessment.get("verdict", "")],
        ["Tóm tắt", assessment.get("summary", "")],
        ["CVE đã bị khai thác", assessment.get("known_exploited", 0)],
        ["Điểm rủi ro cao nhất", assessment.get("max_risk_score", 0)],
        ["EPSS cao nhất", assessment.get("max_epss", 0)],
        [],
        ["Package bị ảnh hưởng nhiều nhất"],
    ]
    for package in assessment.get("top_packages", []) or []:
        if isinstance(package, dict):
            rows.append([package.get("package", ""), package.get("count", "")])
    rows.extend([[], ["Bước xử lý tiếp theo"]])
    for index, step in enumerate(assessment.get("next_steps", []) or [], start=1):
        rows.append([index, step])
    rows.extend([[], _vulnerability_export_columns()])
    rows.extend(_vulnerability_export_row(item) for item in items[:5000])
    return rows


def _xlsx_download(filename: str, rows: list[list[Any]], sheet_name: str) -> Response:
    return Response(
        content=_build_xlsx(rows, sheet_name=sheet_name),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    servers = (await db.execute(select(Server))).scalars().all()
    await _sync_server_statuses(db, list(servers))

    total = (await db.execute(select(func.count()).select_from(Server))).scalar()
    hardened = (await db.execute(select(func.count()).select_from(Server).where(Server.last_status == "hardened"))).scalar()
    partial = (await db.execute(select(func.count()).select_from(Server).where(Server.last_status == "partial"))).scalar()
    none_ = (await db.execute(select(func.count()).select_from(Server).where(Server.last_status == "none"))).scalar()
    unchecked = total - hardened - partial - none_
    return {"total": total, "hardened": hardened, "partial": partial, "none": none_, "unchecked": unchecked}


@app.get("/api/servers", response_model=list[ServerResponse])
async def list_servers(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Server).order_by(Server.created_at.desc()))).scalars().all()
    await _sync_server_statuses(db, list(rows))
    return rows


@app.post("/api/servers", response_model=ServerResponse, status_code=201)
async def create_server(body: ServerCreate, db: AsyncSession = Depends(get_db)):
    if not body.password and not body.ssh_key:
        raise HTTPException(400, "Either password or ssh_key is required")
    server = Server(**body.model_dump())
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


@app.get("/api/servers/{server_id}", response_model=ServerResponse)
async def get_server(server_id: str, db: AsyncSession = Depends(get_db)):
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    await _sync_server_statuses(db, [server])
    return server


@app.delete("/api/servers/{server_id}", status_code=204)
async def delete_server(server_id: str, db: AsyncSession = Depends(get_db)):
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    await db.execute(delete(Report).where(Report.server_id == server_id))
    await db.execute(delete(CheckTask).where(CheckTask.server_id == server_id))
    await db.delete(server)
    await db.commit()


@app.post("/api/servers/{server_id}/check", response_model=TaskResponse, status_code=202)
async def trigger_check(server_id: str, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    task = CheckTask(server_id=server_id)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    background_tasks.add_task(_run_check_bg, task.id, server_id)
    return task


@app.get("/api/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(CheckTask, task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task


@app.get("/api/servers/{server_id}/reports", response_model=list[ReportResponse])
async def list_reports(server_id: str, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(Report).where(Report.server_id == server_id).order_by(Report.checked_at.desc()).limit(20)
        )
    ).scalars().all()
    changed = False
    for row in rows:
        changed = _ensure_report_parsed(row) or changed
    if changed:
        await db.commit()
    if rows:
        server = await db.get(Server, server_id)
        if server and rows[0].status and server.last_status != rows[0].status:
            server.last_status = rows[0].status
            server.last_checked_at = rows[0].checked_at
            await db.commit()
    return rows


@app.get("/api/servers/{server_id}/reports/latest", response_model=ReportResponse)
async def latest_report(server_id: str, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(Report).where(Report.server_id == server_id).order_by(Report.checked_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "No reports yet")
    if _ensure_report_parsed(row):
        await db.commit()
        await db.refresh(row)
    server = await db.get(Server, server_id)
    if server and row.status and server.last_status != row.status:
        server.last_status = row.status
        server.last_checked_at = row.checked_at
        await db.commit()
        await db.refresh(row)
    return row


@app.get("/api/servers/{server_id}/reports/latest/export.xlsx")
async def export_latest_report(server_id: str, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(Report).where(Report.server_id == server_id).order_by(Report.checked_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "No reports yet")
    return await export_report(server_id, row.id, db)


@app.get("/api/servers/{server_id}/reports/{report_id}/export.xlsx")
async def export_report(server_id: str, report_id: str, db: AsyncSession = Depends(get_db)):
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(404, "Server not found")

    row = (
        await db.execute(
            select(Report).where(Report.server_id == server_id, Report.id == report_id).limit(1)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Report not found")
    if _ensure_report_parsed(row):
        await db.commit()
        await db.refresh(row)

    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in server.name).strip("_") or "server"
    checked_at = row.checked_at or datetime.now(timezone.utc)
    filename = f"hardening-{safe_name}-{checked_at:%Y%m%d-%H%M%S}.xlsx"
    return Response(
        content=_build_xlsx(_report_rows(server, row)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# -- Vulnerability feed from agent -------------------------------------------------

@app.get("/api/vulnerabilities/schedule", response_model=VulnerabilityScheduleResponse)
async def get_vulnerability_schedule(db: AsyncSession = Depends(get_db)):
    schedule, updated_at = await _get_vulnerability_schedule(db)
    return _schedule_response(schedule, updated_at)


@app.put("/api/vulnerabilities/schedule", response_model=VulnerabilityScheduleResponse)
async def update_vulnerability_schedule(body: VulnerabilityScheduleUpdate, db: AsyncSession = Depends(get_db)):
    if body.interval_seconds < 60:
        raise HTTPException(400, "interval_seconds must be at least 60")
    if body.interval_seconds > 604800:
        raise HTTPException(400, "interval_seconds must be 604800 or less")

    existing, _updated_at = await _get_vulnerability_schedule(db)
    now = _utc_now()
    schedule = {
        **existing,
        "enabled": body.enabled,
        "interval_seconds": body.interval_seconds,
        "include_analysis": body.include_analysis,
        "send_report": body.send_report,
        "agent_name": body.agent_name.strip(),
        "next_run_at": _iso_utc(now + timedelta(seconds=body.interval_seconds)) if body.enabled else None,
    }
    saved, updated_at = await _save_vulnerability_schedule(db, schedule)
    return _schedule_response(saved, updated_at)


@app.get("/api/vulnerabilities/scans", response_model=list[VulnerabilityScanResponse])
async def list_vulnerability_scans(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(VulnerabilityScan).order_by(VulnerabilityScan.scanned_at.desc()).limit(20))
    ).scalars().all()
    return rows


@app.get("/api/vulnerabilities/latest", response_model=VulnerabilityScanResponse)
async def latest_vulnerability_scan(db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(select(VulnerabilityScan).order_by(VulnerabilityScan.scanned_at.desc()).limit(1))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "No vulnerability scan yet")
    return row


@app.get("/api/vulnerabilities/latest/export.xlsx")
async def export_latest_vulnerability_scan(db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(select(VulnerabilityScan).order_by(VulnerabilityScan.scanned_at.desc()).limit(1))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "No vulnerability scan yet")

    servers = (await db.execute(select(Server))).scalars().all()
    scanned_at = row.scanned_at or _utc_now()
    filename = f"vulnerability-report-{scanned_at:%Y%m%d-%H%M%S}.xlsx"
    return _xlsx_download(
        filename,
        _latest_vulnerability_export_rows(row, list(servers)),
        sheet_name="Bao cao lo hong",
    )


@app.get("/api/vulnerabilities/summary", response_model=VulnerabilitySummaryResponse)
async def vulnerability_summary(db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(select(VulnerabilityScan).order_by(VulnerabilityScan.scanned_at.desc()).limit(1))
    ).scalar_one_or_none()
    if not row:
        return VulnerabilitySummaryResponse(
            latest_scan_id=None,
            scanned_at=None,
            status="pending",
            source=None,
            total=0,
            fetched=0,
            critical=0,
            high=0,
            medium=0,
            low=0,
            analysis=None,
            error=None,
            items=[],
        )

    items = row.items if isinstance(row.items, list) else []
    return VulnerabilitySummaryResponse(
        latest_scan_id=row.id,
        scanned_at=row.scanned_at,
        status=row.status or "unknown",
        source=row.source,
        total=row.total or 0,
        fetched=row.fetched or 0,
        critical=row.critical or 0,
        high=row.high or 0,
        medium=row.medium or 0,
        low=row.low or 0,
        analysis=row.analysis,
        error=row.error,
        items=items[:300],
    )


@app.get("/api/vulnerabilities/emerging", response_model=EmergingCveResponse)
async def emerging_vulnerabilities(limit: int = 10, days: int = 14, db: AsyncSession = Depends(get_db)):
    safe_limit = max(1, min(limit, 50))
    safe_days = max(1, min(days, 120))
    scan = (
        await db.execute(select(VulnerabilityScan).order_by(VulnerabilityScan.scanned_at.desc()).limit(1))
    ).scalar_one_or_none()
    servers = (await db.execute(select(Server))).scalars().all()
    scan_items = scan.items if scan and isinstance(scan.items, list) else []

    candidates, errors = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: _emerging_source_candidates(safe_days),
    )
    items = _emerging_cve_items(candidates, scan_items, list(servers), safe_limit)
    sources = sorted({
        source
        for item in items
        for source in str(item.get("source") or "").split(", ")
        if source
    })

    return EmergingCveResponse(
        generated_at=_utc_now(),
        latest_scan_id=scan.id if scan else None,
        scanned_at=scan.scanned_at if scan else None,
        days=safe_days,
        total=len(items),
        sources=sources,
        errors=errors,
        items=items,
    )


@app.get("/api/vulnerabilities/assets/{server_id}", response_model=VulnerabilityAssetResponse)
async def vulnerability_asset_detail(server_id: str, limit: int = 200, db: AsyncSession = Depends(get_db)):
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(404, "Server not found")
    server_response = ServerResponse.model_validate(server)

    row = (
        await db.execute(select(VulnerabilityScan).order_by(VulnerabilityScan.scanned_at.desc()).limit(1))
    ).scalar_one_or_none()
    if not row:
        return VulnerabilityAssetResponse(
            server=server_response,
            latest_scan_id=None,
            scanned_at=None,
            status="pending",
            source=None,
            total=0,
            critical=0,
            high=0,
            medium=0,
            low=0,
            items=[],
            assessment=_asset_vulnerability_assessment_v2(server, []),
            error=None,
        )

    all_items = row.items if isinstance(row.items, list) else []
    matched = _matched_vulnerability_items(all_items, server)
    _sort_vulnerability_items(matched)

    assessment = _asset_vulnerability_assessment_v2(server, matched)
    counts = assessment["counts"]
    capped_limit = max(1, min(limit, 500))
    return VulnerabilityAssetResponse(
        server=server_response,
        latest_scan_id=row.id,
        scanned_at=row.scanned_at,
        status=row.status or "unknown",
        source=row.source,
        total=len(matched),
        critical=counts["critical"],
        high=counts["high"],
        medium=counts["medium"],
        low=counts["low"],
        items=matched[:capped_limit],
        assessment=assessment,
        error=row.error,
    )


@app.get("/api/vulnerabilities/assets/{server_id}/export.xlsx")
async def export_vulnerability_asset_detail(server_id: str, db: AsyncSession = Depends(get_db)):
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(404, "Server not found")

    row = (
        await db.execute(select(VulnerabilityScan).order_by(VulnerabilityScan.scanned_at.desc()).limit(1))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "No vulnerability scan yet")

    all_items = row.items if isinstance(row.items, list) else []
    matched = _matched_vulnerability_items(all_items, server)
    _sort_vulnerability_items(matched)

    assessment = _asset_vulnerability_assessment_v2(server, matched)
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in server.name).strip("_") or "server"
    scanned_at = row.scanned_at or _utc_now()
    filename = f"vulnerability-{safe_name}-{scanned_at:%Y%m%d-%H%M%S}.xlsx"
    return _xlsx_download(
        filename,
        _asset_vulnerability_export_rows(
            server=server,
            scan=row,
            items=matched,
            assessment=assessment,
        ),
        sheet_name="CVE Detail",
    )


@app.get("/api/vulnerabilities/findings")
async def vulnerability_findings(limit: int = 100, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(select(VulnerabilityScan).order_by(VulnerabilityScan.scanned_at.desc()).limit(1))
    ).scalar_one_or_none()
    if not row:
        return []
    items = row.items if isinstance(row.items, list) else []
    return items[: max(1, min(limit, 500))]


@app.post("/api/vulnerabilities/refresh", response_model=VulnerabilitySummaryResponse)
async def refresh_vulnerabilities(body: VulnerabilityRefreshRequest, db: AsyncSession = Depends(get_db)):
    scan = await _refresh_vulnerabilities_from_agent(
        db=db,
        agent_name=body.agent_name,
        include_analysis=body.include_analysis,
        send_report=body.send_report,
    )
    items = scan.items if isinstance(scan.items, list) else []
    return VulnerabilitySummaryResponse(
        latest_scan_id=scan.id,
        scanned_at=scan.scanned_at,
        status=scan.status or "unknown",
        source=scan.source,
        total=scan.total or 0,
        fetched=scan.fetched or 0,
        critical=scan.critical or 0,
        high=scan.high or 0,
        medium=scan.medium or 0,
        low=scan.low or 0,
        analysis=scan.analysis,
        error=scan.error,
        items=items[:300],
    )


# ── Agent proxy endpoints ─────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str


CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d{4,10}\b", re.IGNORECASE)


def _extract_cves_from_message(message: str) -> list[str]:
    cves: list[str] = []
    for match in CVE_PATTERN.findall(message or ""):
        cve = match.upper()
        if cve not in cves:
            cves.append(cve)
    return cves


async def _cve_lookup_chat_response(message: str, db: AsyncSession) -> str | None:
    cves = _extract_cves_from_message(message)
    if not cves:
        return None

    scan = (
        await db.execute(select(VulnerabilityScan).order_by(VulnerabilityScan.scanned_at.desc()).limit(1))
    ).scalar_one_or_none()
    if not scan or not isinstance(scan.items, list):
        return (
            f"## Kiểm tra CVE: {', '.join(cves)}\n\n"
            "Dashboard chưa có dữ liệu Wazuh vulnerability scan để đối chiếu. "
            "Hãy chạy `Refresh from Agent` ở trang Vulnerability Assets rồi hỏi lại."
        )

    lines = [
        f"## Kiểm tra CVE: {', '.join(cves)}",
        "",
        f"**Nguồn đối chiếu**: latest Wazuh scan"
        f"{f' lúc {scan.scanned_at.isoformat()}' if scan.scanned_at else ''}.",
        "",
    ]

    items = [item for item in scan.items if isinstance(item, dict)]
    for cve in cves:
        matches = [item for item in items if _cve_id(item.get("cve")) == cve]
        if matches:
            lines.extend([
                f"### {cve}: Có xuất hiện trong hệ thống",
                "",
                f"- **Số finding**: {len(matches)}",
                f"- **Mức cao nhất**: {_severity_vi(max((item.get('severity') for item in matches), key=lambda value: {'Critical': 4, 'High': 3, 'Medium': 2, 'Low': 1}.get(_severity_label(value), 0), default='Low'))}",
                "",
                "| Asset | Package | Version | Severity | CVSS |",
                "|---|---|---|---|---:|",
            ])
            for item in matches[:12]:
                lines.append(
                    "| "
                    f"{_text(item.get('agent') or item.get('agent_id') or 'unknown')} | "
                    f"{_text(item.get('package') or 'unknown')} | "
                    f"{_text(item.get('version') or '')} | "
                    f"{_severity_vi(item.get('severity'))} | "
                    f"{_text(item.get('score') or item.get('nvd_cvss_score') or '')} |"
                )
            if len(matches) > 12:
                lines.append(f"\nCòn {len(matches) - 12} finding khác trong dữ liệu scan.")
            lines.extend([
                "",
                "**Khuyến nghị**: ưu tiên kiểm tra package/version trên asset bị ảnh hưởng, đối chiếu vendor advisory, vá theo SLA, rồi chạy lại Wazuh scan để xác nhận CVE không còn xuất hiện.",
                "",
            ])
        else:
            lines.extend([
                f"### {cve}: Chưa thấy trong latest Wazuh scan",
                "",
                "Chưa có finding trùng CVE này trong dữ liệu dashboard hiện tại. "
                "Điều này không đồng nghĩa chắc chắn an toàn nếu Wazuh feed chưa sync, package inventory thiếu, hoặc CVE quá mới.",
                "",
                "**Nên làm tiếp**:",
                "1. Refresh vulnerability scan từ agent.",
                "2. Kiểm tra package/vendor liên quan trên asset nghi ngờ.",
                "3. Đối chiếu NVD/CVE.org/CISA KEV nếu CVE mới được công bố.",
                "",
            ])

    return "\n".join(lines).strip()


def _call_agent(payload: dict, session_id: str, user_id: str = "dashboard-user", timeout: int = 120) -> dict:
    if not AGENT_INVOCATIONS_URL:
        if not LOCAL_AGENT_ENABLED:
            raise RuntimeError("Agent runtime is disabled. Set LOCAL_AGENT_ENABLED=true or AGENT_URL.")
        from agent_runtime import invoke_agent

        return invoke_agent(payload, user_id=user_id, session_id=session_id)
    req = urllib.request.Request(
        AGENT_INVOCATIONS_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-GreenNode-AgentBase-User-Id": user_id,
            "X-GreenNode-AgentBase-Session-Id": session_id,
        },
        method="POST",
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
        return json.loads(r.read())


def _agent_chat_error_message(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        try:
            raw_body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw_body = ""
        print(f"[agent-chat] Agent HTTP {exc.code}: {raw_body[:800]}")
        if exc.code == 404:
            return (
                "Agent endpoint đang trả 404. Kiểm tra lại `AGENT_URL`, thường endpoint chat cần trỏ tới `/invocations`. "
                "Tôi đã lưu câu hỏi này, bạn có thể thử lại sau khi runtime được cập nhật."
            )
        if exc.code in {401, 403}:
            return (
                "Agent runtime từ chối request do thiếu quyền hoặc cấu hình xác thực. "
                "Kiểm tra lại credential/runtime permission rồi thử lại."
            )
        if exc.code >= 500:
            return (
                "Agent runtime đang gặp lỗi nội bộ khi xử lý câu hỏi này. "
                "Bạn có thể thử lại sau vài giây; nếu lỗi lặp lại, kiểm tra log runtime AgentBase để xem stack trace."
            )
        return f"Agent runtime trả lỗi HTTP {exc.code}. Vui lòng kiểm tra cấu hình endpoint hoặc log runtime."

    print(f"[agent-chat] Agent call failed: {exc}")
    return (
        "Dashboard chưa gọi được agent runtime cho lượt chat này. "
        "Kiểm tra kết nối tới `AGENT_URL`, trạng thái runtime và thử lại."
    )


@app.post("/invocations")
async def local_agent_invocations(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"message": str(payload)}
    user_id = (
        request.headers.get("X-GreenNode-AgentBase-User-Id")
        or payload.get("user_id")
        or payload.get("userId")
        or "http-user"
    )
    session_id = (
        request.headers.get("X-GreenNode-AgentBase-Session-Id")
        or payload.get("session_id")
        or payload.get("sessionId")
        or f"http-{uuid.uuid4().hex[:12]}"
    )
    try:
        from agent_runtime import invoke_agent

        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: invoke_agent(payload, user_id=str(user_id), session_id=str(session_id)),
        )
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "response": (
                "Agent runtime local gặp lỗi khi xử lý request. "
                "Kiểm tra cấu hình LLM_API_KEY, LLM_BASE_URL, MEMORY_ID và log container."
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@app.get("/api/agent/status")
async def agent_status():
    if not AGENT_AVAILABLE:
        return {"connected": False, "error": "Agent runtime is disabled", "url": ""}
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _call_agent({"message": "ping"}, f"healthcheck-{uuid.uuid4().hex[:8]}")
        )
        connected = result.get("status") != "error"
        return {
            "connected": connected,
            "url": AGENT_INVOCATIONS_URL or "local:/invocations",
            "response": result.get("response", ""),
            "error": result.get("error") or (result.get("response") if not connected else None),
        }
    except Exception as e:
        return {"connected": False, "error": str(e), "url": AGENT_INVOCATIONS_URL or "local:/invocations"}


@app.get("/api/agent/chat/{session_id}/messages", response_model=list[AgentChatMessageResponse])
async def agent_chat_messages(session_id: str, db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(AgentChatMessage)
            .where(AgentChatMessage.session_id == session_id)
            .order_by(AgentChatMessage.created_at.asc())
            .limit(200)
        )
    ).scalars().all()
    return rows


@app.post("/api/agent/chat")
async def agent_chat(body: ChatRequest, db: AsyncSession = Depends(get_db)):
    if not AGENT_AVAILABLE:
        response_text = "Dashboard chưa có agent runtime khả dụng. Bật LOCAL_AGENT_ENABLED=true hoặc cấu hình AGENT_URL."
        timestamp = datetime.now(timezone.utc).isoformat()
        db.add(AgentChatMessage(session_id=body.session_id, role="user", content=body.message))
        db.add(AgentChatMessage(session_id=body.session_id, role="assistant", content=response_text))
        await db.commit()
        return {"response": response_text, "timestamp": timestamp, "agent_error": "Agent runtime disabled"}

    user_message = AgentChatMessage(session_id=body.session_id, role="user", content=body.message)
    db.add(user_message)
    await db.commit()

    try:
        local_response = await _cve_lookup_chat_response(body.message, db)
        if local_response:
            timestamp = datetime.now(timezone.utc).isoformat()
            db.add(AgentChatMessage(session_id=body.session_id, role="assistant", content=local_response))
            await db.commit()
            return {
                "response": local_response,
                "timestamp": timestamp,
                "source": "dashboard-vulnerability-db",
            }

        result = await asyncio.get_event_loop().run_in_executor(
            None, lambda: _call_agent({"message": body.message}, body.session_id)
        )
        response_text = _text(result.get("response") or result.get("message"))
        if not response_text:
            response_text = "Agent runtime đã phản hồi nhưng không có nội dung trả lời. Vui lòng thử lại hoặc kiểm tra log agent."
        timestamp = result.get("timestamp", datetime.now(timezone.utc).isoformat())
        db.add(AgentChatMessage(session_id=body.session_id, role="assistant", content=response_text))
        await db.commit()
        return {
            "response": response_text,
            "timestamp": timestamp,
        }
    except Exception as exc:
        response_text = _agent_chat_error_message(exc)
        timestamp = datetime.now(timezone.utc).isoformat()
        db.add(AgentChatMessage(session_id=body.session_id, role="assistant", content=response_text))
        await db.commit()
        return {
            "response": response_text,
            "timestamp": timestamp,
            "agent_error": str(exc),
        }


from web_dashboard import register_dashboard_routes


register_dashboard_routes(app)


# Next.js standalone server handles frontend — FastAPI serves /api/* only
