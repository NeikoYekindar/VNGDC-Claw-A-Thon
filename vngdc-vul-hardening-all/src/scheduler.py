import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import (
    SCHEDULE_HOUR,
    SCHEDULE_MINUTE,
    TIMEZONE,
    HARDENING_SERVERS,
    TEAMS_WEBHOOK_URL,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)

logger = logging.getLogger(__name__)


def daily_security_check() -> None:
    """Entrypoint for daily scheduled security checks at 9 AM."""
    from src.tools.hardening import _run_hardening_for_server
    from src.tools.wazuh import _run_wazuh_scan
    from src.tools.teams import _send_report
    from src.tools.telegram import _send_report as _send_telegram_report

    logger.info("=== Daily security check started ===")
    sections = []

    # 1. Hardening checks for all configured servers
    if not HARDENING_SERVERS:
        logger.warning("No HARDENING_SERVERS configured — skipping hardening checks.")
    for server_spec in HARDENING_SERVERS:
        logger.info(f"Running hardening check: {server_spec}")
        try:
            result = _run_hardening_for_server(server_spec)
            sections.append(result)
        except Exception as e:
            logger.error(f"Hardening check failed for {server_spec}: {e}")
            sections.append({"type": "hardening", "server": server_spec, "error": str(e)})

    # 2. Wazuh vulnerability scan
    logger.info("Running Wazuh vulnerability scan...")
    try:
        vuln_result = _run_wazuh_scan()
        sections.append(vuln_result)
    except Exception as e:
        logger.error(f"Wazuh scan failed: {e}")
        sections.append({"type": "wazuh", "error": str(e)})

    # 3. Send combined report to Teams
    if TEAMS_WEBHOOK_URL:
        try:
            _send_report(title="[Automated] Daily Security Report", sections=sections)
            logger.info("Daily report sent to Microsoft Teams.")
        except Exception as e:
            logger.error(f"Failed to send Teams report: {e}")
    else:
        logger.warning("TEAMS_WEBHOOK_URL not set — report not sent.")

    # 4. Send the same combined report to Telegram when configured
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            _send_telegram_report(title="[Automated] Daily Security Report", sections=sections)
            logger.info("Daily report sent to Telegram.")
        except Exception as e:
            logger.error(f"Failed to send Telegram report: {e}")
    else:
        logger.warning("Telegram bot token/chat id not set; report not sent.")

    logger.info("=== Daily security check completed ===")


def start_scheduler() -> BackgroundScheduler:
    """Start background scheduler. Called once at app startup."""
    scheduler = BackgroundScheduler(timezone=TIMEZONE)
    scheduler.add_job(
        daily_security_check,
        trigger=CronTrigger(
            hour=SCHEDULE_HOUR,
            minute=SCHEDULE_MINUTE,
            timezone=TIMEZONE,
        ),
        id="daily_security_check",
        replace_existing=True,
        misfire_grace_time=300,  # Allow up to 5 min late start
    )
    scheduler.start()
    logger.info(
        f"Scheduler started — daily check at {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} ({TIMEZONE})"
    )
    return scheduler
