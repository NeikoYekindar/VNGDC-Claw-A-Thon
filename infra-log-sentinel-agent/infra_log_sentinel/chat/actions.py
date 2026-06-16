from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import csv
import re
import unicodedata

from infra_log_sentinel.analysis.runbook import recommend_commands
from infra_log_sentinel.analysis.time_window import filter_events_by_lookback
from infra_log_sentinel.config import Settings
from infra_log_sentinel.ingestion.local_folder import iter_new_log_lines
from infra_log_sentinel.models import LogEvent
from infra_log_sentinel.notifications.gmail_sender import (
    GmailConfigError,
    GmailSendError,
    send_report_email,
)
from infra_log_sentinel.parsing.log_parser import parse_raw_lines
from infra_log_sentinel.reporting.pdf_report import build_pdf_report
from infra_log_sentinel.state.log_cursor import LogCursorStore
from infra_log_sentinel.state.runtime_control import (
    CONTROL_EMAIL_REPORTS,
    CONTROL_INCIDENT_GENERATION,
    CONTROL_LOG_GENERATION,
    CONTROL_TELEGRAM_ALERTS,
    VALUE_DEMO_LOG_INTERVAL_SECONDS,
    VALUE_INCIDENT_LOG_INTERVAL_SECONDS,
    RuntimeControlStore,
    now_in_app_timezone,
)


DOMAINS = (
    "network",
    "fortigate",
    "juniper",
    "aruba",
    "linux",
    "windows",
    "vmware",
    "checkmk",
    "cacti",
    "prometheus",
    "grafana",
    "elk",
    "wazuh",
    "syslog",
)
SEVERITIES = ("critical", "error", "warning", "info")
SEVERITY_ORDER = {"critical": 0, "error": 1, "warning": 2, "info": 3}
CHANGE_TERMS = ("doi", "set", "edit", "change", "cap nhat", "thanh", "cau hinh")


@dataclass(frozen=True)
class ChatActionResult:
    handled: bool
    message: str


def try_execute_chat_action(
    settings: Settings,
    events: list[LogEvent],
    question: str,
    dry_run: bool = False,
) -> ChatActionResult:
    action = _detect_action(question)
    if action is None:
        return ChatActionResult(handled=False, message="")

    if action == "control_status":
        return ChatActionResult(handled=True, message=_control_status(settings))
    if action == "clarify_interval":
        return ChatActionResult(handled=True, message=_clarify_interval())
    if action == "clarify_operational_change":
        return ChatActionResult(handled=True, message=_clarify_operational_change())
    if action == "clarify_delivery":
        return ChatActionResult(handled=True, message=_clarify_delivery())
    if action == "explain_scan_interval_change":
        return ChatActionResult(handled=True, message=_explain_scan_interval_change(question))
    if action == "explain_report_schedule_change":
        return ChatActionResult(handled=True, message=_explain_report_schedule_change(question))
    if action == "pause_controls":
        return ChatActionResult(handled=True, message=_pause_controls(settings, question, dry_run=dry_run))
    if action == "resume_controls":
        return ChatActionResult(handled=True, message=_resume_controls(settings, question, dry_run=dry_run))
    if action == "set_log_interval":
        return ChatActionResult(handled=True, message=_set_log_interval(settings, question, dry_run=dry_run))
    if action == "new_logs":
        return ChatActionResult(handled=True, message=_scan_new_logs(settings))

    scoped_events = _events_for_action(settings, events, question)
    if action == "report":
        return ChatActionResult(
            handled=True,
            message=_generate_report(settings, scoped_events, question),
        )
    if action == "email_report":
        return ChatActionResult(
            handled=True,
            message=_email_report(settings, scoped_events, question, dry_run=dry_run),
        )
    if action == "export_csv":
        return ChatActionResult(
            handled=True,
            message=_export_csv(settings, scoped_events, question),
        )

    return ChatActionResult(handled=False, message="")


def _detect_action(question: str) -> str | None:
    q = _normalize(question)
    if _looks_like_assistant_correction(q):
        return None
    if _looks_like_informational_log_question(q):
        return None

    if any(term in q for term in ["control status", "trang thai control", "trang thai pause", "pause status"]):
        return "control_status"
    if _looks_like_interval_update(q):
        return "set_log_interval"
    if _looks_like_scan_interval_update(q):
        return "explain_scan_interval_change"
    if _looks_like_report_schedule_update(q):
        return "explain_report_schedule_change"
    if _looks_like_interval_clarification(q):
        return "clarify_interval"
    if _looks_like_operational_change_clarification(q):
        return "clarify_operational_change"
    if _looks_like_pause(q):
        return "pause_controls"
    if _looks_like_resume(q):
        return "resume_controls"
    if _looks_like_delivery_clarification(q):
        return "clarify_delivery"
    if any(term in q for term in ["log moi", "new log", "scan new", "kiem tra log moi"]):
        return "new_logs"
    if any(term in q for term in ["csv", "export", "excel", "xuat file", "xuat danh sach"]):
        return "export_csv"
    if any(term in q for term in ["gui bao cao", "send report", "email report", "gmail", "gui mail", "send mail"]):
        return "email_report"
    if any(term in q for term in ["bao cao", "report", "pdf", "xuat bao cao", "tao bao cao"]):
        return "report"
    return None


def _looks_like_assistant_correction(q: str) -> bool:
    correction_terms = (
        "khong phai yeu cau",
        "khong yeu cau",
        "toi khong yeu cau",
        "khong de cap den viec thay doi",
        "khong de cap viec thay doi",
        "trong cau hoi tren khong de cap",
        "cau hoi tren khong de cap",
        "cau hoi truoc khong de cap",
        "ban dang khong hieu",
        "agent dang khong hieu",
        "bot dang khong hieu",
    )
    return any(term in q for term in correction_terms)


def _looks_like_informational_log_question(q: str) -> bool:
    has_log_scope = (
        "log" in q
        or "alert" in q
        or "event" in q
        or any(domain in q for domain in DOMAINS)
        or any(severity in q for severity in SEVERITIES)
    )
    if not has_log_scope:
        return False

    explicit_delivery_or_export = (
        "pdf" in q
        or "csv" in q
        or "excel" in q
        or "gmail" in q
        or "email" in q
        or "mail" in q
        or "xuat bao cao" in q
        or "tao bao cao" in q
        or "gui bao cao" in q
        or "send report" in q
        or "export" in q
        or "xuat file" in q
    )
    if explicit_delivery_or_export:
        return False

    info_terms = (
        "tom tat",
        "summary",
        "tong quan",
        "bao nhieu",
        "count",
        "co",
        "khong",
        "nao",
        "phan tich",
        "uu tien",
        "can xem",
        "command",
        "lenh",
        "xu ly",
        "nguyen nhan",
        "cause",
        "impact",
        "tac dong",
    )
    return any(term in q for term in info_terms)


def _events_for_action(settings: Settings, events: list[LogEvent], question: str) -> list[LogEvent]:
    recent_events = filter_events_by_lookback(
        events,
        lookback_hours=settings.report_lookback_hours,
    )
    filtered = _filter_by_question(recent_events, question)
    return _sort_events(filtered if _has_filters(question) else recent_events)


def _generate_report(settings: Settings, events: list[LogEvent], question: str) -> str:
    report_path = build_pdf_report(
        events=events,
        output_dir=settings.report_output_dir,
        alert_levels=settings.severity_alert_levels,
        report_window_label=_window_label(settings, question),
    )
    return (
        "Đã tạo PDF report theo yêu cầu.\n"
        f"- File: {report_path}\n"
        f"- Số event trong report: {len(events)}\n"
        f"- Phạm vi mặc định: {settings.report_lookback_hours} giờ gần nhất"
    )


def _email_report(settings: Settings, events: list[LogEvent], question: str, dry_run: bool) -> str:
    pause_state = RuntimeControlStore(settings.state_db_path).pause_state(CONTROL_EMAIL_REPORTS)
    if pause_state.paused:
        return (
            "Gmail report dang tam dung theo runtime control.\n"
            f"- Tam dung den: {pause_state.paused_until:%Y-%m-%d %H:%M:%S}\n"
            "- Hay chat 'bat lai gui report' neu muon gui lai ngay."
        )

    report_path = build_pdf_report(
        events=events,
        output_dir=settings.report_output_dir,
        alert_levels=settings.severity_alert_levels,
        report_window_label=_window_label(settings, question),
    )
    try:
        result = send_report_email(settings=settings, report_path=report_path, dry_run=dry_run)
    except (GmailConfigError, GmailSendError) as exc:
        return f"Không gửi được Gmail report: {exc}"

    return (
        "Đã xử lý yêu cầu gửi report qua Gmail.\n"
        f"- File: {report_path}\n"
        f"- Số event trong report: {len(events)}\n"
        f"- Kết quả Gmail: {result.message}"
    )


def _export_csv(settings: Settings, events: list[LogEvent], question: str) -> str:
    export_events = events
    q = _normalize(question)
    if "alert" in q and not any(severity in q for severity in SEVERITIES):
        export_events = [event for event in events if event.severity in set(settings.severity_alert_levels)]

    output_dir = settings.report_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"infra-log-sentinel-export-{datetime.now():%Y%m%d-%H%M%S}.csv"

    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "domain",
                "source",
                "severity",
                "event_type",
                "message",
                "probable_cause",
                "impact",
                "recommended_action",
                "commands",
            ],
        )
        writer.writeheader()
        for event in export_events:
            writer.writerow(
                {
                    "timestamp": event.timestamp,
                    "domain": event.domain,
                    "source": event.source,
                    "severity": event.severity,
                    "event_type": event.event_type,
                    "message": event.message,
                    "probable_cause": event.probable_cause,
                    "impact": event.impact,
                    "recommended_action": event.recommended_action,
                    "commands": " | ".join(command.command for command in recommend_commands(event)[:5]),
                }
            )

    return (
        "Đã export CSV theo yêu cầu.\n"
        f"- File: {output_path}\n"
        f"- Số event export: {len(export_events)}\n"
        f"- Phạm vi mặc định: {settings.report_lookback_hours} giờ gần nhất"
    )


def _scan_new_logs(settings: Settings) -> str:
    cursor_store = LogCursorStore(settings.state_db_path)
    raw_lines = list(
        iter_new_log_lines(
            settings.log_root_path,
            cursor_store,
            update_cursor=False,
        )
    )
    events = parse_raw_lines(raw_lines)
    alert_events = _sort_events(
        [event for event in events if event.severity in set(settings.severity_alert_levels)]
    )

    lines = [
        "Đã kiểm tra log mới theo realtime cursor.",
        f"- Dòng log mới: {len(raw_lines)}",
        f"- Alert mới: {len(alert_events)}",
    ]
    if alert_events:
        lines.append("- Top alert mới:")
        for event in alert_events[:5]:
            lines.append(f"  - [{event.severity.upper()}] {event.domain}/{event.source} {event.event_type}: {event.message}")
    else:
        lines.append("- Không có warning/error/critical mới.")
    lines.append("Lưu ý: chat action này chỉ kiểm tra, không consume cursor và không gửi Telegram.")
    return "\n".join(lines)


def _control_status(settings: Settings) -> str:
    store = RuntimeControlStore(settings.state_db_path)
    interval = store.get_float_value(
        VALUE_DEMO_LOG_INTERVAL_SECONDS,
        settings.demo_log_interval_seconds,
    )
    incident_interval = store.get_float_value(
        VALUE_INCIDENT_LOG_INTERVAL_SECONDS,
        settings.incident_log_interval_seconds,
    )
    telegram_pause = store.pause_state(CONTROL_TELEGRAM_ALERTS)
    email_pause = store.pause_state(CONTROL_EMAIL_REPORTS)
    loggen_pause = store.pause_state(CONTROL_LOG_GENERATION)
    incident_pause = store.pause_state(CONTROL_INCIDENT_GENERATION)
    delivery_state, delivery_detail = _telegram_alert_delivery_state(
        settings,
        paused=telegram_pause.paused,
        manual_off=bool(telegram_pause.paused_until and telegram_pause.paused_until.year >= 9999),
    )
    lines = [
        "Runtime control status:",
        f"- telegram_alert_pause: {telegram_pause.as_text()}",
        f"- telegram_alert_delivery: {delivery_state}",
        f"- scheduler_worker: {'enabled' if settings.runtime_scheduler_enabled else 'disabled'}",
        f"- delivery_mode: {'dry_run' if settings.runtime_scheduler_dry_run else 'live'}",
        f"- telegram_config: {'configured' if _telegram_alerts_configured(settings) else 'missing'}",
        f"- email_reports: {email_pause.as_text()}",
        f"- log_generation: {loggen_pause.as_text()}",
        f"- demo_log_interval_seconds: {interval:g}",
        f"- incident_generation: {incident_pause.as_text()}",
        f"- incident_log_interval_seconds: {incident_interval:g}",
    ]
    if delivery_detail:
        lines.extend(["", f"Note: {delivery_detail}"])
    return "\n".join(lines)


def _telegram_alert_delivery_state(settings: Settings, paused: bool, manual_off: bool = False) -> tuple[str, str]:
    if not _telegram_alerts_configured(settings):
        return (
            "misconfigured",
            "Telegram bot token/chat id is missing or placeholder, so alerts cannot be sent.",
        )
    if not settings.runtime_scheduler_enabled:
        return (
            "disabled",
            "Runtime scheduler is off, so realtime alert scans are not running.",
        )
    if settings.runtime_scheduler_dry_run:
        return (
            "dry_run",
            "Runtime scheduler is in preview mode, so Telegram alert messages are not sent.",
        )
    if paused and manual_off:
        return (
            "off",
            "Telegram alert delivery is off until it is enabled again.",
        )
    if paused:
        return (
            "paused",
            "Telegram alert delivery is temporarily paused by runtime control.",
        )
    return (
        "live",
        "Scheduler is enabled, dry-run is off, config is present, and alert delivery is not paused.",
    )


def _telegram_alerts_configured(settings: Settings) -> bool:
    return _has_real_secret(settings.telegram_bot_token) and _has_real_secret(settings.telegram_chat_id)


def _has_real_secret(value: str) -> bool:
    return value.strip() not in {
        "",
        "replace_with_telegram_bot_token",
        "replace_with_telegram_chat_id",
    }


def _pause_controls(settings: Settings, question: str, dry_run: bool) -> str:
    paused_until = _parse_until(question)
    if paused_until is None:
        return (
            "Can chi dinh moc thoi gian de tam dung.\n"
            "Vi du: 'tam dung alert va report den 17:30' hoac 'tam ngung sinh log trong 30 phut'."
        )

    targets = _control_targets(question, default_all=False)
    if not targets:
        return (
            "Minh chua ro can tam dung phan nao.\n"
            "Co the dung: alert, report/gmail, sinh log."
        )

    labels = ", ".join(_control_label(target) for target in targets)
    if dry_run:
        return (
            "Preview only: mình chưa thay đổi runtime control.\n"
            f"- Sẽ tạm dừng: {labels}\n"
            f"- Đến: {paused_until:%Y-%m-%d %H:%M:%S}\n"
            "- Tắt Preview only nếu anh muốn áp dụng thật."
        )

    store = RuntimeControlStore(settings.state_db_path)
    for target in targets:
        store.pause_until(target, paused_until)

    return (
        "Da cap nhat runtime control.\n"
        f"- Tam dung: {labels}\n"
        f"- Den: {paused_until:%Y-%m-%d %H:%M:%S}\n"
        "- Co the bat lai som bang lenh: 'bat lai alert', 'bat lai report', hoac 'bat lai sinh log'."
    )


def _resume_controls(settings: Settings, question: str, dry_run: bool) -> str:
    targets = _control_targets(question, default_all=False)
    if not targets:
        return (
            "Mình hiểu anh muốn bật lại một phần runtime control, nhưng chưa rõ phần nào.\n"
            "Anh có thể nói rõ hơn, ví dụ:\n"
            "- `bật lại alert`\n"
            "- `bật lại report`\n"
            "- `bật lại sinh log`\n"
            "- `bật lại tất cả`"
        )

    labels = ", ".join(_control_label(target) for target in targets)
    if dry_run:
        return (
            "Preview only: mình chưa thay đổi runtime control.\n"
            f"- Sẽ bật lại: {labels}\n"
            "- Tắt Preview only nếu anh muốn áp dụng thật."
        )

    store = RuntimeControlStore(settings.state_db_path)
    for target in targets:
        store.resume(target)

    return (
        "Da bat lai runtime control.\n"
        f"- Dang chay lai: {labels}"
    )


def _set_log_interval(settings: Settings, question: str, dry_run: bool) -> str:
    interval_seconds = _parse_interval_seconds(question)
    if interval_seconds is None:
        return (
            "Can chi dinh interval sinh log.\n"
            "Vi du: 'doi interval sinh log 120 giay' hoac 'sinh log moi 5 phut'."
        )

    interval_seconds = max(interval_seconds, 1.0)
    is_incident_interval = _mentions_incident_generator(_normalize(question))
    setting_name = VALUE_INCIDENT_LOG_INTERVAL_SECONDS if is_incident_interval else VALUE_DEMO_LOG_INTERVAL_SECONDS
    label = "auto incident log generation" if is_incident_interval else "auto log generation"
    if dry_run:
        return (
            "Preview only: mình chưa thay đổi interval auto sinh log.\n"
            f"- Nếu áp dụng thật, interval mới sẽ là: {interval_seconds:g} giây\n"
            "- Tắt Preview only nếu anh muốn cập nhật runtime generator."
        )

    RuntimeControlStore(settings.state_db_path).set_value(
        setting_name,
        f"{interval_seconds:g}",
    )
    return (
        f"Da cap nhat interval {label}.\n"
        f"- Interval moi: {interval_seconds:g} giay\n"
        "- Runtime generator se ap dung o chu ky tiep theo."
    )


def _clarify_interval() -> str:
    return (
        "Bạn muốn đổi interval nào?\n"
        "- Interval auto sinh log: ví dụ `đổi interval sinh log 120 giây`\n"
        "- Interval scan alert realtime: ví dụ `đổi scan interval 60 giây`\n"
        "- Lịch report Gmail: ví dụ `đổi giờ gửi report thành 09:00`\n\n"
        "Hiện tại mình có thể cập nhật trực tiếp interval auto sinh log. "
        "Các interval khác mình sẽ cần bạn xác nhận trước khi thay đổi cấu hình."
    )


def _clarify_interval() -> str:
    return (
        "Bạn muốn đổi interval nào?\n"
        "- Interval auto sinh log: ví dụ `đổi interval sinh log 120 giây`\n"
        "- Interval scan alert realtime: ví dụ `đổi scan interval 60 giây`\n"
        "- Lịch report Gmail: ví dụ `đổi giờ gửi report thành 09:00`\n\n"
        "Mình sẽ không tự đoán khi câu lệnh có thể ảnh hưởng vận hành. Anh chọn đúng mục cần đổi, "
        "mình sẽ xử lý theo hướng an toàn nhất."
    )


def _clarify_operational_change() -> str:
    return (
        "Mình hiểu đây là yêu cầu thay đổi cấu hình hoặc hành vi runtime, nhưng câu lệnh còn thiếu ngữ cảnh.\n\n"
        "Anh vui lòng nói rõ mục tiêu cần đổi theo một trong các mẫu sau:\n"
        "- `đổi interval sinh log 120 giây`\n"
        "- `tạm dừng alert đến 17:30`\n"
        "- `tạm dừng report trong 30 phút`\n"
        "- `đổi giờ gửi report thành 09:00`\n"
        "- `đổi scan interval 60 giây`\n"
        "- `đổi severity alert thành warning,error,critical`\n\n"
        "Nguyên tắc mới của mình: nếu một câu có thể làm thay đổi Telegram, Gmail, scheduler, "
        "generator hoặc cấu hình cảnh báo mà chưa đủ target/value/time, mình sẽ hỏi lại trước."
    )


def _clarify_delivery() -> str:
    return (
        "Anh muốn mình gửi nội dung gì và qua kênh nào?\n\n"
        "Một vài mẫu rõ nghĩa:\n"
        "- `gửi báo cáo hôm nay qua Gmail`\n"
        "- `gửi summary critical qua Telegram`\n"
        "- `export CSV alert hôm nay`\n"
        "- `tạo PDF report 24 giờ gần nhất`\n\n"
        "Nếu là thao tác gửi thật, anh có thể bỏ chọn Dry run delivery trên UI."
    )


def _explain_scan_interval_change(question: str) -> str:
    interval_seconds = _parse_interval_seconds(question)
    interval_text = f"{interval_seconds:g} giây" if interval_seconds is not None else "mốc anh chỉ định"
    return (
        "Mình hiểu anh muốn đổi interval scan alert realtime.\n\n"
        f"- Interval mong muốn: {interval_text}\n"
        "- Đây là chu kỳ scheduler dùng để quét log mới và gửi alert.\n"
        "- Bản hiện tại chưa tự đổi scan interval trực tiếp trong runtime chat để tránh ảnh hưởng luồng alert.\n\n"
        "Nếu anh muốn đổi thật, anh xác nhận lại theo mẫu: "
        "`xác nhận đổi scan interval 60 giây và redeploy`. Khi đó mình sẽ cập nhật cấu hình/deploy ở bước ngoài UI."
    )


def _explain_report_schedule_change(question: str) -> str:
    return (
        "Mình hiểu anh muốn đổi lịch gửi Gmail report.\n\n"
        "- Đây là cấu hình scheduler của report hằng ngày.\n"
        "- Agent đang ưu tiên hỏi lại trước vì đổi lịch report có thể làm thay đổi thời điểm gửi email thật.\n\n"
        "Anh xác nhận theo mẫu: `xác nhận đổi giờ gửi report thành 09:00 Asia/Ho_Chi_Minh`. "
        "Sau đó mình sẽ cập nhật cấu hình/deploy ở bước ngoài UI."
    )


def _filter_by_question(events: list[LogEvent], question: str) -> list[LogEvent]:
    q = _normalize(question)
    domains = [domain for domain in DOMAINS if domain in q]
    severities = [severity for severity in SEVERITIES if severity in q]
    if "nghiem trong" in q or "khan" in q:
        severities.append("critical")
    if "canh bao" in q:
        severities.append("warning")
    if "loi" in q:
        severities.append("error")

    if not domains and not severities:
        return events

    filtered = []
    for event in events:
        if domains and event.domain not in domains:
            continue
        if severities and event.severity not in set(severities):
            continue
        filtered.append(event)
    return filtered


def _has_filters(question: str) -> bool:
    q = _normalize(question)
    return (
        any(domain in q for domain in DOMAINS)
        or any(severity in q for severity in SEVERITIES)
        or "nghiem trong" in q
        or "khan" in q
        or "canh bao" in q
        or "loi" in q
    )


def _sort_events(events: list[LogEvent]) -> list[LogEvent]:
    return sorted(
        events,
        key=lambda event: (SEVERITY_ORDER.get(event.severity, 99), event.domain, event.source, event.event_type),
    )


def _window_label(settings: Settings, question: str) -> str:
    filters = []
    q = _normalize(question)
    filters.extend(domain for domain in DOMAINS if domain in q)
    filters.extend(severity for severity in SEVERITIES if severity in q)
    suffix = f" | Filter: {', '.join(filters)}" if filters else ""
    return f"Last {settings.report_lookback_hours} hours{suffix}"


def _looks_like_pause(q: str) -> bool:
    return any(term in q for term in ["tam dung", "tam ngung", "pause", "stop temporarily", "mute", "disable"])


def _looks_like_resume(q: str) -> bool:
    if any(term in q for term in ["bat lai", "resume", "enable", "mo lai"]):
        return True
    return "tiep tuc" in q and any(
        term in q
        for term in [
            "telegram",
            "alert",
            "canh bao",
            "report",
            "bao cao",
            "gmail",
            "mail",
            "sinh log",
            "incident",
            "su co",
            "rca",
            "tat ca",
        ]
    )


def _looks_like_interval_update(q: str) -> bool:
    generator_terms = [
        "sinh log",
        "generate log",
        "generator",
        "auto log",
        "incident log",
        "incident generator",
        "rca log",
        "log su co",
    ]
    interval_terms = ["interval", "chu ky", "tan suat", "every", "moi"]

    if any(term in q for term in generator_terms) and (
        any(term in q for term in interval_terms) or _has_change_term(q)
    ):
        return True
    if "demo_log_interval_seconds" in q and _parse_interval_seconds(q) is not None:
        return True

    return False


def _looks_like_interval_clarification(q: str) -> bool:
    interval_terms = ["interval", "chu ky", "tan suat"]
    generator_terms = [
        "sinh log",
        "generate log",
        "generator",
        "auto log",
        "incident log",
        "incident generator",
        "rca log",
        "log su co",
    ]
    if any(term in q for term in generator_terms):
        return False
    return (
        any(term in q for term in interval_terms)
        and _has_change_term(q)
        and _parse_interval_seconds(q) is not None
    )


def _looks_like_scan_interval_update(q: str) -> bool:
    if _parse_interval_seconds(q) is None or not _has_change_term(q):
        return False
    return (
        ("scan" in q and any(term in q for term in ["interval", "chu ky", "tan suat"]))
        or ("realtime" in q and "alert" in q)
        or ("alert" in q and any(term in q for term in ["interval", "chu ky", "tan suat"]))
    )


def _looks_like_report_schedule_update(q: str) -> bool:
    if not _has_change_term(q):
        return False
    report_terms = ["report", "bao cao", "gmail", "email", "mail"]
    schedule_terms = ["lich", "schedule", "gio gui", "thoi gian gui", "send time"]
    has_clock = bool(re.search(r"\b\d{1,2}(?::|h)\d{0,2}\b", q))
    return any(term in q for term in report_terms) and (any(term in q for term in schedule_terms) or has_clock)


def _looks_like_operational_change_clarification(q: str) -> bool:
    if not _has_change_term(q):
        return False
    if any(term in q for term in ["sinh log", "generate log", "generator", "auto log"]):
        return False
    if any(term in q for term in ["scan interval", "doi scan", "lich report", "gio gui report"]):
        return False
    operational_terms = [
        "config",
        "cau hinh",
        "setting",
        "tham so",
        "parameter",
        "threshold",
        "nguong",
        "severity",
        "level",
        "muc canh bao",
        "kenh",
        "channel",
        "model",
        "runtime",
        "scheduler",
        "telegram",
        "gmail",
        "email",
        "alert",
        "report",
        "bao cao",
        "log",
    ]
    return any(term in q for term in operational_terms)


def _looks_like_delivery_clarification(q: str) -> bool:
    if not any(term in q for term in ["gui", "send"]):
        return False
    if any(term in q for term in ["command", "lenh", "runbook", "xu ly", "khac phuc", "phan tich"]):
        return False
    delivery_targets = ["bao cao", "report", "gmail", "mail", "email", "telegram", "alert", "csv", "pdf", "file"]
    return not any(term in q for term in delivery_targets)


def _has_change_term(q: str) -> bool:
    return any(_contains_term(q, term) for term in CHANGE_TERMS)


def _contains_term(q: str, term: str) -> bool:
    if " " in term or "_" in term:
        return term in q
    return bool(re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", q))


def _control_targets(question: str, default_all: bool) -> list[str]:
    q = _normalize(question)
    targets = []

    if any(term in q for term in ["tat ca", "all", "everything"]):
        return [
            CONTROL_TELEGRAM_ALERTS,
            CONTROL_EMAIL_REPORTS,
            CONTROL_LOG_GENERATION,
            CONTROL_INCIDENT_GENERATION,
        ]

    if any(term in q for term in ["telegram", "alert", "canh bao"]):
        targets.append(CONTROL_TELEGRAM_ALERTS)
    if any(term in q for term in ["report", "bao cao", "gmail", "email", "mail"]):
        targets.append(CONTROL_EMAIL_REPORTS)
    if _mentions_incident_generator(q):
        targets.append(CONTROL_INCIDENT_GENERATION)
    elif any(term in q for term in ["sinh log", "generate log", "generator", "auto log"]):
        targets.append(CONTROL_LOG_GENERATION)

    if not targets and default_all:
        return [
            CONTROL_TELEGRAM_ALERTS,
            CONTROL_EMAIL_REPORTS,
            CONTROL_LOG_GENERATION,
            CONTROL_INCIDENT_GENERATION,
        ]
    return _dedupe(targets)


def _control_label(name: str) -> str:
    labels = {
        CONTROL_TELEGRAM_ALERTS: "Telegram alerts",
        CONTROL_EMAIL_REPORTS: "Gmail scheduled reports",
        CONTROL_LOG_GENERATION: "auto log generation",
        CONTROL_INCIDENT_GENERATION: "auto incident log generation",
    }
    return labels.get(name, name)


def _mentions_incident_generator(q: str) -> bool:
    return any(
        term in q
        for term in [
            "incident log",
            "incident generator",
            "log incident",
            "log su co",
            "sinh incident",
            "sinh su co",
            "rca log",
            "root cause log",
        ]
    )


def _parse_until(question: str) -> datetime | None:
    q = _normalize(question)
    now = now_in_app_timezone()

    relative = re.search(
        r"(?:trong|for|sau)?\s*(\d+(?:[\.,]\d+)?)\s*(phut|minute|minutes|min|gio|hour|hours|giay|second|seconds|sec)",
        q,
    )
    if relative:
        amount = float(relative.group(1).replace(",", "."))
        unit = relative.group(2)
        if unit in {"giay", "second", "seconds", "sec"}:
            return now + timedelta(seconds=amount)
        if unit in {"phut", "minute", "minutes", "min"}:
            return now + timedelta(minutes=amount)
        return now + timedelta(hours=amount)

    full_datetime = re.search(
        r"(\d{4}-\d{2}-\d{2})[ t]+(\d{1,2})(?::|h)(\d{2})?",
        q,
    )
    if full_datetime:
        date_part = full_datetime.group(1)
        hour = int(full_datetime.group(2))
        minute = int(full_datetime.group(3) or "0")
        candidate = datetime.fromisoformat(f"{date_part}T{hour:02d}:{minute:02d}:00")
        candidate = candidate.replace(tzinfo=now.tzinfo)
        return candidate

    clock = re.search(r"(?:den|toi|until)\s+(\d{1,2})(?::|h)(\d{2})?", q)
    if clock:
        hour = int(clock.group(1))
        minute = int(clock.group(2) or "0")
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    return None


def _parse_interval_seconds(question: str) -> float | None:
    q = _normalize(question)
    match = re.search(
        r"(\d+(?:[\.,]\d+)?)\s*(giay|second|seconds|sec|s|phut|minute|minutes|min|m|gio|hour|hours|h)",
        q,
    )
    if not match:
        return None

    value = float(match.group(1).replace(",", "."))
    unit = match.group(2)
    if unit in {"giay", "second", "seconds", "sec", "s"}:
        return value
    if unit in {"phut", "minute", "minutes", "min", "m"}:
        return value * 60
    return value * 3600


def _dedupe(items: list[str]) -> list[str]:
    result = []
    for item in items:
        if item not in result:
            result.append(item)
    return result


def _normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("đ", "d").replace("Đ", "d")
    replacements = {
        "á": "a",
        "à": "a",
        "ả": "a",
        "ã": "a",
        "ạ": "a",
        "ă": "a",
        "ắ": "a",
        "ằ": "a",
        "ẳ": "a",
        "ẵ": "a",
        "ặ": "a",
        "â": "a",
        "ấ": "a",
        "ầ": "a",
        "ẩ": "a",
        "ẫ": "a",
        "ậ": "a",
        "é": "e",
        "è": "e",
        "ẻ": "e",
        "ẽ": "e",
        "ẹ": "e",
        "ê": "e",
        "ế": "e",
        "ề": "e",
        "ể": "e",
        "ễ": "e",
        "ệ": "e",
        "í": "i",
        "ì": "i",
        "ỉ": "i",
        "ĩ": "i",
        "ị": "i",
        "ó": "o",
        "ò": "o",
        "ỏ": "o",
        "õ": "o",
        "ọ": "o",
        "ô": "o",
        "ố": "o",
        "ồ": "o",
        "ổ": "o",
        "ỗ": "o",
        "ộ": "o",
        "ơ": "o",
        "ớ": "o",
        "ờ": "o",
        "ở": "o",
        "ỡ": "o",
        "ợ": "o",
        "ú": "u",
        "ù": "u",
        "ủ": "u",
        "ũ": "u",
        "ụ": "u",
        "ư": "u",
        "ứ": "u",
        "ừ": "u",
        "ử": "u",
        "ữ": "u",
        "ự": "u",
        "ý": "y",
        "ỳ": "y",
        "ỷ": "y",
        "ỹ": "y",
        "ỵ": "y",
        "đ": "d",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text
