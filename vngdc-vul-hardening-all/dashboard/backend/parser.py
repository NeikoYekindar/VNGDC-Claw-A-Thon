import re
from typing import Any

SECTION_RE = re.compile(r"^=+\s*(?:\d+\.\s*)?(.+?)\s*=+$")
CHECK_RE = re.compile(r"^\[(PASS|FAIL|WARN|INFO)\]\s*(.+)$", re.IGNORECASE)


def parse_output(output: str) -> dict[str, Any]:
    sections: list[dict] = []
    current: dict | None = None

    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue

        sec = SECTION_RE.match(line)
        if sec:
            if current:
                sections.append(_finalize(current))
            current = {"name": sec.group(1).strip(), "checks": []}
            continue

        chk = CHECK_RE.match(line)
        if chk and current is not None:
            level, msg = chk.group(1).lower(), chk.group(2).strip()
            current["checks"].append({"level": level, "message": msg})

    if current:
        sections.append(_finalize(current))

    return {"sections": sections, "status": _overall(sections)}


def _finalize(sec: dict) -> dict:
    checks = sec["checks"]
    counts = {"pass": 0, "fail": 0, "warn": 0, "info": 0}
    for c in checks:
        counts[c["level"]] = counts.get(c["level"], 0) + 1

    if counts["fail"] > 0:
        status = "fail"
    elif counts["warn"] > 0:
        status = "warn"
    elif counts["pass"] > 0:
        status = "pass"
    else:
        status = "info"

    return {
        "name": sec["name"],
        "checks": checks,
        "status": status,
        "pass_count": counts["pass"],
        "fail_count": counts["fail"],
        "warn_count": counts["warn"],
        "info_count": counts["info"],
    }


def _overall(sections: list[dict]) -> str:
    scored = [s for s in sections if s["status"] in {"pass", "fail", "warn"}]
    if not scored:
        return "none"
    fail = sum(1 for s in scored if s["status"] == "fail")
    warn = sum(1 for s in scored if s["status"] == "warn")
    if fail == 0 and warn == 0:
        return "hardened"
    if fail < len(scored):
        return "partial"
    return "none"
