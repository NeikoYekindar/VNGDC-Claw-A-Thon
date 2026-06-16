import os
from pathlib import Path
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv()

# --- GreenNode AgentBase Memory ---
MEMORY_ID = os.environ.get("MEMORY_ID", "")
MEMORY_STRATEGY_ID = os.environ.get("MEMORY_STRATEGY_ID", "default")

# --- LLM: MiniMax (OpenAI-compatible) ---
LLM_MODEL = os.environ.get("LLM_MODEL", "MiniMax-Text-01")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.minimaxi.chat/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

# --- Microsoft Teams Webhook ---
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")

# --- Telegram Bot ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
TELEGRAM_ALLOWED_CHAT_IDS = [
    s.strip() for s in os.environ.get("TELEGRAM_ALLOWED_CHAT_IDS", "").split(",") if s.strip()
]
TELEGRAM_COMMAND_PREFIX = os.environ.get("TELEGRAM_COMMAND_PREFIX", "/agent")

# --- Wazuh ---
WAZUH_HOST = os.environ.get("WAZUH_HOST", "")
WAZUH_PORT = int(os.environ.get("WAZUH_PORT", "55000"))
WAZUH_USER = os.environ.get("WAZUH_USER", "wazuh-wui")
WAZUH_PASSWORD = os.environ.get("WAZUH_PASSWORD", "")
WAZUH_INDEXER_HOST = os.environ.get("WAZUH_INDEXER_HOST", "")
WAZUH_INDEXER_PORT = int(os.environ.get("WAZUH_INDEXER_PORT", "9200"))
WAZUH_INDEXER_USER = os.environ.get("WAZUH_INDEXER_USER", WAZUH_USER)
WAZUH_INDEXER_PASSWORD = os.environ.get("WAZUH_INDEXER_PASSWORD", WAZUH_PASSWORD)
WAZUH_INDEXER_INDEX = os.environ.get("WAZUH_INDEXER_INDEX", "wazuh-states-vulnerabilities*")
WAZUH_INDEXER_VERIFY_SSL = os.environ.get("WAZUH_INDEXER_VERIFY_SSL", "false").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
WAZUH_VULN_BATCH_SIZE = int(os.environ.get("WAZUH_VULN_BATCH_SIZE", "500"))
WAZUH_VULN_MAX_ITEMS = int(os.environ.get("WAZUH_VULN_MAX_ITEMS", "5000"))

# --- SSH credentials for hardening checks ---
# Servers format: "user@host" or "user@host:port", comma-separated
# Example: "root@192.168.1.10,ubuntu@10.0.0.5:2222,netops@10.0.0.20:22"
HARDENING_SERVERS = [
    s.strip() for s in os.environ.get("HARDENING_SERVERS", "").split(",") if s.strip()
]
SSH_KEY_PATH = os.environ.get("SSH_KEY_PATH", "")  # Path to private key file
SSH_PASSWORD = os.environ.get("SSH_PASSWORD", "")   # Fallback password auth

# --- Scheduler ---
SCHEDULE_HOUR = int(os.environ.get("SCHEDULE_HOUR", "9"))
SCHEDULE_MINUTE = int(os.environ.get("SCHEDULE_MINUTE", "0"))
TIMEZONE = os.environ.get("TIMEZONE", "Asia/Ho_Chi_Minh")

# --- Paths ---
BASE_DIR = Path(__file__).parent.parent
PROMPTS_DIR = BASE_DIR / "data" / "prompts"
SCRIPTS_DIR = BASE_DIR / "data" / "scripts"
HARDENING_PROFILES_DIR = BASE_DIR / "data" / "hardening_profiles"


def validate_config() -> None:
    """Raise ValueError if required env vars are missing."""
    missing = []
    if not MEMORY_ID:
        missing.append("MEMORY_ID")
    if not LLM_API_KEY:
        missing.append("LLM_API_KEY")
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill in the values."
        )
