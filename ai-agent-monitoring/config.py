"""
Central configuration for the AI Alert RCA Agent.
All runtime settings are loaded from environment variables and/or config.yaml.
Never hardcode secrets here.
"""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Pydantic config models (mirrors config.yaml schema)
# ---------------------------------------------------------------------------

class AgentConfig(BaseModel):
    batch_window_minutes: int = 5
    command_timeout_seconds: int = 20
    max_alerts_per_batch: int = 50
    default_confidence_threshold: str = "medium"


class SystemContextConfig(BaseModel):
    infrastructure_type: str = "on_premise"
    critical_environments: list[str] = ["prod"]
    critical_services: list[str] = ["payment-api", "auth-service", "database", "gateway"]
    low_relevance_keywords: list[str] = [
        "cloud load balancer",
        "aws autoscaling",
        "gcp cloud run",
        "azure app service",
    ]


class TelegramConfig(BaseModel):
    bot_token_env: str = "TELEGRAM_BOT_TOKEN"
    chat_id_env: str = "TELEGRAM_CHAT_ID"


class SSHConfig(BaseModel):
    username_env: str = "SSH_USERNAME"
    private_key_path_env: str = "SSH_PRIVATE_KEY_PATH"
    bastion_host_env: str = "BASTION_HOST"
    allowed_commands: list[str] = Field(default_factory=lambda: [
        "uptime", "free -m", "du -sh", "df -h", "df -ih",
        "top -b -n 1", "ps aux", "vmstat", "mpstat",
        "ss", "ip addr", "ip route", "systemctl status",
        "journalctl", "tail", "grep", "lsblk", "dmesg",
        "kubectl get pods", "kubectl describe pod", "kubectl logs", "kubectl top pod",
        "ping -c 4", "ss -s", "ss -tulpen",
    ])


class MetricsConfig(BaseModel):
    prometheus_url_env: str = "PROMETHEUS_URL"
    allow_direct_instance_metrics: bool = True


class MonitoringConfig(BaseModel):
    alertmanager_url: str = "http://54.82.62.233:9093"
    network_monitoring_enabled: bool = False   # tắt: chỉ server; bật: thêm CheckMK
    correlation_enabled: bool = True


class CheckMKConfig(BaseModel):
    url_env: str = "CHECKMK_URL"
    username_env: str = "CHECKMK_USERNAME"
    secret_env: str = "CHECKMK_AUTOMATION_SECRET"


class AppConfig(BaseModel):
    agent: AgentConfig = AgentConfig()
    system_context: SystemContextConfig = SystemContextConfig()
    telegram: TelegramConfig = TelegramConfig()
    ssh: SSHConfig = SSHConfig()
    metrics: MetricsConfig = MetricsConfig()
    monitoring: MonitoringConfig = MonitoringConfig()
    checkmk: CheckMKConfig = CheckMKConfig()


# ---------------------------------------------------------------------------
# Environment settings (from .env)
# ---------------------------------------------------------------------------

class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM (GreenNode AIP / OpenAI-compatible)
    llm_model: str = ""
    llm_base_url: str = ""
    llm_api_key: str = ""

    # Teams
    teams_webhook_url: str = ""

    # SSH
    ssh_username: str = ""
    ssh_private_key_path: str = ""
    bastion_host: str = ""

    # Metrics
    prometheus_url: str = ""

    # CheckMK (only used when network_monitoring_enabled=true)
    checkmk_url: str = ""
    checkmk_username: str = "automation"
    checkmk_automation_secret: str = ""

    # Mock mode — set MOCK_MODE=true to skip real SSH/metrics (for testing)
    mock_mode: bool = False


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(config_path: Optional[str] = None) -> AppConfig:
    """Load AppConfig from config.yaml (if found) with defaults fallback."""
    path = Path(config_path or os.environ.get("CONFIG_PATH", "config.yaml"))
    if path.exists():
        with open(path) as f:
            raw = yaml.safe_load(f)
        return AppConfig(**raw)
    return AppConfig()


# Singletons — imported by other modules
settings = EnvSettings()
config = load_config()
