from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_timezone: str
    log_source_mode: str
    log_root_path: Path
    runtime_log_bootstrap_enabled: bool
    demo_log_bootstrap_count: int
    demo_log_generator_enabled: bool
    demo_log_interval_seconds: float
    demo_log_domain: str
    demo_log_severity: str
    incident_log_generator_enabled: bool
    incident_log_interval_seconds: float
    runtime_scheduler_enabled: bool
    runtime_scheduler_dry_run: bool
    runtime_scheduler_max_alerts: int | None
    runtime_scheduler_max_escalations: int | None
    report_time: str
    report_lookback_hours: int
    scan_interval_seconds: int
    escalation_timeout_seconds: int
    severity_alert_levels: tuple[str, ...]
    state_db_path: Path
    report_output_dir: Path
    gmail_address: str
    gmail_app_password: str
    report_recipient_email: str
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_ack_keywords: tuple[str, ...]
    telegram_chat_enabled: bool
    telegram_chat_poll_interval_seconds: float
    telegram_chat_dry_run: bool
    llm_provider: str
    llm_api_base: str
    llm_api_key: str
    llm_model: str


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    value = os.getenv(name, default)
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _optional_int_env(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    return int(value)


def load_settings(env_file: str | None = None) -> Settings:
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()

    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        app_timezone=os.getenv("APP_TIMEZONE", "Asia/Ho_Chi_Minh"),
        log_source_mode=os.getenv("LOG_SOURCE_MODE", "local_folder"),
        log_root_path=Path(os.getenv("LOG_ROOT_PATH", "samples/logs")),
        runtime_log_bootstrap_enabled=_bool_env("RUNTIME_LOG_BOOTSTRAP_ENABLED", False),
        demo_log_bootstrap_count=int(os.getenv("DEMO_LOG_BOOTSTRAP_COUNT", "0")),
        demo_log_generator_enabled=_bool_env("DEMO_LOG_GENERATOR_ENABLED", False),
        demo_log_interval_seconds=float(os.getenv("DEMO_LOG_INTERVAL_SECONDS", "30")),
        demo_log_domain=os.getenv("DEMO_LOG_DOMAIN", "all"),
        demo_log_severity=os.getenv("DEMO_LOG_SEVERITY", "abnormal"),
        incident_log_generator_enabled=_bool_env("INCIDENT_LOG_GENERATOR_ENABLED", False),
        incident_log_interval_seconds=float(os.getenv("INCIDENT_LOG_INTERVAL_SECONDS", "300")),
        runtime_scheduler_enabled=_bool_env("RUNTIME_SCHEDULER_ENABLED", False),
        runtime_scheduler_dry_run=_bool_env("RUNTIME_SCHEDULER_DRY_RUN", True),
        runtime_scheduler_max_alerts=_optional_int_env("RUNTIME_SCHEDULER_MAX_ALERTS"),
        runtime_scheduler_max_escalations=_optional_int_env("RUNTIME_SCHEDULER_MAX_ESCALATIONS"),
        report_time=os.getenv("REPORT_TIME", "09:00"),
        report_lookback_hours=int(os.getenv("REPORT_LOOKBACK_HOURS", "24")),
        scan_interval_seconds=int(os.getenv("SCAN_INTERVAL_SECONDS", "60")),
        escalation_timeout_seconds=int(os.getenv("ESCALATION_TIMEOUT_SECONDS", "300")),
        severity_alert_levels=_csv_env("SEVERITY_ALERT_LEVELS", "warning,error,critical"),
        state_db_path=Path(os.getenv("STATE_DB_PATH", "data/infra_log_sentinel.sqlite")),
        report_output_dir=Path(os.getenv("REPORT_OUTPUT_DIR", "reports")),
        gmail_address=os.getenv("GMAIL_ADDRESS", ""),
        gmail_app_password=os.getenv("GMAIL_APP_PASSWORD", ""),
        report_recipient_email=os.getenv("REPORT_RECIPIENT_EMAIL", ""),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        telegram_ack_keywords=_csv_env("TELEGRAM_ACK_KEYWORDS", "ACK,ack,noted,da nhan"),
        telegram_chat_enabled=_bool_env("TELEGRAM_CHAT_ENABLED", False),
        telegram_chat_poll_interval_seconds=float(
            os.getenv("TELEGRAM_CHAT_POLL_INTERVAL_SECONDS", "3")
        ),
        telegram_chat_dry_run=_bool_env("TELEGRAM_CHAT_DRY_RUN", False),
        llm_provider=os.getenv("LLM_PROVIDER", "greennode"),
        llm_api_base=os.getenv("LLM_API_BASE", os.getenv("LLM_BASE_URL", os.getenv("AIP_BASE_URL", ""))),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=os.getenv("LLM_MODEL", ""),
    )
