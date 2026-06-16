import base64
import json
import logging
import urllib.request
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

try:
    from langchain_core.tools import tool
except ModuleNotFoundError:
    def tool(func):
        return func

from src.config import TEAMS_WEBHOOK_URL

logger = logging.getLogger(__name__)

REPORT_SOURCE = "VNGDC Security Agent"
REPORT_TEMPLATE = "security_report_workbook_v2"
MAX_CARD_TEXT_CHARS = 22_000

STYLE_NORMAL = 0
STYLE_TITLE = 1
STYLE_SECTION = 2
STYLE_LABEL = 3
STYLE_VALUE = 4
STYLE_TABLE_HEADER = 5
STYLE_FAIL = 6
STYLE_WARN = 7
STYLE_OK = 8
STYLE_RAW = 9
STYLE_MUTED = 10
STYLE_METRIC_FAIL = 11
STYLE_METRIC_WARN = 12
STYLE_METRIC_OK = 13


def _now_ict() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S ICT")


def _clean_xml_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = "".join(ch for ch in text if ch in "\t\n\r" or ord(ch) >= 32)
    return text[:32700]


def _plain(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truncate(text: Any, limit: int) -> str:
    value = _plain(text)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 18)].rstrip() + "\n...[truncated]"


def _join_text_list(value: Any, separator: str = "\n") -> str:
    if isinstance(value, list):
        return separator.join(_plain(item) for item in value if _plain(item))
    if isinstance(value, dict):
        return separator.join(f"{key}: {_plain(val)}" for key, val in value.items() if _plain(val))
    return _plain(value)


def _col_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_cell(row_index: int, col_index: int, value: Any, style: int = STYLE_NORMAL) -> str:
    ref = f"{_col_name(col_index)}{row_index}"
    style_attr = f' s="{style}"' if style else ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    text = escape(_clean_xml_text(value))
    return f'<c r="{ref}"{style_attr} t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>'


def _cell_value_and_style(cell: Any) -> tuple[Any, int]:
    if isinstance(cell, dict):
        return cell.get("value", ""), int(cell.get("style", STYLE_NORMAL) or STYLE_NORMAL)
    if isinstance(cell, tuple) and len(cell) >= 2:
        return cell[0], int(cell[1] or STYLE_NORMAL)
    return cell, STYLE_NORMAL


def _xlsx_row(row_index: int, row: list[Any]) -> str:
    cells = []
    for col_index, cell in enumerate(row, start=1):
        value, style = _cell_value_and_style(cell)
        cells.append(_xlsx_cell(row_index, col_index, value, style))
    return f'<row r="{row_index}">{"".join(cells)}</row>'


def _xlsx_styles() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="6">
    <font><sz val="11"/><color rgb="FF172033"/><name val="Aptos"/></font>
    <font><b/><sz val="18"/><color rgb="FFFFFFFF"/><name val="Aptos Display"/></font>
    <font><b/><sz val="11"/><color rgb="FF172033"/><name val="Aptos"/></font>
    <font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Aptos"/></font>
    <font><sz val="10"/><color rgb="FF253047"/><name val="Consolas"/></font>
    <font><b/><sz val="13"/><color rgb="FFFFFFFF"/><name val="Aptos"/></font>
  </fonts>
  <fills count="13">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF0B5CAB"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F2A44"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEAF2FF"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF2166B1"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFD13438"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF59E0B"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF107C41"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFE8E8"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFF4DE"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFE8F5E9"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF6F8FA"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFD9E2EC"/></left>
      <right style="thin"><color rgb="FFD9E2EC"/></right>
      <top style="thin"><color rgb="FFD9E2EC"/></top>
      <bottom style="thin"><color rgb="FFD9E2EC"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="14">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="2" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="6" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="2" fillId="10" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="3" fillId="8" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="4" fillId="12" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="12" borderId="1" xfId="0" applyFill="1" applyBorder="1"><alignment vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="5" fillId="6" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="5" fillId="7" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="5" fillId="8" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
  <dxfs count="0"/>
  <tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>"""


def _safe_sheet_name(name: str, fallback: str) -> str:
    cleaned = "".join("_" if ch in "[]:*?/\\'" else ch for ch in _plain(name))
    cleaned = cleaned[:31].strip()
    return cleaned or fallback


def _worksheet_xml(
    rows: list[list[Any]],
    widths: list[float] | None = None,
    merges: list[str] | None = None,
    freeze_after_row: int | None = None,
    autofilter_ref: str | None = None,
) -> str:
    sheet_rows = []
    for row_index, row in enumerate(rows, start=1):
        sheet_rows.append(_xlsx_row(row_index, row))

    cols = ""
    if widths:
        col_defs = []
        for index, width in enumerate(widths, start=1):
            col_defs.append(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>')
        cols = f'<cols>{"".join(col_defs)}</cols>'

    if freeze_after_row:
        top_left = f"A{freeze_after_row + 1}"
        sheet_views = (
            '<sheetViews><sheetView workbookViewId="0">'
            f'<pane ySplit="{freeze_after_row}" topLeftCell="{top_left}" activePane="bottomLeft" state="frozen"/>'
            '</sheetView></sheetViews>'
        )
    else:
        sheet_views = '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'

    merge_xml = ""
    if merges:
        merge_cells = "".join(f'<mergeCell ref="{ref}"/>' for ref in merges)
        merge_xml = f'<mergeCells count="{len(merges)}">{merge_cells}</mergeCells>'

    autofilter_xml = f'<autoFilter ref="{autofilter_ref}"/>' if autofilter_ref else ""

    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'{sheet_views}'
        '<sheetFormatPr defaultRowHeight="18"/>'
        f'{cols}'
        '<sheetData>'
        f'{"".join(sheet_rows)}'
        '</sheetData>'
        f'{autofilter_xml}'
        f'{merge_xml}'
        '<pageMargins left="0.35" right="0.35" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>'
        '</worksheet>'
    )


def _build_workbook(sheets: list[dict[str, Any]]) -> bytes:
    sheet_overrides = "\n".join(
        f'  <Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(sheets) + 1)
    )
    workbook_sheets = "\n".join(
        f'    <sheet name="{escape(_safe_sheet_name(str(sheet.get("name", "")), f"Sheet{index}"))}" sheetId="{index}" r:id="rId{index}"/>'
        for index, sheet in enumerate(sheets, start=1)
    )
    workbook_rels = "\n".join(
        f'  <Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(sheets) + 1)
    )

    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
{sheet_overrides}
</Types>""")
        z.writestr("_rels/.rels", """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""")
        z.writestr("xl/workbook.xml", f"""<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
{workbook_sheets}
  </sheets>
</workbook>""")
        z.writestr("xl/_rels/workbook.xml.rels", f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{workbook_rels}
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""")
        z.writestr("xl/styles.xml", _xlsx_styles())
        for index, sheet in enumerate(sheets, start=1):
            z.writestr(
                f"xl/worksheets/sheet{index}.xml",
                _worksheet_xml(
                    sheet.get("rows", []),
                    widths=sheet.get("widths"),
                    merges=sheet.get("merges"),
                    freeze_after_row=sheet.get("freeze_after_row"),
                    autofilter_ref=sheet.get("autofilter_ref"),
                ),
            )
    return out.getvalue()


def _build_xlsx(rows: list[list[Any]]) -> bytes:
    return _build_workbook([
        {
            "name": "Security Report",
            "rows": rows,
            "widths": [26, 38, 26, 38, 26, 38],
            "freeze_after_row": 1,
        }
    ])


def _report_rows(title: str, sections: list) -> list[list[Any]]:
    rows: list[list[Any]] = [
        [title],
        ["Generated at", _now_ict()],
        ["Source", REPORT_SOURCE],
        ["Template", REPORT_TEMPLATE],
        [],
    ]

    for section in sections:
        if not isinstance(section, dict):
            rows.extend([["Message"], [section], []])
            continue

        sec_type = section.get("type", "")
        if sec_type == "hardening_alert":
            rows.extend([
                ["Section", "Hardening Alert"],
                ["Server", section.get("server", "")],
                ["OS", section.get("os", "")],
                ["Status", _status_for_section(section)],
                ["FAIL", section.get("fail_count", 0)],
                ["WARN", section.get("warn_count", 0)],
            ])
            if section.get("analysis"):
                rows.extend([[], ["Agent Analysis"], [section.get("analysis", "")]])
            if section.get("output"):
                rows.extend([[], ["Raw Output"]])
                for line in str(section.get("output", "")).splitlines():
                    rows.append([line])
            rows.append([])
        elif sec_type == "hardening":
            rows.extend([
                ["Section", "Hardening Check"],
                ["Server", section.get("server", "")],
                ["OS", section.get("os", "")],
                ["Status", _status_for_section(section)],
            ])
            if section.get("error"):
                rows.append(["Error", section.get("error", "")])
            if section.get("output"):
                rows.extend([[], ["Raw Output"]])
                for line in str(section.get("output", "")).splitlines():
                    rows.append([line])
            rows.append([])
        elif sec_type == "wazuh":
            rows.extend([
                ["Section", "Wazuh Vulnerability Scan"],
                ["Status", _status_for_section(section)],
                ["Summary", json.dumps(section.get("summary", {}), ensure_ascii=False)],
            ])
            for item in section.get("critical", [])[:50]:
                rows.append([
                    item.get("cve", ""),
                    item.get("package", ""),
                    item.get("version", ""),
                    item.get("agent", ""),
                ])
            rows.append([])

    return rows


def _section_name(section: dict) -> str:
    sec_type = section.get("type", "")
    if sec_type == "hardening_alert":
        return "Hardening Alert"
    if sec_type == "hardening":
        return "Hardening Check"
    if sec_type == "wazuh":
        return "Wazuh Vulnerability Scan"
    return "Security Data"


def _level_style(level: Any) -> int:
    value = _plain(level).upper()
    if any(token in value for token in ("FAIL", "ERROR", "CRITICAL", "CẦN XỬ LÝ", "LỖI")):
        return STYLE_FAIL
    if any(token in value for token in ("WARN", "HIGH", "REVIEW", "CẦN RÀ SOÁT")):
        return STYLE_WARN
    if any(token in value for token in ("OK", "PASS", "DONE", "COMPLETED", "ĐẠT", "HOÀN TẤT")):
        return STYLE_OK
    return STYLE_VALUE


def _metric_style(value: int, warning: bool = False) -> int:
    if value > 0:
        return STYLE_METRIC_WARN if warning else STYLE_METRIC_FAIL
    return STYLE_METRIC_OK


def _status_style_from_metrics(fail_count: int, warn_count: int) -> int:
    if fail_count > 0:
        return STYLE_FAIL
    if warn_count > 0:
        return STYLE_WARN
    return STYLE_OK


def _recommendation_for_finding(level: str, domain: str, evidence: str) -> str:
    text = f"{domain} {evidence}".lower()
    if "ssh" in text:
        return "Review sshd_config, reload SSH safely, then rerun the hardening verification."
    if "firewall" in text or "ufw" in text:
        return "Confirm firewall policy, enable UFW if required, and document allowed inbound ports."
    if "fail2ban" in text or "auth" in text:
        return "Validate brute-force protection and authentication policy on the target server."
    if "password" in text or "pwquality" in text:
        return "Align password policy with the baseline and verify PAM configuration."
    if "patch" in text or "update" in text or "cve" in text:
        return "Prioritize patching by exposure and business criticality, then rescan."
    if "kernel" in text or "sysctl" in text:
        return "Apply the expected sysctl baseline and persist the change under /etc/sysctl.d."
    if "log" in text or "audit" in text:
        return "Enable required logging/audit controls and confirm evidence collection."
    if _plain(level).upper() in {"CRITICAL", "HIGH"}:
        return "Triage affected asset, patch or mitigate, then validate remediation evidence."
    return "Review the control evidence, remediate configuration drift, and rerun validation."


def _parse_evidence_line(line: str, source: str, server: str) -> dict[str, Any] | None:
    stripped = line.strip()
    if not stripped.startswith("[") or "]" not in stripped[:16]:
        return None

    end = stripped.find("]")
    level = stripped[1:end].strip().upper()
    if level not in {"FAIL", "WARN", "ERROR", "CRITICAL", "HIGH"}:
        return None

    rest = stripped[end + 1:].strip()
    parts = [part.strip() for part in rest.split("|")]
    control = parts[0] if parts else level
    domain = parts[1] if len(parts) > 1 else source
    evidence = " | ".join(parts[2:]) if len(parts) > 2 else rest
    return {
        "level": level,
        "source": source,
        "control": control,
        "domain": domain,
        "evidence": evidence,
        "recommendation": _recommendation_for_finding(level, domain, evidence),
        "server": server,
        "status": "Open",
    }


def _collect_report_data(title: str, sections: list) -> dict[str, Any]:
    status, _theme_color = _overall_status(sections)
    data: dict[str, Any] = {
        "title": title,
        "generated_at": _now_ict(),
        "overall_status": status,
        "server": "",
        "os": "",
        "fail_count": 0,
        "warn_count": 0,
        "critical_count": 0,
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "sections": [],
        "findings": [],
        "analysis": [],
        "raw": [],
        "vulnerabilities": [],
    }

    for section in sections:
        if not isinstance(section, dict):
            body = _plain(section)
            if body:
                data["analysis"].append({"title": "Message", "body": body})
            continue

        name = _section_name(section)
        server = _plain(section.get("server")) or "N/A"
        os_type = _plain(section.get("os")) or "N/A"
        section_status = _status_for_section(section)

        if not data["server"] and server != "N/A":
            data["server"] = server
        if not data["os"] and os_type != "N/A":
            data["os"] = os_type

        data["sections"].append({
            "name": name,
            "server": server,
            "os": os_type,
            "status": section_status,
        })

        if section.get("error"):
            error = _plain(section.get("error"))
            data["findings"].append({
                "level": "ERROR",
                "source": name,
                "control": "Runtime",
                "domain": "Execution",
                "evidence": error,
                "recommendation": "Fix the runtime or connectivity issue, then rerun the check.",
                "server": server,
                "status": "Open",
            })
            data["analysis"].append({"title": f"{name} error", "body": error})

        if section.get("type") in {"hardening", "hardening_alert"}:
            fail_count = _count_value(section, "fail_count")
            warn_count = _count_value(section, "warn_count")
            data["fail_count"] += fail_count
            data["warn_count"] += warn_count

            output_lines = _plain(section.get("output")).splitlines()
            for index, line in enumerate(output_lines, start=1):
                data["raw"].append({"source": name, "line": index, "text": line})
                finding = _parse_evidence_line(line, name, server)
                if finding:
                    data["findings"].append(finding)

            if section.get("analysis"):
                data["analysis"].append({
                    "title": f"{name} - {server}",
                    "body": _plain(section.get("analysis")),
                })
            elif fail_count or warn_count:
                data["analysis"].append({
                    "title": f"{name} - {server}",
                    "body": (
                        f"Baseline verification reported {fail_count} FAIL and {warn_count} WARN. "
                        "Review the Findings sheet first, then use Raw Evidence for command-level proof."
                    ),
                })

            if (fail_count or warn_count) and not any(
                finding["source"] == name and finding["server"] == server for finding in data["findings"]
            ):
                data["findings"].append({
                    "level": "FAIL" if fail_count else "WARN",
                    "source": name,
                    "control": "Hardening summary",
                    "domain": "Baseline",
                    "evidence": f"Summary returned {fail_count} FAIL and {warn_count} WARN.",
                    "recommendation": "Inspect Raw Evidence and rerun verification after remediation.",
                    "server": server,
                    "status": "Open",
                })

        elif section.get("type") == "wazuh":
            summary = section.get("summary", {}) if isinstance(section.get("summary"), dict) else {}
            data["critical_count"] += int(summary.get("Critical", 0) or 0)
            data["high_count"] += int(summary.get("High", 0) or 0)
            data["medium_count"] += int(summary.get("Medium", 0) or 0)
            data["low_count"] += int(summary.get("Low", 0) or 0)

            source = _plain(section.get("source")) or "wazuh"
            index_name = _plain(section.get("index")) or "N/A"
            fetched = _count_value(section, "fetched")
            total = _count_value(section, "total")
            data["analysis"].append({
                "title": f"{name} - {source}",
                "body": (
                    f"Vulnerability data source: {source}. Index/API scope: {index_name}. "
                    f"Fetched {fetched or total} of {total} vulnerability records for this report. "
                    "Prioritize Critical and High CVEs by affected asset, package exposure, CVSS score, and production impact."
                ),
            })

            vuln_items = section.get("items", [])
            if not isinstance(vuln_items, list) or not vuln_items:
                vuln_items = []
                for key in ("critical", "high"):
                    values = section.get(key, [])
                    if isinstance(values, list):
                        vuln_items.extend(values)

            for item in vuln_items[:5000]:
                if not isinstance(item, dict):
                    continue
                severity = (_plain(item.get("severity")) or "Low").capitalize()
                if severity not in {"Critical", "High", "Medium", "Low"}:
                    severity = "Low"
                cve = _plain(item.get("cve")) or "CVE"
                package = _plain(item.get("package")) or "unknown package"
                version = _plain(item.get("version")) or "unknown version"
                agent = _plain(item.get("agent")) or "unknown asset"
                agent_id = _plain(item.get("agent_id"))
                os_name = _plain(item.get("os"))
                score = item.get("score", "")
                detected_at = _plain(item.get("detected_at"))
                published_at = _plain(item.get("published_at"))
                vuln_status = _plain(item.get("status")) or "Open"
                title_text = _plain(item.get("title"))
                reference = _join_text_list(item.get("reference"))
                risk_priority = _plain(item.get("risk_priority"))
                risk_score = item.get("risk_score", "")
                epss = item.get("epss", "")
                exploit_likelihood = _plain(item.get("exploit_likelihood")) or "Unknown"
                known_exploited = "Yes" if item.get("known_exploited") else "No"
                fixed_version = _plain(item.get("fixed_version")) or "Vendor advisory required"
                patch_sla = _plain(item.get("patch_sla")) or "N/A"
                patch_plan = _join_text_list(item.get("patch_plan"))
                agent_assessment = _plain(item.get("agent_assessment"))
                evidence = f"{package} {version} on {agent}"
                vuln_row = {
                    "severity": severity,
                    "cve": cve,
                    "package": package,
                    "version": version,
                    "agent": agent,
                    "agent_id": agent_id,
                    "os": os_name,
                    "score": score,
                    "detected_at": detected_at,
                    "published_at": published_at,
                    "status": vuln_status,
                    "description": title_text,
                    "reference": reference,
                    "risk_priority": risk_priority,
                    "risk_score": risk_score,
                    "epss": epss,
                    "exploit_likelihood": exploit_likelihood,
                    "known_exploited": known_exploited,
                    "nvd_cvss_score": item.get("nvd_cvss_score", ""),
                    "nvd_severity": item.get("nvd_severity", ""),
                    "fixed_version": fixed_version,
                    "patch_sla": patch_sla,
                    "patch_plan": patch_plan,
                    "agent_assessment": agent_assessment,
                    "recommendation": item.get("recommendation") or _recommendation_for_finding(severity.upper(), "cve", evidence),
                }
                data["vulnerabilities"].append(vuln_row)
                if severity in {"Critical", "High"}:
                    data["findings"].append({
                        "level": severity.upper(),
                        "source": name,
                        "control": cve,
                        "domain": package,
                        "evidence": evidence,
                        "recommendation": vuln_row["recommendation"],
                        "server": agent,
                        "status": "Open",
                    })

    data["server"] = data["server"] or "N/A"
    data["os"] = data["os"] or "N/A"
    return data


def _risk_statement(data: dict[str, Any]) -> str:
    fail_count = int(data["fail_count"])
    warn_count = int(data["warn_count"])
    critical_count = int(data["critical_count"])
    high_count = int(data["high_count"])
    if fail_count or critical_count:
        return (
            "Risk level is high because the report contains blocking hardening failures "
            "or Critical vulnerabilities. Treat remediation as operational priority."
        )
    if warn_count or high_count:
        return (
            "Risk level requires review. No blocking failure was detected, but warnings "
            "or High vulnerabilities should be triaged and tracked."
        )
    return "No blocking issue was detected in this report. Keep the evidence and continue periodic validation."


def _summary_sheet(data: dict[str, Any]) -> dict[str, Any]:
    fail_count = int(data["fail_count"])
    warn_count = int(data["warn_count"])
    critical_count = int(data["critical_count"])
    high_count = int(data["high_count"])
    medium_count = int(data["medium_count"])
    low_count = int(data["low_count"])
    status_style = _status_style_from_metrics(fail_count + critical_count, warn_count + high_count)

    rows: list[list[Any]] = [
        [(data["title"], STYLE_TITLE), "", "", "", "", "", "", ""],
        [("Generated at", STYLE_LABEL), data["generated_at"], ("Source", STYLE_LABEL), REPORT_SOURCE, ("Template", STYLE_LABEL), REPORT_TEMPLATE, "", ""],
        [],
        [("Executive Summary", STYLE_SECTION), "", "", "", "", "", "", ""],
        [("Overall status", STYLE_LABEL), (data["overall_status"], status_style), ("Primary server", STYLE_LABEL), data["server"], ("Platform", STYLE_LABEL), data["os"], "", ""],
        [("FAIL", STYLE_LABEL), (fail_count, _metric_style(fail_count)), ("WARN", STYLE_LABEL), (warn_count, _metric_style(warn_count, warning=True)), ("Critical CVE", STYLE_LABEL), (critical_count, _metric_style(critical_count)), ("High CVE", STYLE_LABEL), (high_count, _metric_style(high_count, warning=True))],
        [("Medium CVE", STYLE_LABEL), (medium_count, _metric_style(medium_count, warning=True)), ("Low CVE", STYLE_LABEL), (low_count, _metric_style(low_count, warning=True)), ("Inventory rows", STYLE_LABEL), len(data.get("vulnerabilities", [])), "", ""],
        [],
        [("Risk Statement", STYLE_SECTION), "", "", "", "", "", "", ""],
        [(_risk_statement(data), STYLE_VALUE), "", "", "", "", "", "", ""],
        [],
        [("Action Plan", STYLE_SECTION), "", "", "", "", "", "", ""],
        [("Priority", STYLE_TABLE_HEADER), ("Action", STYLE_TABLE_HEADER), ("Owner", STYLE_TABLE_HEADER), ("Expected evidence", STYLE_TABLE_HEADER), "", "", "", ""],
        [("P1", STYLE_FAIL), ("Remediate FAIL/Critical items first.", STYLE_VALUE), ("System owner / Security", STYLE_VALUE), ("Clean rerun result and change record.", STYLE_VALUE), "", "", "", ""],
        [("P2", STYLE_WARN), ("Review WARN/High items and approve exceptions if any.", STYLE_VALUE), ("Security / Platform", STYLE_VALUE), ("Exception note or updated baseline evidence.", STYLE_VALUE), "", "", "", ""],
        [("P3", STYLE_OK), ("Archive report and schedule the next validation.", STYLE_VALUE), ("Operations", STYLE_VALUE), ("Stored Excel report and next run timestamp.", STYLE_VALUE), "", "", "", ""],
        [],
        [("Report Sections", STYLE_SECTION), "", "", "", "", "", "", ""],
        [("Section", STYLE_TABLE_HEADER), ("Server", STYLE_TABLE_HEADER), ("OS", STYLE_TABLE_HEADER), ("Status", STYLE_TABLE_HEADER), "", "", "", ""],
    ]

    for section in data["sections"]:
        rows.append([
            section["name"],
            section["server"],
            section["os"],
            (section["status"], _level_style(section["status"])),
            "", "", "", "",
        ])

    return {
        "name": "Executive Summary",
        "rows": rows,
        "widths": [20, 34, 22, 34, 20, 18, 18, 18],
        "merges": ["A1:H1", "A4:H4", "A9:H9", "A10:H10", "A12:H12", "A18:H18"],
        "freeze_after_row": 4,
    }


def _findings_sheet(data: dict[str, Any]) -> dict[str, Any]:
    findings = data["findings"][:1000]
    rows: list[list[Any]] = [
        [("Prioritized Findings", STYLE_TITLE), "", "", "", "", "", "", ""],
        [("Generated at", STYLE_LABEL), data["generated_at"], ("Status", STYLE_LABEL), data["overall_status"], "", "", "", ""],
        [],
        [("Severity", STYLE_TABLE_HEADER), ("Source", STYLE_TABLE_HEADER), ("Control / CVE", STYLE_TABLE_HEADER), ("Domain / Package", STYLE_TABLE_HEADER), ("Evidence", STYLE_TABLE_HEADER), ("Recommendation", STYLE_TABLE_HEADER), ("Asset", STYLE_TABLE_HEADER), ("Workflow Status", STYLE_TABLE_HEADER)],
    ]
    if not findings:
        rows.append([("OK", STYLE_OK), "No FAIL/WARN/Critical/High finding was extracted.", "", "", "", "", "", "Closed"])
    else:
        for finding in findings:
            level = _plain(finding.get("level")) or "INFO"
            rows.append([
                (level, _level_style(level)),
                finding.get("source", ""),
                finding.get("control", ""),
                finding.get("domain", ""),
                finding.get("evidence", ""),
                finding.get("recommendation", ""),
                finding.get("server", ""),
                finding.get("status", "Open"),
            ])
    last_row = max(4, len(rows))
    return {
        "name": "Findings",
        "rows": rows,
        "widths": [14, 22, 24, 26, 52, 52, 24, 18],
        "merges": ["A1:H1"],
        "freeze_after_row": 4,
        "autofilter_ref": f"A4:H{last_row}",
    }


def _analysis_sheet(data: dict[str, Any]) -> dict[str, Any]:
    rows: list[list[Any]] = [
        [("Agent Analysis", STYLE_TITLE), "", "", "", "", ""],
        [("Generated at", STYLE_LABEL), data["generated_at"], ("Source", STYLE_LABEL), REPORT_SOURCE, "", ""],
        [],
    ]
    merges = ["A1:F1"]
    analysis_blocks = data["analysis"] or [{"title": "Analysis", "body": "No additional agent analysis was generated for this report."}]
    for block in analysis_blocks:
        heading_row = len(rows) + 1
        body_row = heading_row + 1
        rows.append([(block.get("title", "Analysis"), STYLE_SECTION), "", "", "", "", ""])
        rows.append([(_truncate(block.get("body", ""), 12000), STYLE_VALUE), "", "", "", "", ""])
        rows.append([])
        merges.extend([f"A{heading_row}:F{heading_row}", f"A{body_row}:F{body_row}"])
    return {
        "name": "Agent Analysis",
        "rows": rows,
        "widths": [28, 28, 28, 28, 28, 28],
        "merges": merges,
        "freeze_after_row": 2,
    }


def _raw_evidence_sheet(data: dict[str, Any]) -> dict[str, Any]:
    raw_rows = data["raw"][:2500]
    rows: list[list[Any]] = [
        [("Raw Evidence", STYLE_TITLE), "", ""],
        [("Generated at", STYLE_LABEL), data["generated_at"], ""],
        [],
        [("Source", STYLE_TABLE_HEADER), ("Line", STYLE_TABLE_HEADER), ("Output", STYLE_TABLE_HEADER)],
    ]
    if not raw_rows:
        rows.append(["N/A", "", "No raw output was provided."])
    else:
        for item in raw_rows:
            rows.append([
                item.get("source", ""),
                item.get("line", ""),
                (item.get("text", ""), STYLE_RAW),
            ])
        if len(data["raw"]) > len(raw_rows):
            rows.append([
                "Truncated",
                len(raw_rows) + 1,
                (f"Raw evidence was limited to {len(raw_rows)} lines to keep the workbook lightweight.", STYLE_MUTED),
            ])
    last_row = max(4, len(rows))
    return {
        "name": "Raw Evidence",
        "rows": rows,
        "widths": [24, 10, 120],
        "merges": ["A1:C1"],
        "freeze_after_row": 4,
        "autofilter_ref": f"A4:C{last_row}",
    }


def _severity_rank(value: Any) -> int:
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    return order.get(_plain(value).capitalize(), 4)


def _score_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _vulnerability_inventory_sheet(data: dict[str, Any]) -> dict[str, Any]:
    vulnerabilities = sorted(
        data.get("vulnerabilities", []),
        key=lambda item: (
            _severity_rank(item.get("severity")),
            -_score_number(item.get("score")),
            _plain(item.get("agent")),
            _plain(item.get("cve")),
        ),
    )[:5000]

    rows: list[list[Any]] = [
        [("Vulnerability Inventory", STYLE_TITLE), "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        [("Generated at", STYLE_LABEL), data["generated_at"], ("Total rows", STYLE_LABEL), len(vulnerabilities), ("Source", STYLE_LABEL), REPORT_SOURCE, "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
        [],
        [
            ("Severity", STYLE_TABLE_HEADER),
            ("CVE", STYLE_TABLE_HEADER),
            ("Risk Priority", STYLE_TABLE_HEADER),
            ("CVSS", STYLE_TABLE_HEADER),
            ("NVD Severity", STYLE_TABLE_HEADER),
            ("Risk", STYLE_TABLE_HEADER),
            ("EPSS", STYLE_TABLE_HEADER),
            ("Exploit likelihood", STYLE_TABLE_HEADER),
            ("KEV", STYLE_TABLE_HEADER),
            ("Patch SLA", STYLE_TABLE_HEADER),
            ("Fixed Version", STYLE_TABLE_HEADER),
            ("Asset", STYLE_TABLE_HEADER),
            ("Agent ID", STYLE_TABLE_HEADER),
            ("Operating System", STYLE_TABLE_HEADER),
            ("Package", STYLE_TABLE_HEADER),
            ("Installed Version", STYLE_TABLE_HEADER),
            ("Detected At", STYLE_TABLE_HEADER),
            ("Published At", STYLE_TABLE_HEADER),
            ("Status", STYLE_TABLE_HEADER),
            ("Description", STYLE_TABLE_HEADER),
            ("Reference", STYLE_TABLE_HEADER),
            ("Agent Assessment", STYLE_TABLE_HEADER),
            ("Recommendation", STYLE_TABLE_HEADER),
            ("Patch Plan", STYLE_TABLE_HEADER),
        ],
    ]

    if not vulnerabilities:
        rows.append([("OK", STYLE_OK), "No vulnerability inventory data was included.", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
    else:
        for item in vulnerabilities:
            severity = _plain(item.get("severity")).capitalize() or "Low"
            rows.append([
                (severity, _level_style(severity)),
                item.get("cve", ""),
                item.get("risk_priority", ""),
                item.get("nvd_cvss_score") or item.get("score", ""),
                item.get("nvd_severity", ""),
                item.get("risk_score", ""),
                item.get("epss", ""),
                item.get("exploit_likelihood", ""),
                item.get("known_exploited", ""),
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
                _truncate(item.get("description", ""), 1200),
                _truncate(item.get("reference", ""), 1200),
                _truncate(item.get("agent_assessment", ""), 1200),
                item.get("recommendation", ""),
                _truncate(item.get("patch_plan", ""), 1600),
            ])

    last_row = max(4, len(rows))
    return {
        "name": "Vulnerability Inventory",
        "rows": rows,
        "widths": [14, 20, 14, 10, 14, 10, 10, 18, 10, 12, 24, 24, 12, 30, 26, 22, 24, 24, 16, 70, 70, 70, 52, 70],
        "merges": ["A1:X1"],
        "freeze_after_row": 4,
        "autofilter_ref": f"A4:X{last_row}",
    }


def _asset_exposure_sheet(data: dict[str, Any]) -> dict[str, Any]:
    assets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "agent_id": "",
            "os": "",
            "Critical": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0,
            "packages": set(),
            "cves": [],
            "max_score": 0.0,
            "max_risk": 0,
            "known_exploited": 0,
        }
    )

    for item in data.get("vulnerabilities", []):
        asset_name = _plain(item.get("agent")) or "unknown asset"
        severity = _plain(item.get("severity")).capitalize()
        if severity not in {"Critical", "High", "Medium", "Low"}:
            severity = "Low"
        record = assets[asset_name]
        record["agent_id"] = record["agent_id"] or _plain(item.get("agent_id"))
        record["os"] = record["os"] or _plain(item.get("os"))
        record[severity] += 1
        if item.get("package"):
            record["packages"].add(_plain(item.get("package")))
        if item.get("cve"):
            record["cves"].append(_plain(item.get("cve")))
        record["max_score"] = max(float(record["max_score"]), _score_number(item.get("score")))
        try:
            record["max_risk"] = max(int(record["max_risk"]), int(item.get("risk_score") or 0))
        except (TypeError, ValueError):
            pass
        if _plain(item.get("known_exploited")).lower() in {"yes", "true", "1"}:
            record["known_exploited"] += 1

    rows: list[list[Any]] = [
        [("Asset Exposure", STYLE_TITLE), "", "", "", "", "", "", "", "", "", "", ""],
        [("Generated at", STYLE_LABEL), data["generated_at"], ("Assets", STYLE_LABEL), len(assets), "", "", "", "", "", "", "", ""],
        [],
        [
            ("Asset", STYLE_TABLE_HEADER),
            ("Agent ID", STYLE_TABLE_HEADER),
            ("Operating System", STYLE_TABLE_HEADER),
            ("Critical", STYLE_TABLE_HEADER),
            ("High", STYLE_TABLE_HEADER),
            ("Medium", STYLE_TABLE_HEADER),
            ("Low", STYLE_TABLE_HEADER),
            ("Total", STYLE_TABLE_HEADER),
            ("Max CVSS", STYLE_TABLE_HEADER),
            ("Max Risk", STYLE_TABLE_HEADER),
            ("CISA KEV", STYLE_TABLE_HEADER),
            ("Top CVEs / Packages", STYLE_TABLE_HEADER),
        ],
    ]

    if not assets:
        rows.append(["N/A", "", "", 0, 0, 0, 0, 0, "", "", "", "No affected asset was included."])
    else:
        sorted_assets = sorted(
            assets.items(),
            key=lambda pair: (
                -pair[1]["Critical"],
                -pair[1]["High"],
                -pair[1]["Medium"],
                -pair[1]["max_risk"],
                -pair[1]["max_score"],
                pair[0],
            ),
        )
        for asset_name, record in sorted_assets:
            total = record["Critical"] + record["High"] + record["Medium"] + record["Low"]
            top_cves = ", ".join(dict.fromkeys(record["cves"][:8]))
            packages = ", ".join(sorted(record["packages"])[:8])
            rows.append([
                asset_name,
                record["agent_id"],
                record["os"],
                (record["Critical"], _metric_style(record["Critical"])),
                (record["High"], _metric_style(record["High"], warning=True)),
                record["Medium"],
                record["Low"],
                total,
                record["max_score"] or "",
                record["max_risk"] or "",
                record["known_exploited"] or 0,
                _truncate(f"CVEs: {top_cves}\nPackages: {packages}", 1200),
            ])

    last_row = max(4, len(rows))
    return {
        "name": "Asset Exposure",
        "rows": rows,
        "widths": [28, 12, 34, 12, 12, 12, 12, 12, 12, 12, 12, 80],
        "merges": ["A1:L1"],
        "freeze_after_row": 4,
        "autofilter_ref": f"A4:L{last_row}",
    }


def _build_report_workbook(title: str, sections: list) -> bytes:
    data = _collect_report_data(title, sections)
    sheets = [
        _summary_sheet(data),
        _findings_sheet(data),
    ]
    if data.get("vulnerabilities"):
        sheets.extend([
            _vulnerability_inventory_sheet(data),
            _asset_exposure_sheet(data),
        ])
    sheets.extend([
        _analysis_sheet(data),
        _raw_evidence_sheet(data),
    ])
    return _build_workbook(sheets)


def _build_excel_attachment(title: str, sections: list) -> dict | None:
    if not any(isinstance(s, dict) and s.get("type") in {"hardening", "hardening_alert", "wazuh"} for s in sections):
        return None

    safe_title = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in title.lower()).strip("_")
    filename = f"{safe_title or 'security-report'}-{datetime.now():%Y%m%d-%H%M%S}.xlsx"
    content = base64.b64encode(_build_report_workbook(title, sections)).decode("ascii")
    return {
        "name": filename,
        "contentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "contentBase64": content,
        "content": content,
    }


def _count_value(section: dict, key: str) -> int:
    try:
        return int(section.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _status_for_section(section: dict) -> str:
    sec_type = section.get("type", "")
    if section.get("error"):
        return "Lỗi kiểm tra"
    if sec_type == "hardening_alert":
        fail_count = _count_value(section, "fail_count")
        warn_count = _count_value(section, "warn_count")
        if fail_count > 0:
            return "Cần xử lý"
        if warn_count > 0:
            return "Cần rà soát"
        return "Đạt"
    if sec_type == "hardening":
        return "Hoàn tất"
    if sec_type == "wazuh":
        summary = section.get("summary", {}) if isinstance(section.get("summary"), dict) else {}
        if summary.get("Critical", 0):
            return "Cần xử lý"
        if summary.get("High", 0):
            return "Cần rà soát"
        if section.get("status") == "completed":
            return "Đạt"
        return "Lỗi kiểm tra"
    return "Thông tin"


def _overall_status(sections: list) -> tuple[str, str]:
    has_action = False
    has_review = False
    has_error = False

    for section in sections:
        if not isinstance(section, dict):
            continue
        status = _status_for_section(section)
        if status == "Lỗi kiểm tra":
            has_error = True
        elif status == "Cần xử lý":
            has_action = True
        elif status == "Cần rà soát":
            has_review = True

    if has_error:
        return "Lỗi kiểm tra", "C4314B"
    if has_action:
        return "Cần xử lý", "D13438"
    if has_review:
        return "Cần rà soát", "F59E0B"
    return "Đạt", "107C41"


def _evidence_lines(output: Any, limit: int = 8) -> list[str]:
    lines = []
    for line in _plain(output).splitlines():
        if any(marker in line for marker in ("[FAIL]", "[WARN]", "Critical", "High", "CVE-")):
            lines.append(line.strip())
        if len(lines) >= limit:
            break
    return lines


def _bullet_lines(lines: list[str]) -> str:
    if not lines:
        return "- Chưa có bằng chứng rút gọn trong card. Xem file Excel đính kèm để kiểm tra raw output."
    return "\n".join(f"- `{_truncate(line, 240)}`" for line in lines)


def _analysis_block(analysis: Any, fallback: str) -> str:
    text = _plain(analysis)
    if not text:
        return fallback
    return _truncate(text, 2600)


def _render_hardening_alert(section: dict, attachment_name: str | None) -> str:
    server = _plain(section.get("server")) or "unknown"
    os_type = _plain(section.get("os")) or "unknown"
    fail_count = _count_value(section, "fail_count")
    warn_count = _count_value(section, "warn_count")
    status = _status_for_section(section)
    evidence = _evidence_lines(section.get("output"))

    if fail_count > 0:
        summary = (
            f"Server `{server}` chưa đạt baseline hardening. Có **{fail_count} FAIL** cần xử lý trước, "
            f"kèm **{warn_count} WARN** cần rà soát để giảm rủi ro cấu hình sai hoặc kiểm soát bảo mật chưa đủ."
        )
    elif warn_count > 0:
        summary = (
            f"Server `{server}` không có FAIL nhưng còn **{warn_count} WARN**. Cần rà soát các cảnh báo này "
            "để xác nhận kiểm soát bù trừ hoặc chuẩn hóa cấu hình theo baseline."
        )
    else:
        summary = f"Server `{server}` đang đạt các kiểm tra hardening chính trong lần chạy này."

    analysis = _analysis_block(
        section.get("analysis"),
        "Agent chưa có phân tích chi tiết bổ sung. Ưu tiên xử lý các dòng FAIL/WARN trong phần bằng chứng và file Excel đính kèm.",
    )
    attachment_text = attachment_name or "Không có file đính kèm"

    return f"""## 1. Tóm tắt điều hành

{summary}

## 2. Phạm vi kiểm tra

- **Server/Scope**: `{server}`
- **Hệ điều hành/Nền tảng**: `{os_type}`
- **Loại kiểm tra**: Hardening baseline
- **File bằng chứng**: `{attachment_text}`

## 3. Kết quả trọng yếu

- **Trạng thái**: **{status}**
- **Fail/Critical**: **{fail_count}**
- **Warn/High**: **{warn_count}**
- **Tác động vận hành**: Các FAIL cần được xử lý trước khi xem server là đạt chuẩn hardening.

## 4. Phát hiện ưu tiên

{analysis}

## 5. Hành động yêu cầu

1. **P1 - Xử lý FAIL**: ưu tiên các control liên quan SSH, authentication, firewall, patching và logging.
2. **P2 - Rà soát WARN**: xác nhận cảnh báo là ngoại lệ hợp lệ hoặc cập nhật cấu hình theo baseline.
3. **Theo dõi**: chạy lại hardening check sau khi sửa và lưu file Excel làm bằng chứng.

## 6. Bằng chứng và dữ liệu đính kèm

{_bullet_lines(evidence)}
"""


def _render_hardening(section: dict, attachment_name: str | None) -> str:
    server = _plain(section.get("server")) or "unknown"
    os_type = _plain(section.get("os")) or "unknown"
    status = _status_for_section(section)
    attachment_text = attachment_name or "Không có file đính kèm"

    if section.get("error"):
        return f"""## 1. Tóm tắt điều hành

Hardening check cho `{server}` không hoàn tất. Cần xử lý lỗi kết nối hoặc lỗi script trước khi kết luận trạng thái bảo mật.

## 2. Phạm vi kiểm tra

- **Server/Scope**: `{server}`
- **Hệ điều hành/Nền tảng**: `{os_type}`
- **Loại kiểm tra**: Hardening baseline
- **File bằng chứng**: `{attachment_text}`

## 3. Kết quả trọng yếu

- **Trạng thái**: **{status}**
- **Lỗi**: `{_truncate(section.get("error"), 500)}`

## 5. Hành động yêu cầu

1. **P1 - Khôi phục khả năng kiểm tra**: kiểm tra SSH, credential, quyền sudo và script hardening.
2. **Theo dõi**: chạy lại check sau khi sửa lỗi và xác nhận có raw output.
"""

    preview = _truncate(section.get("output"), 1200)
    return f"""## 1. Tóm tắt điều hành

Hardening check cho `{server}` đã hoàn tất. Xem file Excel để đối chiếu raw output đầy đủ và lưu bằng chứng vận hành.

## 2. Phạm vi kiểm tra

- **Server/Scope**: `{server}`
- **Hệ điều hành/Nền tảng**: `{os_type}`
- **Loại kiểm tra**: Hardening baseline
- **File bằng chứng**: `{attachment_text}`

## 3. Kết quả trọng yếu

- **Trạng thái**: **{status}**

## 6. Bằng chứng và dữ liệu đính kèm

```text
{preview}
```
"""


def _render_wazuh(section: dict, attachment_name: str | None) -> str:
    summary = section.get("summary", {}) if isinstance(section.get("summary"), dict) else {}
    critical = int(summary.get("Critical", 0) or 0)
    high = int(summary.get("High", 0) or 0)
    medium = int(summary.get("Medium", 0) or 0)
    low = int(summary.get("Low", 0) or 0)
    status = _status_for_section(section)
    attachment_text = attachment_name or "Không có file đính kèm"

    if section.get("status") != "completed":
        return f"""## 1. Tóm tắt điều hành

Wazuh vulnerability scan không hoàn tất. Cần kiểm tra kết nối Wazuh/API credential trước khi kết luận tình trạng lỗ hổng.

## 3. Kết quả trọng yếu

- **Trạng thái**: **{status}**
- **Lỗi/Thông báo**: `{_truncate(section.get("message") or section.get("error"), 500)}`
"""

    top_cves = []
    for item in section.get("critical", [])[:8]:
        cve = item.get("cve", "CVE")
        package = item.get("package", "unknown")
        version = item.get("version", "unknown")
        agent = item.get("agent", "unknown")
        top_cves.append(f"- **{cve}** - `{package}` `{version}` trên `{agent}`")

    if not top_cves:
        top_cves.append("- Không có CVE Critical trong dữ liệu rút gọn của card.")

    top_cve_text = "\n".join(top_cves)

    return f"""## 1. Tóm tắt điều hành

Wazuh scan đã hoàn tất. Có **{critical} Critical** và **{high} High** cần ưu tiên theo mức độ ảnh hưởng và khả năng khai thác.

## 2. Phạm vi kiểm tra

- **Server/Scope**: Wazuh monitored assets
- **Hệ điều hành/Nền tảng**: Wazuh
- **Loại kiểm tra**: Vulnerability scan
- **File bằng chứng**: `{attachment_text}`

## 3. Kết quả trọng yếu

- **Trạng thái**: **{status}**
- **Critical**: **{critical}**
- **High**: **{high}**
- **Medium**: **{medium}**
- **Low**: **{low}**

## 4. Phát hiện ưu tiên

{top_cve_text}

## 5. Hành động yêu cầu

1. **P1 - Critical/High**: xác định asset Internet-facing hoặc production để vá trước.
2. **P2 - Medium/Low**: gom theo gói/phần mềm và đưa vào lịch patch định kỳ.
3. **Theo dõi**: chạy lại scan sau khi patch và lưu file Excel làm bằng chứng.
"""


def _render_section(section: Any, attachment_name: str | None) -> str:
    if not isinstance(section, dict):
        return f"""## 1. Tóm tắt điều hành

{_truncate(section, 3000)}
"""

    sec_type = section.get("type", "")
    if sec_type == "hardening_alert":
        return _render_hardening_alert(section, attachment_name)
    if sec_type == "hardening":
        return _render_hardening(section, attachment_name)
    if sec_type == "wazuh":
        return _render_wazuh(section, attachment_name)
    return f"""## 1. Tóm tắt điều hành

{_truncate(json.dumps(section, ensure_ascii=False, indent=2), 3000)}
"""


def _build_facts(sections: list, status: str, attachment_name: str | None) -> list[dict[str, str]]:
    facts = [
        {"name": "Trạng thái", "value": status},
        {"name": "Thời điểm", "value": _now_ict()},
        {"name": "Nguồn", "value": REPORT_SOURCE},
        {"name": "Template", "value": REPORT_TEMPLATE},
    ]
    if attachment_name:
        facts.append({"name": "File bằng chứng", "value": attachment_name})

    for section in sections:
        if not isinstance(section, dict):
            continue
        if section.get("type") in {"hardening", "hardening_alert"}:
            facts.append({
                "name": _plain(section.get("server")) or "Server",
                "value": _status_for_section(section),
            })
        elif section.get("type") == "wazuh":
            facts.append({"name": "Wazuh", "value": _status_for_section(section)})
    return facts


def _build_card_text(title: str, sections: list, status: str, attachment_name: str | None) -> str:
    rendered_sections = "\n\n---\n\n".join(_render_section(section, attachment_name) for section in sections)
    body = rendered_sections or "## 1. Tóm tắt điều hành\n\nKhông có dữ liệu báo cáo."
    text = f"""# {title}

**Trạng thái tổng thể**: **{status}**  
**Thời điểm**: {_now_ict()}  
**Nguồn**: {REPORT_SOURCE}

{body}
"""
    return _truncate(text, MAX_CARD_TEXT_CHARS)


def _build_card(title: str, sections: list) -> dict:
    """Build a professional Teams MessageCard payload from report sections."""
    attachment = _build_excel_attachment(title, sections)
    attachment_name = attachment["name"] if attachment else None
    status, theme_color = _overall_status(sections)
    text = _build_card_text(title, sections, status, attachment_name)

    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "title": title,
        "summary": title,
        "text": text,
        "content": text,
        "themeColor": theme_color,
        "template": REPORT_TEMPLATE,
        "sections": [
            {
                "activityTitle": title,
                "activitySubtitle": _now_ict(),
                "markdown": True,
                "facts": _build_facts(sections, status, attachment_name),
                "text": text,
            }
        ],
    }
    if attachment:
        payload["attachments"] = [attachment]
        payload["fileName"] = attachment["name"]
        payload["fileContentType"] = attachment["contentType"]
        payload["fileContentBase64"] = attachment["contentBase64"]
    return payload


def _send_report(title: str, sections: list) -> bool:
    """Send a structured security report to Teams. Raises on failure."""
    if not TEAMS_WEBHOOK_URL:
        logger.warning("TEAMS_WEBHOOK_URL not configured; notification skipped.")
        return False

    payload = json.dumps(_build_card(title, sections), ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        TEAMS_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        resp.read()
    return True


@tool
def send_teams_notification(message: str, title: str = "Security Alert") -> str:
    """
    Send a security notification or alert to Microsoft Teams via incoming webhook.

    Args:
        message: The message body to send. Can be a summary of findings.
        title: Card title shown in Teams (default: "Security Alert").

    Returns:
        Confirmation or error message.
    """
    try:
        success = _send_report(title=title, sections=[message])
        return "Notification sent to Microsoft Teams." if success else "TEAMS_WEBHOOK_URL not configured."
    except Exception as e:
        logger.error(f"Failed to send Teams notification: {e}")
        return f"Failed to send Teams notification: {e}"
