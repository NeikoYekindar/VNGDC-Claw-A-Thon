"""
SSH executor — runs allowlisted commands on remote hosts.
Credentials loaded from environment, never hardcoded.
All output is sanitized before returning.
"""

import os
from dataclasses import dataclass
from typing import Optional

from config import config, settings
from executors.command_policy import is_allowed
from security.sanitizer import sanitize
from utils.logger import log_command_executed


@dataclass
class CommandResult:
    command: str
    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.error

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "stdout": sanitize(self.stdout),
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "error": self.error,
        }


class SSHExecutor:
    """Execute allowlisted commands over SSH using key or password auth."""

    def __init__(self):
        self.username = os.environ.get(config.ssh.username_env, "")
        self.key_path = os.environ.get(config.ssh.private_key_path_env, "")
        self.bastion_host = os.environ.get(config.ssh.bastion_host_env, "")
        self.timeout = config.agent.command_timeout_seconds

    def run(self, host: str, command: str, batch_id: str = "") -> CommandResult:
        """Run a single command on remote host. Returns sanitized result."""
        if not is_allowed(command):
            log_command_executed(batch_id, host, command, "blocked")
            return CommandResult(
                command=command,
                stdout="",
                stderr="",
                exit_code=1,
                error=f"Command blocked by policy: {command}",
            )

        if settings.mock_mode:
            return self._mock_run(host, command, batch_id)

        return self._real_run(host, command, batch_id)

    def _real_run(self, host: str, command: str, batch_id: str) -> CommandResult:
        try:
            import paramiko
        except ImportError:
            return CommandResult(command=command, stdout="", stderr="", exit_code=1,
                                 error="paramiko not installed")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            connect_kwargs: dict = {
                "hostname": host,
                "username": self.username,
                "timeout": self.timeout,
            }
            if self.key_path and os.path.exists(self.key_path):
                connect_kwargs["key_filename"] = self.key_path
            elif os.environ.get("SSH_PASSWORD"):
                connect_kwargs["password"] = os.environ["SSH_PASSWORD"]
            else:
                # Try agent key
                connect_kwargs["look_for_keys"] = True

            # Bastion hop if configured
            if self.bastion_host:
                sock = self._open_bastion_channel(host, client)
                connect_kwargs["sock"] = sock

            client.connect(**connect_kwargs)
            stdin, stdout, stderr = client.exec_command(command, timeout=self.timeout)

            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            code = stdout.channel.recv_exit_status()

            log_command_executed(batch_id, host, command, "success" if code == 0 else "failed")
            return CommandResult(command=command, stdout=out, stderr=err, exit_code=code)

        except Exception as exc:  # noqa: BLE001
            status = "timeout" if "timed out" in str(exc).lower() else "failed"
            log_command_executed(batch_id, host, command, status)
            return CommandResult(
                command=command, stdout="", stderr="", exit_code=1,
                timed_out="timed out" in str(exc).lower(),
                error=str(exc),
            )
        finally:
            client.close()

    def _open_bastion_channel(self, target_host: str, _client):
        """Open a socket channel through bastion host."""
        import paramiko
        bastion = paramiko.SSHClient()
        bastion.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if self.key_path:
            bastion.connect(self.bastion_host, username=self.username, key_filename=self.key_path)
        else:
            bastion.connect(self.bastion_host, username=self.username, look_for_keys=True)
        transport = bastion.get_transport()
        return transport.open_channel("direct-tcpip", (target_host, 22), ("", 0))

    def run_multiple(self, host: str, commands: list[str], batch_id: str = "") -> list[CommandResult]:
        """Run multiple commands sequentially on the same host.
        Stops immediately if a connection-level failure is detected (timeout, refused, etc.)
        so we don't waste 20s × N commands trying an unreachable host.
        """
        results = []
        for cmd in commands:
            result = self.run(host, cmd, batch_id)
            results.append(result)
            if result.error and self._is_connection_error(result.error):
                print(
                    f"[SSH] Connection failed to {host} ({result.error[:80]}), "
                    f"skipping {len(commands) - len(results)} remaining commands.",
                    flush=True,
                )
                break
        return results

    @staticmethod
    def _is_connection_error(error: str) -> bool:
        """Return True if error indicates SSH connection failure (not just command failure)."""
        err = error.lower()
        return any(k in err for k in [
            "timed out", "connection refused", "no route to host",
            "name or service not known", "network unreachable",
            "connection reset", "no existing session", "unable to connect",
        ])

    # ------------------------------------------------------------------
    # Mock mode — returns realistic fake output for local testing
    # ------------------------------------------------------------------

    def _mock_run(self, host: str, command: str, batch_id: str) -> CommandResult:
        log_command_executed(batch_id, host, command, "mock")
        mock_outputs = {
            "uptime": " 10:25:01 up 42 days, 3:14,  2 users,  load average: 2.80, 2.75, 2.70",
            "free -m": "              total        used        free\nMem:          16384        14200        2184\nSwap:          2048         512        1536",
            "df -h": "Filesystem      Size  Used Avail Use% Mounted on\n/dev/sda1        50G   47G  3.0G  94% /\n",
            "df -ih": "Filesystem     Inodes IUsed IFree IUse% Mounted on\n/dev/sda1        3.2M  1.1M  2.1M   35% /\n",
        }
        for key, output in mock_outputs.items():
            if command.strip().startswith(key):
                return CommandResult(command=command, stdout=output, stderr="", exit_code=0)
        return CommandResult(
            command=command,
            stdout=f"[MOCK] Output for: {command}",
            stderr="",
            exit_code=0,
        )
