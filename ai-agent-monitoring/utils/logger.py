"""
Structured audit logger.
Logs batch events, commands, report status — never logs secrets.
"""

import json
import logging
import sys
from datetime import datetime


# ---------------------------------------------------------------------------
# JSON formatter for structured logs
# ---------------------------------------------------------------------------

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra"):
            payload.update(record.extra)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _make_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

agent_logger = _make_logger("agent")


def log_alert_received(alert_id: str, alert_name: str, instance: str) -> None:
    agent_logger.info("alert_received", extra={
        "extra": {"alert_id": alert_id, "alert_name": alert_name, "instance": instance}
    })


def log_batch_created(batch_id: str, alert_ids: list[str]) -> None:
    agent_logger.info("batch_created", extra={
        "extra": {"batch_id": batch_id, "alert_ids": alert_ids}
    })


def log_batch_processing(batch_id: str, alert_count: int) -> None:
    agent_logger.info("batch_processing_started", extra={
        "extra": {"batch_id": batch_id, "alert_count": alert_count}
    })


def log_command_executed(batch_id: str, instance: str, command: str, status: str) -> None:
    """Log command execution — never log sensitive output."""
    agent_logger.info("command_executed", extra={
        "extra": {
            "batch_id": batch_id,
            "instance": instance,
            "command": command,
            "status": status,  # success | failed | timeout
        }
    })


def log_report_sent(batch_id: str, success: bool, reason: str = "") -> None:
    agent_logger.info("report_sent", extra={
        "extra": {"batch_id": batch_id, "success": success, "reason": reason}
    })


def log_rca_result(batch_id: str, root_cause: str, confidence: str) -> None:
    agent_logger.info("rca_result", extra={
        "extra": {"batch_id": batch_id, "root_cause": root_cause, "confidence": confidence}
    })


def log_error(batch_id: str, error: str) -> None:
    agent_logger.error("agent_error", extra={
        "extra": {"batch_id": batch_id, "error": error}
    })
