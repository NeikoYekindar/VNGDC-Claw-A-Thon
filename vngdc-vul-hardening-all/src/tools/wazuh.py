import base64
from functools import lru_cache
import json
import logging
import ssl
import urllib.parse
import urllib.request
from typing import Any

try:
    from langchain_core.tools import tool
except ModuleNotFoundError:
    def tool(func):
        return func

from src.config import (
    BASE_DIR,
    WAZUH_HOST,
    WAZUH_INDEXER_HOST,
    WAZUH_INDEXER_INDEX,
    WAZUH_INDEXER_PASSWORD,
    WAZUH_INDEXER_PORT,
    WAZUH_INDEXER_USER,
    WAZUH_INDEXER_VERIFY_SSL,
    WAZUH_PASSWORD,
    WAZUH_PORT,
    WAZUH_USER,
    WAZUH_VULN_BATCH_SIZE,
    WAZUH_VULN_MAX_ITEMS,
    TEAMS_WEBHOOK_URL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)

logger = logging.getLogger(__name__)

SEVERITIES = ("Critical", "High", "Medium", "Low")
CVE_ID_PREFIX = "CVE-"
CVE_SOURCES_PATH = BASE_DIR / "data" / "security_intel" / "cve_sources.json"


def _ssl_context(verify_ssl: bool = False) -> ssl.SSLContext:
    context = ssl.create_default_context()
    if not verify_ssl:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context


def _basic_auth(user: str, password: str) -> str:
    raw = f"{user}:{password}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _json_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    verify_ssl: bool = False,
    timeout: int = 30,
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    with urllib.request.urlopen(req, context=_ssl_context(verify_ssl), timeout=timeout) as resp:
        return json.loads(resp.read())


def _wazuh_manager_request(
    path: str,
    token: str | None = None,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"https://{WAZUH_HOST}:{WAZUH_PORT}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        headers["Authorization"] = _basic_auth(WAZUH_USER, WAZUH_PASSWORD)
    return _json_request(url, method=method, headers=headers, body=body, verify_ssl=False, timeout=20)


def _get_manager_token() -> str:
    resp = _wazuh_manager_request("/security/user/authenticate", method="POST")
    return resp["data"]["token"]


def _wazuh_indexer_request(path: str, body: dict[str, Any]) -> dict[str, Any]:
    encoded_path = path if path.startswith("/") else f"/{path}"
    url = f"https://{WAZUH_INDEXER_HOST}:{WAZUH_INDEXER_PORT}{encoded_path}"
    headers = {"Authorization": _basic_auth(WAZUH_INDEXER_USER, WAZUH_INDEXER_PASSWORD)}
    return _json_request(
        url,
        method="POST",
        headers=headers,
        body=body,
        verify_ssl=WAZUH_INDEXER_VERIFY_SSL,
        timeout=45,
    )


def _severity(value: Any) -> str:
    text = str(value or "Low").strip().capitalize()
    return text if text in SEVERITIES else "Low"


def _score_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _basic_risk_score(severity: str, score: Any) -> int:
    base = {"Critical": 58, "High": 42, "Medium": 24, "Low": 10}.get(_severity(severity), 10)
    cvss = min(_score_float(score), 10.0) * 2.5
    return max(0, min(100, int(round(base + cvss))))


def _basic_patch_sla(severity: str, risk_score: int) -> tuple[str, int]:
    severity = _severity(severity)
    if risk_score >= 85 or severity == "Critical":
        return "48h", 48
    if risk_score >= 65 or severity == "High":
        return "72h", 72
    if severity == "Medium":
        return "14d", 336
    return "30d", 720


def _basic_patch_plan(item: dict[str, Any]) -> list[str]:
    package = str(item.get("package") or "package bị ảnh hưởng")
    cve = str(item.get("cve") or "CVE này")
    os_text = str(item.get("os") or "").lower()

    if "ubuntu" in os_text or "debian" in os_text:
        return [
            f"Xác nhận `{package}` thuộc dịch vụ nào và đánh giá tác động vận hành trước khi vá.",
            f"Chạy `sudo apt update` rồi kiểm tra phiên bản ứng viên bằng `apt-cache policy {package}`.",
            f"Vá bằng `sudo apt install --only-upgrade {package}` hoặc bản vá đã được phê duyệt từ repository/vendor nội bộ.",
            "Khởi động lại dịch vụ bị ảnh hưởng nếu bản cập nhật yêu cầu, sau đó kiểm tra health check.",
            f"Chạy lại Wazuh vulnerability scan và xác nhận `{cve}` không còn được báo cáo.",
        ]
    if "windows" in os_text:
        return [
            f"Mở Microsoft/MSRC advisory cho `{cve}`.",
            "Triển khai KB hoặc product update cần thiết qua kênh patch đã được phê duyệt.",
            "Khởi động lại nếu cần và xác minh bản cập nhật đã được cài.",
            f"Chạy lại Wazuh vulnerability scan và xác nhận `{cve}` không còn được báo cáo.",
        ]
    return [
        f"Rà soát vendor advisory và release notes bản vá cho `{package}`.",
        "Nâng cấp qua package manager hoặc kênh vendor được hỗ trợ.",
        "Khởi động lại dịch vụ phụ thuộc nếu cần.",
        f"Chạy lại Wazuh vulnerability scan và xác nhận `{cve}` đã được xử lý.",
    ]


def _basic_risk_priority(severity: str, risk_score: int) -> str:
    if risk_score >= 85 or _severity(severity) == "Critical":
        return "P1"
    if risk_score >= 65 or _severity(severity) == "High":
        return "P2"
    return "P3"


def _severity_vi(severity: Any) -> str:
    return {
        "Critical": "Nghiêm trọng",
        "High": "Cao",
        "Medium": "Trung bình",
        "Low": "Thấp",
    }.get(_severity(severity), "Chưa xác định")


def _exploit_vi(value: Any) -> str:
    text = str(value or "Unknown").strip()
    return {
        "Known exploited": "Đã ghi nhận khai thác",
        "High": "Cao",
        "Medium": "Trung bình",
        "Low": "Thấp",
        "Unknown": "Chưa xác định",
    }.get(text, text)


def _basic_recommendation(item: dict[str, Any]) -> str:
    cve = str(item.get("cve") or "CVE này")
    package = str(item.get("package") or "package bị ảnh hưởng")
    fixed_version = str(item.get("fixed_version") or "").strip()
    patch_sla = str(item.get("patch_sla") or "").strip()
    exploit = str(item.get("exploit_likelihood") or "Unknown").strip()
    fixed_text = (
        f" Phiên bản/bản vá mục tiêu: `{fixed_version}`."
        if fixed_version and fixed_version != "Vendor advisory required"
        else " Cần xác minh fixed version từ vendor advisory trước khi chốt lệnh vá."
    )
    sla_text = f" SLA vá khuyến nghị: {patch_sla}." if patch_sla else ""
    return (
        f"Cập nhật `{package}` qua repository/vendor channel được hỗ trợ, ưu tiên repo/proxy nội bộ nếu máy không có Internet outbound, "
        f"sau đó chạy lại Wazuh để xác nhận `{cve}` đã được xử lý."
        f"{fixed_text}{sla_text} Khả năng khai thác: {_exploit_vi(exploit)}. "
        "Nếu chưa có bản vá, tạo exception có thời hạn, giảm exposure bằng firewall/segmentation và theo dõi advisory chính thức."
    )


def _with_basic_remediation_context(item: dict[str, Any]) -> dict[str, Any]:
    severity = _severity(item.get("severity"))
    risk_score = _basic_risk_score(severity, item.get("score"))
    sla, sla_hours = _basic_patch_sla(severity, risk_score)
    priority = _basic_risk_priority(severity, risk_score)
    item["severity"] = severity
    item.setdefault("known_exploited", False)
    item.setdefault("epss", "")
    item.setdefault("epss_percentile", "")
    item.setdefault("exploit_likelihood", "Unknown")
    item.setdefault("fixed_version", "Vendor advisory required")
    item["risk_score"] = risk_score
    item["risk_label"] = "Critical" if risk_score >= 85 else "High" if risk_score >= 65 else "Medium" if risk_score >= 40 else "Low"
    item["risk_priority"] = priority
    item["patch_sla"] = sla
    item["patch_sla_hours"] = sla_hours
    item["patch_plan"] = _basic_patch_plan(item)
    item["agent_assessment"] = (
        f"{priority} - CVE mức {_severity_vi(severity)} `{item.get('cve') or 'N/A'}` ảnh hưởng package "
        f"`{item.get('package') or 'unknown'}` phiên bản `{item.get('version') or 'unknown'}`. "
        f"Điểm rủi ro: {risk_score}/100. Khả năng khai thác: {_exploit_vi(item.get('exploit_likelihood'))}. SLA vá: {sla}."
    )
    item["recommendation"] = _basic_recommendation(item)
    return item


def _nested(data: dict[str, Any], path: str, default: Any = "") -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return default
        current = current.get(part)
        if current is None:
            return default
    return current


def _hit_source(hit: dict[str, Any]) -> dict[str, Any]:
    source = hit.get("_source", {})
    return source if isinstance(source, dict) else {}


@lru_cache(maxsize=1)
def _cve_source_config() -> dict[str, Any]:
    try:
        return json.loads(CVE_SOURCES_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to load CVE source config %s: %s", CVE_SOURCES_PATH, exc)
        return {"sources": []}


def _is_cve_id(value: Any) -> bool:
    text = str(value or "").strip().upper()
    return text.startswith(CVE_ID_PREFIX) and len(text.split("-")) >= 3


def _normalize_cve(value: Any) -> str:
    return str(value or "").strip().upper()


def _source_matches_os(source: dict[str, Any], os_text: str) -> bool:
    matches = source.get("os_match")
    if not matches:
        return False
    haystack = os_text.lower()
    return any(str(match).lower() in haystack for match in matches)


def _format_source_url(source: dict[str, Any], cve: str) -> str:
    template = str(source.get("url_template") or "")
    if not template:
        return ""
    return template.replace("{cve}", urllib.parse.quote(cve, safe="-"))


def _configured_cve_links(cve: Any, os_text: str = "") -> list[str]:
    cve_id = _normalize_cve(cve)
    if not _is_cve_id(cve_id):
        return []

    sources = _cve_source_config().get("sources", [])
    if not isinstance(sources, list):
        return []

    vendor_sources: list[dict[str, Any]] = []
    common_sources: list[dict[str, Any]] = []
    common_order = ["cisa_kev", "nvd", "cve_org", "osv", "github_advisory", "epss_api"]

    for source in sources:
        if not isinstance(source, dict):
            continue
        if source.get("scope") == "vendor_advisory" and _source_matches_os(source, os_text):
            vendor_sources.append(source)
        elif source.get("id") in common_order:
            common_sources.append(source)

    common_sources.sort(key=lambda item: common_order.index(item.get("id")) if item.get("id") in common_order else 999)

    links: list[str] = []
    for source in [*vendor_sources, *common_sources]:
        url = _format_source_url(source, cve_id)
        if url and url not in links:
            links.append(url)
    return links


def _normalize_reference_urls(raw: Any) -> list[str]:
    values: list[Any] = []
    if isinstance(raw, list):
        values = raw
    elif isinstance(raw, dict):
        values = list(raw.values())
    elif isinstance(raw, str):
        values = raw.split()

    urls: list[str] = []
    for value in values:
        if isinstance(value, dict):
            value = value.get("url") or value.get("href") or ""
        text = str(value or "").strip().strip(",;")
        if text.startswith(("http://", "https://")) and text not in urls:
            urls.append(text)
    return urls


def _prioritized_references(cve: Any, raw_references: Any, os_text: str = "") -> list[str]:
    links = _configured_cve_links(cve, os_text)
    for url in _normalize_reference_urls(raw_references):
        if url not in links:
            links.append(url)
    return links


def _vulnerability_item(source: dict[str, Any]) -> dict[str, Any]:
    cve = _nested(source, "vulnerability.id", "N/A")
    package_name = _nested(source, "package.name", "unknown")
    package_version = _nested(source, "package.version", "?")
    agent_name = _nested(source, "agent.name", "unknown")
    agent_id = _nested(source, "agent.id", "")
    os_full = _nested(source, "host.os.full", "")
    score = _nested(source, "vulnerability.score.base", "")
    title = _nested(source, "vulnerability.description", "")
    references = _nested(source, "vulnerability.reference", "")
    detected_at = _nested(source, "vulnerability.detected_at", "")
    published_at = _nested(source, "vulnerability.published_at", "")
    status = _nested(source, "vulnerability.status", "")
    severity = _severity(_nested(source, "vulnerability.severity", "Low"))

    return _with_basic_remediation_context({
        "cve": cve,
        "package": package_name,
        "version": package_version,
        "agent": agent_name,
        "agent_id": agent_id,
        "os": os_full,
        "severity": severity,
        "score": score,
        "title": title,
        "reference": _prioritized_references(cve, references, os_full),
        "intel_sources": _configured_cve_links(cve, os_full),
        "detected_at": detected_at,
        "published_at": published_at,
        "status": status,
    })


def _severity_summary_from_aggs(resp: dict[str, Any]) -> dict[str, int]:
    summary = {severity: 0 for severity in SEVERITIES}
    buckets = _nested(resp, "aggregations.by_severity.buckets", [])
    if isinstance(buckets, list):
        for bucket in buckets:
            if not isinstance(bucket, dict):
                continue
            summary[_severity(bucket.get("key"))] += int(bucket.get("doc_count") or 0)
    return summary


def _hits_total(resp: dict[str, Any]) -> int:
    total = _nested(resp, "hits.total.value", 0)
    try:
        return int(total)
    except (TypeError, ValueError):
        return 0


def _indexer_query(agent_name: str, offset: int, size: int) -> dict[str, Any]:
    filters: list[dict[str, Any]] = []
    if agent_name:
        filters.append(
            {
                "bool": {
                    "should": [
                        {"term": {"agent.id": agent_name}},
                        {"term": {"agent.name": agent_name}},
                    ],
                    "minimum_should_match": 1,
                }
            }
        )

    query: dict[str, Any] = {"match_all": {}} if not filters else {"bool": {"filter": filters}}
    return {
        "from": offset,
        "size": size,
        "track_total_hits": True,
        "_source": [
            "agent.id",
            "agent.name",
            "agent.version",
            "host.os.full",
            "host.os.name",
            "host.os.version",
            "package.name",
            "package.version",
            "package.type",
            "vulnerability.id",
            "vulnerability.severity",
            "vulnerability.score.base",
            "vulnerability.description",
            "vulnerability.detected_at",
            "vulnerability.published_at",
            "vulnerability.reference",
            "vulnerability.status",
        ],
        "query": query,
        "sort": [
            {"vulnerability.detected_at": {"order": "desc", "unmapped_type": "date"}},
        ],
        "aggs": {
            "by_severity": {
                "terms": {
                    "field": "vulnerability.severity",
                    "size": 10,
                }
            }
        },
    }


def _run_wazuh_indexer_scan(agent_name: str = "") -> dict[str, Any]:
    if not WAZUH_INDEXER_HOST:
        return {"type": "wazuh", "status": "not_configured", "message": "WAZUH_INDEXER_HOST not set"}
    if not WAZUH_INDEXER_USER or not WAZUH_INDEXER_PASSWORD:
        return {
            "type": "wazuh",
            "status": "not_configured",
            "message": "WAZUH_INDEXER_USER or WAZUH_INDEXER_PASSWORD not set",
        }

    index_path = f"/{WAZUH_INDEXER_INDEX}/_search"
    batch_size = max(1, min(WAZUH_VULN_BATCH_SIZE, 1000))
    max_items = max(1, WAZUH_VULN_MAX_ITEMS)

    items: list[dict[str, Any]] = []
    summary = {severity: 0 for severity in SEVERITIES}
    total = 0

    for offset in range(0, max_items, batch_size):
        size = min(batch_size, max_items - len(items))
        if size <= 0:
            break
        resp = _wazuh_indexer_request(index_path, _indexer_query(agent_name, offset, size))
        hits = _nested(resp, "hits.hits", [])
        if offset == 0:
            total = _hits_total(resp)
            summary = _severity_summary_from_aggs(resp)
        if not isinstance(hits, list) or not hits:
            break
        for hit in hits:
            if isinstance(hit, dict):
                items.append(_vulnerability_item(_hit_source(hit)))
        if len(items) >= total or len(items) >= max_items:
            break

    if not any(summary.values()):
        for item in items:
            summary[_severity(item.get("severity"))] += 1

    groups: dict[str, list[dict[str, Any]]] = {severity: [] for severity in SEVERITIES}
    for item in items:
        groups[_severity(item.get("severity"))].append(item)

    return {
        "type": "wazuh",
        "status": "completed",
        "source": "indexer",
        "index": WAZUH_INDEXER_INDEX,
        "total": total or len(items),
        "fetched": len(items),
        "truncated": bool((total or 0) > len(items)),
        "summary": summary,
        "critical": groups["Critical"][:50],
        "high": groups["High"][:100],
        "items": items,
    }


def _run_wazuh_manager_scan(agent_name: str = "") -> dict[str, Any]:
    if not WAZUH_HOST:
        return {"type": "wazuh", "status": "not_configured", "message": "WAZUH_HOST not set"}

    token = _get_manager_token()

    params: dict[str, Any] = {"limit": 500, "offset": 0}
    if agent_name:
        params["agents_list"] = agent_name

    query = urllib.parse.urlencode(params)
    resp = _wazuh_manager_request(f"/vulnerability?{query}", token=token)
    manager_items = resp.get("data", {}).get("affected_items", [])

    groups: dict[str, list[dict[str, Any]]] = {severity: [] for severity in SEVERITIES}
    for item in manager_items:
        if not isinstance(item, dict):
            continue
        severity = _severity(item.get("severity"))
        groups[severity].append(
            _with_basic_remediation_context({
                "cve": item.get("cve", "N/A"),
                "package": item.get("name", "unknown"),
                "version": item.get("version", "?"),
                "agent": item.get("agent", {}).get("name", "unknown") if isinstance(item.get("agent"), dict) else "unknown",
                "severity": severity,
                "title": item.get("title", ""),
                "reference": _prioritized_references(item.get("cve", "N/A"), item.get("reference", "")),
                "intel_sources": _configured_cve_links(item.get("cve", "N/A")),
            })
        )

    return {
        "type": "wazuh",
        "status": "completed",
        "source": "manager",
        "total": len(manager_items),
        "fetched": len(manager_items),
        "summary": {severity: len(groups[severity]) for severity in SEVERITIES},
        "critical": groups["Critical"][:10],
        "high": groups["High"][:15],
        "items": [item for severity in SEVERITIES for item in groups[severity]],
    }


def _run_wazuh_scan(agent_name: str = "") -> dict[str, Any]:
    """Query Wazuh vulnerability data and return structured summary."""
    if WAZUH_INDEXER_HOST:
        return _run_wazuh_indexer_scan(agent_name)
    return _run_wazuh_manager_scan(agent_name)


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    if value in (None, ""):
        return []
    return [str(value)]


def _manager_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("id") or "")
    return str(value or "")


def _os_full(os_data: Any) -> str:
    if not isinstance(os_data, dict):
        return ""
    if os_data.get("full"):
        return str(os_data["full"])

    parts = [
        os_data.get("name") or os_data.get("platform"),
        os_data.get("version"),
        os_data.get("codename"),
    ]
    return " ".join(str(part) for part in parts if part not in (None, ""))


def _wazuh_agent_item(item: dict[str, Any]) -> dict[str, Any]:
    os_data = item.get("os") if isinstance(item.get("os"), dict) else {}
    groups = item.get("group", item.get("groups", []))

    return {
        "id": str(item.get("id") or ""),
        "name": str(item.get("name") or ""),
        "ip": str(item.get("ip") or item.get("registerIP") or ""),
        "status": str(item.get("status") or "unknown"),
        "version": str(item.get("version") or ""),
        "manager": _manager_name(item.get("manager")),
        "groups": _as_list(groups),
        "node_name": str(item.get("node_name") or item.get("nodeName") or ""),
        "last_keep_alive": str(item.get("lastKeepAlive") or item.get("last_keep_alive") or ""),
        "date_add": str(item.get("dateAdd") or item.get("date_add") or ""),
        "config_sum": str(item.get("configSum") or item.get("config_sum") or ""),
        "merged_sum": str(item.get("mergedSum") or item.get("merged_sum") or ""),
        "os": {
            "full": _os_full(os_data),
            "name": str(os_data.get("name") or ""),
            "platform": str(os_data.get("platform") or ""),
            "version": str(os_data.get("version") or ""),
            "codename": str(os_data.get("codename") or ""),
            "major": str(os_data.get("major") or ""),
            "minor": str(os_data.get("minor") or ""),
            "arch": str(os_data.get("arch") or ""),
        },
    }


def _run_wazuh_agent_inventory(status: str = "", search: str = "", limit: int = 100) -> dict[str, Any]:
    """Query Wazuh Manager agent inventory and return normalized server data."""
    if not WAZUH_HOST:
        return {"type": "wazuh_agents", "status": "not_configured", "message": "WAZUH_HOST not set"}
    if not WAZUH_USER or not WAZUH_PASSWORD:
        return {
            "type": "wazuh_agents",
            "status": "not_configured",
            "message": "WAZUH_USER or WAZUH_PASSWORD not set",
        }

    token = _get_manager_token()
    try:
        requested_limit = int(limit or 100)
    except (TypeError, ValueError):
        requested_limit = 100
    safe_limit = max(1, min(requested_limit, 1000))

    params: dict[str, Any] = {
        "limit": safe_limit,
        "offset": 0,
        "select": (
            "id,name,ip,status,version,manager,group,node_name,os,"
            "lastKeepAlive,dateAdd,configSum,mergedSum"
        ),
    }
    if status:
        params["status"] = status
    if search:
        params["search"] = search

    query = urllib.parse.urlencode(params)
    try:
        resp = _wazuh_manager_request(f"/agents?{query}", token=token)
    except Exception:
        # Older Wazuh versions can be stricter about select fields.
        params.pop("select", None)
        query = urllib.parse.urlencode(params)
        resp = _wazuh_manager_request(f"/agents?{query}", token=token)

    data = resp.get("data", {}) if isinstance(resp.get("data"), dict) else {}
    raw_items = data.get("affected_items", [])
    if not isinstance(raw_items, list):
        raw_items = []

    agents = [_wazuh_agent_item(item) for item in raw_items if isinstance(item, dict)]
    total = data.get("total_affected_items")
    try:
        total_count = int(total)
    except (TypeError, ValueError):
        total_count = len(agents)

    status_counts: dict[str, int] = {}
    os_counts: dict[str, int] = {}
    for agent in agents:
        agent_status = str(agent.get("status") or "unknown")
        status_counts[agent_status] = status_counts.get(agent_status, 0) + 1

        os_data = agent.get("os", {}) if isinstance(agent.get("os"), dict) else {}
        os_key = str(os_data.get("platform") or os_data.get("name") or "unknown")
        os_counts[os_key] = os_counts.get(os_key, 0) + 1

    return {
        "type": "wazuh_agents",
        "status": "completed",
        "source": "manager",
        "total": total_count,
        "fetched": len(agents),
        "truncated": total_count > len(agents),
        "filters": {
            "status": status,
            "search": search,
            "limit": safe_limit,
        },
        "summary": {
            "by_status": status_counts,
            "by_os": os_counts,
        },
        "items": agents,
    }


@tool
def list_wazuh_agents(status: str = "", search: str = "", limit: int = 100) -> str:
    """
    List servers monitored by Wazuh Manager, including agent status, IP, OS, version, groups, and last keep-alive.

    Args:
        status: Optional Wazuh agent status filter, for example active, disconnected, never_connected, or pending.
        search: Optional text filter for agent name, IP, or metadata.
        limit: Maximum number of Wazuh agents to return, capped at 1000.

    Returns:
        Human-readable Wazuh agent inventory summary.
    """
    try:
        result = _run_wazuh_agent_inventory(status=status, search=search, limit=limit)
        if result.get("status") == "not_configured":
            return f"Wazuh agent inventory is not configured: {result.get('message')}"

        by_status = result.get("summary", {}).get("by_status", {})
        by_os = result.get("summary", {}).get("by_os", {})
        agents = result.get("items", [])

        lines = [
            "=== Wazuh Agent Inventory ===",
            "Source: manager",
            f"Total agents: {result.get('total', 0)}",
            f"Fetched for analysis: {result.get('fetched', 0)}",
            "",
            "[STATUS SUMMARY]",
        ]
        for key in sorted(by_status):
            lines.append(f"  {key}: {by_status[key]}")

        if by_os:
            lines.append("\n[OS SUMMARY]")
            for key in sorted(by_os):
                lines.append(f"  {key}: {by_os[key]}")

        if result.get("truncated"):
            lines.append(
                f"\nNote: inventory was truncated at {result.get('fetched')} agents. "
                "Increase the limit argument if the agent needs more context."
            )

        if agents:
            lines.append("\n[AGENTS]")
            for agent in agents:
                if not isinstance(agent, dict):
                    continue
                os_data = agent.get("os", {}) if isinstance(agent.get("os"), dict) else {}
                groups = ", ".join(agent.get("groups", [])) if isinstance(agent.get("groups"), list) else ""
                os_name = os_data.get("full") or os_data.get("name") or "unknown"
                lines.append(
                    f"- id={agent.get('id') or 'N/A'} | name={agent.get('name') or 'unknown'} | "
                    f"ip={agent.get('ip') or 'unknown'} | status={agent.get('status') or 'unknown'} | "
                    f"os={os_name} | version={agent.get('version') or 'unknown'} | "
                    f"groups={groups or 'none'} | last_keep_alive={agent.get('last_keep_alive') or 'unknown'}"
                )
        else:
            lines.append("\nNo Wazuh agents matched the current filter.")

        return "\n".join(lines)
    except Exception as exc:
        logger.error("Wazuh agent inventory failed: %s", exc)
        return f"Wazuh agent inventory failed: {exc}"


def _vulnerability_report_title(result: dict[str, Any], agent_name: str = "") -> str:
    summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
    scope = f" - {agent_name}" if agent_name else ""
    return (
        f"Báo cáo lỗ hổng bảo mật{scope}: "
        f"{summary.get('Critical', 0)} nghiêm trọng, {summary.get('High', 0)} cao"
    )


def _send_vulnerability_report(result: dict[str, Any], agent_name: str = "") -> list[str]:
    """Send the vulnerability report with the shared Excel workbook attachment."""
    if result.get("status") != "completed":
        return []

    title = _vulnerability_report_title(result, agent_name)
    sent_channels: list[str] = []

    if TEAMS_WEBHOOK_URL:
        try:
            from src.tools.teams import _send_report

            if _send_report(title=title, sections=[result]):
                sent_channels.append("Teams")
        except Exception as exc:
            logger.error("Failed to send Wazuh Excel report to Teams: %s", exc)

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            from src.tools.telegram import _send_report as _send_telegram_report

            if _send_telegram_report(title=title, sections=[result]):
                sent_channels.append("Telegram")
        except Exception as exc:
            logger.error("Failed to send Wazuh Excel report to Telegram: %s", exc)

    return sent_channels


@tool
def scan_vulnerabilities(agent_name: str = "") -> str:
    """
    Query Wazuh Vulnerability Detection and summarize CVEs on monitored systems.

    Args:
        agent_name: Optional Wazuh agent ID or name to filter to one host.
                    Leave empty to scan all monitored agents.

    Returns:
        Vulnerability summary with prioritized Critical and High CVEs.
    """
    try:
        result = _run_wazuh_scan(agent_name)

        if result["status"] == "not_configured":
            return f"Wazuh not configured: {result['message']}"

        sent_channels = _send_vulnerability_report(result, agent_name)
        summary = result["summary"]
        source = result.get("source", "wazuh")
        lines = [
            "=== Wazuh Vulnerability Detection ===",
            f"Source: {source}",
            f"Total vulnerabilities: {result['total']}",
            f"Fetched for analysis: {result.get('fetched', result['total'])}",
            f"  Critical : {summary.get('Critical', 0)}",
            f"  High     : {summary.get('High', 0)}",
            f"  Medium   : {summary.get('Medium', 0)}",
            f"  Low      : {summary.get('Low', 0)}",
        ]

        if sent_channels:
            lines.append(f"Excel report sent to: {', '.join(sent_channels)}")
        else:
            lines.append("Excel report not sent: Teams/Telegram notification channel is not configured or failed.")

        if result.get("truncated"):
            lines.append(
                f"Note: result was truncated at {result.get('fetched')} items. "
                "Increase WAZUH_VULN_MAX_ITEMS if the agent needs a larger batch."
            )

        if result["critical"]:
            lines.append("\n[CRITICAL CVEs]")
            for vuln in result["critical"][:20]:
                score = f" | score: {vuln.get('score')}" if vuln.get("score") not in ("", None) else ""
                risk = f" | risk: {vuln.get('risk_score')}/100" if vuln.get("risk_score") not in ("", None) else ""
                sla = f" | SLA: {vuln.get('patch_sla')}" if vuln.get("patch_sla") else ""
                detected = f" | detected: {vuln['detected_at']}" if vuln.get("detected_at") else ""
                lines.append(
                    f"  {vuln.get('cve', 'N/A')} | {vuln.get('package', 'unknown')} {vuln.get('version', '')} | "
                    f"agent: {vuln.get('agent', 'unknown')}{score}{risk}{sla}{detected}"
                )
                if vuln.get("title"):
                    lines.append(f"    -> {str(vuln['title'])[:260]}")
                refs = vuln.get("reference") if isinstance(vuln.get("reference"), list) else []
                if refs:
                    lines.append(f"    sources: {' | '.join(refs[:3])}")

        if result["high"]:
            lines.append("\n[HIGH CVEs - top 30]")
            for vuln in result["high"][:30]:
                score = f" | score: {vuln.get('score')}" if vuln.get("score") not in ("", None) else ""
                risk = f" | risk: {vuln.get('risk_score')}/100" if vuln.get("risk_score") not in ("", None) else ""
                sla = f" | SLA: {vuln.get('patch_sla')}" if vuln.get("patch_sla") else ""
                detected = f" | detected: {vuln['detected_at']}" if vuln.get("detected_at") else ""
                lines.append(
                    f"  {vuln.get('cve', 'N/A')} | {vuln.get('package', 'unknown')} {vuln.get('version', '')} | "
                    f"agent: {vuln.get('agent', 'unknown')}{score}{risk}{sla}{detected}"
                )
                refs = vuln.get("reference") if isinstance(vuln.get("reference"), list) else []
                if refs:
                    lines.append(f"    sources: {' | '.join(refs[:3])}")

        return "\n".join(lines)
    except Exception as exc:
        logger.error("Wazuh scan failed: %s", exc)
        return f"Wazuh scan failed: {exc}"
