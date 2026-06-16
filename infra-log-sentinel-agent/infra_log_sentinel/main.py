from __future__ import annotations

import argparse
from collections import Counter
import sys

from .chat.log_chat import run_interactive_chat
from .chat.responder import answer_or_execute_chat
from .config import load_settings
from .analysis.time_window import filter_events_by_lookback
from .ingestion.local_folder import initialize_log_cursors, iter_log_lines, iter_new_log_lines
from .notifications.gmail_sender import GmailConfigError, GmailSendError, send_report_email
from .notifications.telegram_sender import (
    TelegramConfigError,
    TelegramSendError,
    check_telegram_health,
    send_telegram_alerts,
)
from .notifications.telegram_chat import (
    initialize_telegram_update_cursor,
    run_telegram_chat_forever,
    run_telegram_chat_once,
)
from .parsing.log_parser import parse_raw_lines
from .reporting.pdf_report import build_pdf_report
from .scheduler.runner import run_scheduler_forever, run_scheduler_once
from .simulator.log_generator import generate_log_lines
from .state.log_cursor import LogCursorStore


def main() -> None:
    _configure_console_encoding()
    parser = argparse.ArgumentParser(description="Infrastructure Log Sentinel Agent")
    parser.add_argument("--scan", action="store_true", help="Scan local log folder and print summary")
    parser.add_argument("--report", action="store_true", help="Generate a PDF report from local logs")
    parser.add_argument("--email-report", action="store_true", help="Generate a PDF report and send it through Gmail")
    parser.add_argument("--telegram-alerts", action="store_true", help="Send Telegram alerts for configured severities")
    parser.add_argument("--telegram-health", action="store_true", help="Test Telegram bot connectivity and chat delivery")
    parser.add_argument(
        "--telegram-chat",
        action="store_true",
        help="Run Telegram chat bridge loop",
    )
    parser.add_argument(
        "--telegram-chat-once",
        action="store_true",
        help="Process one Telegram chat bridge cycle",
    )
    parser.add_argument(
        "--init-telegram-chat",
        action="store_true",
        help="Mark current Telegram updates as already consumed",
    )
    parser.add_argument("--init-log-cursor", action="store_true", help="Mark current log folder content as already consumed")
    parser.add_argument("--new-only", action="store_true", help="Process only new log lines since the last cursor update")
    parser.add_argument("--scheduler", action="store_true", help="Run the local scheduler loop")
    parser.add_argument("--scheduler-once", action="store_true", help="Run one scheduler cycle for local verification")
    parser.add_argument("--chat", nargs="?", default=None, const="", help="Ask a local question about parsed logs")
    parser.add_argument("--generate-logs", type=int, default=0, help="Append synthetic log lines to LOG_ROOT_PATH")
    parser.add_argument("--generate-log-interval", type=float, default=0.0, help="Seconds to wait between generated log lines")
    parser.add_argument("--generate-log-domain", default="all", help="Synthetic log domain: all, network, linux, windows, vmware")
    parser.add_argument("--generate-log-severity", default="abnormal", help="Synthetic log severity: abnormal, all, info, warning, error, critical")
    parser.add_argument("--dry-run", action="store_true", help="Preview delivery actions without sending messages")
    parser.add_argument("--max-alerts", type=int, default=None, help="Limit alert count for local testing")
    args = parser.parse_args()

    settings = load_settings()
    if (
        not args.scan
        and not args.report
        and not args.email_report
        and not args.telegram_alerts
        and not args.telegram_health
        and not args.telegram_chat
        and not args.telegram_chat_once
        and not args.init_telegram_chat
        and not args.init_log_cursor
        and not args.scheduler
        and not args.scheduler_once
        and args.chat is None
        and not args.generate_logs
    ):
        print("Infrastructure Log Sentinel Agent")
        print(f"Environment: {settings.app_env}")
        print(f"Log source mode: {settings.log_source_mode}")
        print(f"Log root path: {settings.log_root_path}")
        print(f"Report time: {settings.report_time}")
        print(f"Report lookback: {settings.report_lookback_hours}h")
        print("Run with --scan to parse sample logs.")
        print("Run with --report to generate a PDF report.")
        print("Run with --email-report to generate and send a PDF report through Gmail.")
        print("Run with --telegram-alerts to send warning/error/critical alerts through Telegram.")
        print("Run with --telegram-health to test Telegram connectivity.")
        print("Run with --telegram-chat to answer Telegram messages through the configured chat.")
        print("Run with --init-log-cursor to baseline existing logs before realtime alerting.")
        print("Run with --scheduler to start the local scheduler loop.")
        print("Run with --chat \"your question\" to ask about parsed logs.")
        print("Run with --generate-logs 5 to append synthetic logs for realtime testing.")
        return

    events = []
    raw_lines_count = 0
    needs_logs = (
        args.scan
        or args.report
        or args.email_report
        or (args.telegram_alerts and not args.new_only)
        or args.chat is not None
    )
    if needs_logs:
        raw_lines = list(iter_log_lines(settings.log_root_path))
        raw_lines_count = len(raw_lines)
        events = parse_raw_lines(raw_lines)

    if args.init_log_cursor:
        file_count = initialize_log_cursors(
            log_root_path=settings.log_root_path,
            cursor_store=LogCursorStore(settings.state_db_path),
        )
        print(f"Initialized realtime log cursor for {file_count} log file(s). Future --new-only scans read appended lines only.")

    if args.generate_logs:
        try:
            generated = generate_log_lines(
                log_root_path=settings.log_root_path,
                count=args.generate_logs,
                interval_seconds=args.generate_log_interval,
                domain=args.generate_log_domain,
                severity=args.generate_log_severity,
            )
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        print(f"Generated {len(generated)} synthetic log line(s) into {settings.log_root_path}.")
        for item in generated:
            print(f"- [{item.severity.upper()}] {item.domain} -> {item.path.name}: {item.text}")

    if args.scan:
        _print_scan_summary(raw_lines_count=raw_lines_count, events=events, alert_levels=settings.severity_alert_levels)

    report_path = None
    if args.report or args.email_report:
        report_events = filter_events_by_lookback(
            events,
            lookback_hours=settings.report_lookback_hours,
        )
        report_path = build_pdf_report(
            events=report_events,
            output_dir=settings.report_output_dir,
            alert_levels=settings.severity_alert_levels,
            report_window_label=f"Last {settings.report_lookback_hours} hours",
        )
        print(
            f"PDF report generated: {report_path} "
            f"({len(report_events)} event(s) in last {settings.report_lookback_hours}h)"
        )

    if args.email_report:
        try:
            result = send_report_email(settings=settings, report_path=report_path, dry_run=args.dry_run)
        except (GmailConfigError, GmailSendError) as exc:
            raise SystemExit(str(exc)) from exc
        print(result.message)

    if args.telegram_alerts:
        if args.new_only:
            cursor_store = LogCursorStore(settings.state_db_path)
            raw_lines = list(
                iter_new_log_lines(
                    settings.log_root_path,
                    cursor_store,
                    update_cursor=not args.dry_run,
                )
            )
            events = parse_raw_lines(raw_lines)
            print(f"Realtime alert scan read {len(raw_lines)} new log line(s).")
        try:
            result = send_telegram_alerts(
                settings=settings,
                events=events,
                dry_run=args.dry_run,
                max_alerts=args.max_alerts,
            )
        except (TelegramConfigError, TelegramSendError) as exc:
            raise SystemExit(str(exc)) from exc
        print(result.message)

    if args.telegram_health:
        try:
            print(check_telegram_health(settings))
        except (TelegramConfigError, TelegramSendError) as exc:
            raise SystemExit(str(exc)) from exc

    if args.init_telegram_chat:
        try:
            consumed_count = initialize_telegram_update_cursor(settings)
        except (TelegramConfigError, TelegramSendError) as exc:
            raise SystemExit(str(exc)) from exc
        print(
            "Initialized Telegram chat cursor. "
            f"Marked {consumed_count} existing update(s) as consumed."
        )

    if args.telegram_chat_once:
        try:
            responder = _build_chat_responder(settings, args.dry_run, channel="telegram")
            result = run_telegram_chat_once(
                settings=settings,
                responder=responder,
                dry_run=args.dry_run,
            )
        except (TelegramConfigError, TelegramSendError) as exc:
            raise SystemExit(str(exc)) from exc
        print(result.message)

    if args.telegram_chat:
        try:
            responder = _build_chat_responder(settings, args.dry_run, channel="telegram")
            run_telegram_chat_forever(
                settings=settings,
                responder=responder,
                dry_run=args.dry_run,
            )
        except (TelegramConfigError, TelegramSendError) as exc:
            raise SystemExit(str(exc)) from exc

    if args.scheduler_once:
        try:
            result = run_scheduler_once(
                settings=settings,
                dry_run=args.dry_run,
                max_alerts=args.max_alerts,
            )
        except (GmailConfigError, GmailSendError, TelegramConfigError, TelegramSendError) as exc:
            raise SystemExit(str(exc)) from exc
        print(result.as_text())

    if args.scheduler:
        try:
            run_scheduler_forever(
                settings=settings,
                dry_run=args.dry_run,
                max_alerts=args.max_alerts,
            )
        except (GmailConfigError, GmailSendError, TelegramConfigError, TelegramSendError) as exc:
            raise SystemExit(str(exc)) from exc

    if args.chat is not None:
        if args.chat:
            print(_answer_or_execute_chat(settings, args.chat, args.dry_run, channel="cli"))
        else:
            responder = _build_chat_responder(settings, args.dry_run, channel="cli")
            run_interactive_chat(
                events,
                settings.severity_alert_levels,
                responder=responder,
            )


def _print_scan_summary(raw_lines_count: int, events: list, alert_levels: tuple[str, ...]) -> None:
    severity_counts = Counter(event.severity for event in events)
    domain_counts = Counter(event.domain for event in events)

    print("Infrastructure Log Sentinel Agent - Scan Summary")
    print(f"Raw lines: {raw_lines_count}")
    print(f"Parsed events: {len(events)}")
    print(f"By severity: {dict(sorted(severity_counts.items()))}")
    print(f"By domain: {dict(sorted(domain_counts.items()))}")
    print()
    print("Alerts:")
    alert_set = set(alert_levels)
    for event in events:
        if event.severity not in alert_set:
            continue
        print(
            f"- [{event.severity.upper()}] {event.domain}/{event.source} "
            f"{event.event_type}: {event.message}"
        )


def _answer_or_execute_chat(settings, question: str, dry_run: bool, channel: str = "cli") -> str:
    return answer_or_execute_chat(settings, question, dry_run=dry_run, channel=channel)


def _build_chat_responder(settings, dry_run: bool, channel: str = "cli"):
    def responder(question: str) -> str:
        return _answer_or_execute_chat(settings, question, dry_run, channel=channel)

    return responder


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    main()
