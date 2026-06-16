from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import time
import traceback

import schedule

from infra_log_sentinel.config import Settings
from infra_log_sentinel.analysis.time_window import filter_events_by_lookback
from infra_log_sentinel.ingestion.local_folder import iter_log_lines, iter_new_log_lines
from infra_log_sentinel.notifications.gmail_sender import send_report_email
from infra_log_sentinel.notifications.telegram_sender import send_telegram_alerts
from infra_log_sentinel.parsing.log_parser import parse_raw_lines
from infra_log_sentinel.reporting.pdf_report import build_pdf_report
from infra_log_sentinel.state.log_cursor import LogCursorStore
from infra_log_sentinel.state.runtime_control import (
    CONTROL_EMAIL_REPORTS,
    CONTROL_TELEGRAM_ALERTS,
    RuntimeControlStore,
    VALUE_REPORT_TIME,
    VALUE_SCAN_INTERVAL_SECONDS,
)


@dataclass
class SchedulerRunResult:
    messages: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.messages.append(f"{timestamp} | {message}")

    def as_text(self) -> str:
        return "\n".join(self.messages)


def run_scheduler_once(
    settings: Settings,
    dry_run: bool = False,
    max_alerts: int | None = None,
) -> SchedulerRunResult:
    result = SchedulerRunResult()
    result.add("Starting one scheduler cycle.")
    result.add(run_daily_report(settings=settings, dry_run=dry_run))
    result.add(
        run_alert_scan(
            settings=settings,
            dry_run=dry_run,
            max_alerts=max_alerts,
        )
    )
    result.add("Scheduler cycle complete.")
    return result


def run_scheduler_forever(
    settings: Settings,
    dry_run: bool = False,
    max_alerts: int | None = None,
) -> None:
    control_store = RuntimeControlStore(settings.state_db_path)
    current_report_time = ""
    current_scan_interval = 0

    def sync_scheduler_jobs() -> None:
        nonlocal current_report_time, current_scan_interval
        report_time = _runtime_report_time(control_store, settings)
        scan_interval = _runtime_scan_interval_seconds(control_store, settings)
        if report_time == current_report_time and scan_interval == current_scan_interval:
            return
        schedule.clear("daily-report")
        schedule.clear("alert-scan")
        _schedule_daily_report_job(
            report_time=report_time,
            timezone_name=settings.app_timezone,
            job=lambda: _run_job_safely(
                "Daily report job",
                lambda: run_daily_report(settings=settings, dry_run=dry_run),
            ),
        )
        schedule.every(scan_interval).seconds.do(
            lambda: _run_job_safely(
                "Alert scan job",
                lambda: run_alert_scan(settings=settings, dry_run=dry_run, max_alerts=max_alerts),
            )
        ).tag("alert-scan")
        current_report_time = report_time
        current_scan_interval = scan_interval
        print(
            "Scheduler configured. "
            f"Daily report at {report_time} {settings.app_timezone}; "
            f"scan interval {scan_interval}s.",
            flush=True,
        )

    sync_scheduler_jobs()
    while True:
        sync_scheduler_jobs()
        schedule.run_pending()
        time.sleep(1)


def _runtime_report_time(control_store: RuntimeControlStore, settings: Settings) -> str:
    value = control_store.get_value(VALUE_REPORT_TIME)
    if value:
        try:
            datetime.strptime(value, "%H:%M")
            return value
        except ValueError:
            pass
    return settings.report_time


def _schedule_daily_report_job(report_time: str, timezone_name: str, job) -> None:
    schedule.every().day.at(report_time, timezone_name).do(job).tag("daily-report")


def _runtime_scan_interval_seconds(control_store: RuntimeControlStore, settings: Settings) -> int:
    value = control_store.get_value(VALUE_SCAN_INTERVAL_SECONDS)
    if value:
        try:
            seconds = int(float(value))
        except ValueError:
            seconds = settings.scan_interval_seconds
        if 1 <= seconds <= 86400:
            return seconds
    return settings.scan_interval_seconds


def run_daily_report(settings: Settings, dry_run: bool = False) -> str:
    pause_state = RuntimeControlStore(settings.state_db_path).pause_state(CONTROL_EMAIL_REPORTS)
    if pause_state.paused:
        return f"Daily report job skipped: Gmail reports paused until {pause_state.paused_until:%Y-%m-%d %H:%M:%S}."

    events = filter_events_by_lookback(
        _load_events(settings),
        lookback_hours=settings.report_lookback_hours,
    )
    report_path = build_pdf_report(
        events=events,
        output_dir=settings.report_output_dir,
        alert_levels=settings.severity_alert_levels,
        report_window_label=f"Last {settings.report_lookback_hours} hours",
    )
    email_result = send_report_email(
        settings=settings,
        report_path=report_path,
        dry_run=dry_run,
    )
    return (
        f"Daily report job: generated {report_path} "
        f"with {len(events)} event(s) in last {settings.report_lookback_hours}h. "
        f"{email_result.message}"
    )


def run_alert_scan(
    settings: Settings,
    dry_run: bool = False,
    max_alerts: int | None = None,
) -> str:
    cursor_store = LogCursorStore(settings.state_db_path)
    pause_state = RuntimeControlStore(settings.state_db_path).pause_state(CONTROL_TELEGRAM_ALERTS)
    if pause_state.paused:
        raw_lines = list(
            iter_new_log_lines(
                settings.log_root_path,
                cursor_store,
                update_cursor=not dry_run,
            )
        )
        cursor_note = "consumed" if not dry_run else "previewed"
        return (
            f"Alert scan job skipped: Telegram alerts paused until {pause_state.paused_until:%Y-%m-%d %H:%M:%S}. "
            f"Read and {cursor_note} {len(raw_lines)} new log line(s) without sending."
        )

    raw_lines = list(
        iter_new_log_lines(
            settings.log_root_path,
            cursor_store,
            update_cursor=not dry_run,
        )
    )
    events = parse_raw_lines(raw_lines)
    telegram_result = send_telegram_alerts(
        settings=settings,
        events=events,
        dry_run=dry_run,
        max_alerts=max_alerts,
    )
    return f"Alert scan job: read {len(raw_lines)} new log line(s). {telegram_result.message}"


def _load_events(settings: Settings):
    raw_lines = list(iter_log_lines(settings.log_root_path))
    return parse_raw_lines(raw_lines)


def _print_job_result(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{timestamp} | {message}", flush=True)


def _run_job_safely(job_name: str, callback) -> None:
    try:
        _print_job_result(callback())
    except Exception as exc:
        _print_job_result(f"{job_name} failed: {type(exc).__name__}: {exc}")
        traceback.print_exc()
