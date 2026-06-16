"""
Kubernetes executor — runs kubectl commands for pod/container alerts.
Only uses allowlisted read-only kubectl operations.
"""

import subprocess
from dataclasses import dataclass
from typing import Optional

from config import config, settings
from security.sanitizer import sanitize
from utils.logger import log_command_executed

_K8S_ALLOWED = [
    "kubectl get pods",
    "kubectl describe pod",
    "kubectl logs",
    "kubectl top pod",
    "kubectl get events",
]


@dataclass
class K8sResult:
    command: str
    output: str
    exit_code: int
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "output": sanitize(self.output),
            "exit_code": self.exit_code,
            "error": self.error,
        }


class K8sExecutor:
    def __init__(self):
        self.timeout = config.agent.command_timeout_seconds

    def _is_allowed(self, command: str) -> bool:
        cmd_lower = command.strip().lower()
        return any(cmd_lower.startswith(a.lower()) for a in _K8S_ALLOWED)

    def run(self, command: str, batch_id: str = "") -> K8sResult:
        if not self._is_allowed(command):
            return K8sResult(command=command, output="", exit_code=1,
                             error=f"kubectl command blocked: {command}")

        if settings.mock_mode:
            return K8sResult(command=command, output=f"[MOCK] {command}", exit_code=0)

        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            log_command_executed(batch_id, "k8s", command,
                                 "success" if result.returncode == 0 else "failed")
            return K8sResult(
                command=command,
                output=result.stdout + result.stderr,
                exit_code=result.returncode,
            )
        except subprocess.TimeoutExpired:
            log_command_executed(batch_id, "k8s", command, "timeout")
            return K8sResult(command=command, output="", exit_code=1,
                             error="kubectl command timed out")
        except Exception as exc:  # noqa: BLE001
            return K8sResult(command=command, output="", exit_code=1, error=str(exc))
