import base64
import json
import logging
import paramiko
import re
import shlex
from pathlib import Path
from langchain_core.tools import tool

from src.config import SSH_KEY_PATH, SSH_PASSWORD, SCRIPTS_DIR, HARDENING_PROFILES_DIR

logger = logging.getLogger(__name__)

# Map OS type -> check script path
OS_SCRIPTS: dict[str, Path] = {
    "ubuntu": HARDENING_PROFILES_DIR / "ubuntu_24_04" / "verify_config_template.sh",
    "junos": HARDENING_PROFILES_DIR / "juniper_junos" / "verify_config_template.junos",
    "windows": SCRIPTS_DIR / "windows_2022" / "hardening_checks.ps1",
}

OS_PROFILE_DIRS: dict[str, str] = {
    "ubuntu": "ubuntu_24_04",
    "junos": "juniper_junos",
    "windows": "windows_2022",
}


def _load_hardening_profile(os_type: str) -> dict:
    profile_dir_name = OS_PROFILE_DIRS.get(os_type)
    if not profile_dir_name:
        return {}

    profile_dir = HARDENING_PROFILES_DIR / profile_dir_name
    controls_path = profile_dir / "controls.json"
    if os_type == "windows":
        commands_path = profile_dir / "apply_hardening.ps1"
    elif os_type == "junos":
        commands_path = profile_dir / "apply_hardening.set"
    else:
        commands_path = profile_dir / "apply_hardening.sh"
    procedure_path = profile_dir / "post_config_verification.md"
    verification_script_path = profile_dir / "verify_config_template.sh" if os_type == "ubuntu" else None
    if os_type == "junos":
        verification_script_path = profile_dir / "verify_config_template.junos"

    profile: dict = {}
    try:
        profile = json.loads(controls_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Cannot load hardening profile %s: %s", controls_path, exc)
        profile = {"os_type": os_type, "display_name": os_type, "controls": []}

    profile["profile_dir"] = str(profile_dir)
    profile["commands_file"] = str(commands_path)
    profile["verification_procedure_file"] = str(procedure_path) if procedure_path.exists() else ""
    profile["verification_script_file"] = (
        str(verification_script_path) if verification_script_path and verification_script_path.exists() else ""
    )
    try:
        profile["commands"] = commands_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        profile["commands"] = ""
    try:
        profile["verification_procedure"] = procedure_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        profile["verification_procedure"] = ""
    try:
        profile["verification_script"] = verification_script_path.read_text(encoding="utf-8") if verification_script_path else ""
    except (FileNotFoundError, OSError):
        profile["verification_script"] = ""
    return profile


def _format_profile_for_output(profile: dict) -> str:
    controls = profile.get("controls") or []
    if not controls:
        return ""

    lines = [
        "=== CONFIGURED HARDENING PROFILE ===",
        f"[INFO] Profile: {profile.get('display_name', profile.get('os_type', 'unknown'))}",
        f"[INFO] Controls file: {profile.get('profile_dir', '')}",
        f"[INFO] Apply commands file: {profile.get('commands_file', '')}",
        f"[INFO] Verification procedure file: {profile.get('verification_procedure_file', '')}",
        f"[INFO] Verification script file: {profile.get('verification_script_file', '')}",
        f"[INFO] Configured controls: {len(controls)}",
    ]
    for control in controls:
        lines.append(
            "[INFO] {id} | {section} | {setting} => {expected}".format(
                id=control.get("id", "control"),
                section=control.get("section", "GENERAL"),
                setting=control.get("setting", ""),
                expected=control.get("expected", ""),
            )
        )
    return "\n".join(lines)


def _detect_os(client: paramiko.SSHClient) -> str:
    """Detect OS type via uname."""
    _, stdout, _ = client.exec_command("uname -s 2>/dev/null || echo Windows")
    result = stdout.read().decode().strip().lower()
    if "linux" in result:
        return "ubuntu"

    for command in ("show version | match JUNOS | no-more", "cli -c 'show version | match JUNOS | no-more'"):
        try:
            _, stdout, stderr = client.exec_command(command)
            probe = (stdout.read().decode(errors="replace") + stderr.read().decode(errors="replace")).lower()
            if "junos" in probe or "junos:" in probe:
                return "junos"
        except Exception:
            continue
    return "windows"


def _ssh_connect(host: str, port: int, user: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: dict = {"hostname": host, "port": port, "username": user, "timeout": 30}
    if SSH_KEY_PATH:
        kwargs["key_filename"] = SSH_KEY_PATH
    elif SSH_PASSWORD:
        kwargs["password"] = SSH_PASSWORD
    client.connect(**kwargs)
    return client


def _run_script_over_ssh(client: paramiko.SSHClient, script_path: Path) -> str:
    """Execute check script over SSH, return combined stdout+stderr."""
    if script_path.suffix.lower() == ".junos":
        profile = _load_hardening_profile("junos")
        return _run_junos_checks(client, profile)

    script_content = script_path.read_text(encoding="utf-8")
    if script_path.suffix.lower() == ".ps1":
        encoded = base64.b64encode(script_content.encode("utf-16le")).decode("ascii")
        command = f"powershell -NoProfile -ExecutionPolicy Bypass -EncodedCommand {encoded}"
    else:
        command = f"bash -s << 'HARDENING_EOF'\n{script_content}\nHARDENING_EOF"

    _, stdout, stderr = client.exec_command(command)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return out + (f"\n[STDERR]:\n{err}" if err.strip() else "")


def _run_junos_cli(client: paramiko.SSHClient, command: str) -> str:
    """Run a Junos CLI command via SSH, with shell and CLI-mode fallbacks."""
    command = command.strip()
    candidates = [
        f"cli -c {shlex.quote(command)}",
        command,
    ]
    last_output = ""
    for candidate in candidates:
        try:
            _, stdout, stderr = client.exec_command(candidate, timeout=45)
            output = stdout.read().decode(errors="replace")
            error = stderr.read().decode(errors="replace")
            combined = (output + ("\n" + error if error.strip() else "")).strip()
            last_output = combined
            lowered = combined.lower()
            if combined and not any(token in lowered for token in ("unknown command", "syntax error", "not found")):
                return combined
        except Exception as exc:
            last_output = str(exc)
    return last_output


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE) for pattern in patterns if pattern)


def _junos_control_level(control: dict, passed: bool) -> str:
    if passed:
        return "PASS"
    severity = str(control.get("severity") or "fail").lower()
    if severity in {"warn", "warning"}:
        return "WARN"
    if severity == "info":
        return "INFO"
    return "FAIL"


def _evaluate_junos_control(control: dict, config_set: str, op_outputs: dict[str, str]) -> tuple[str, str]:
    source = str(control.get("source") or "config")
    text = config_set if source == "config" else op_outputs.get(source, "")

    match_any = control.get("match_any") or []
    if isinstance(match_any, str):
        match_any = [match_any]
    match_all = control.get("match_all") or []
    if isinstance(match_all, str):
        match_all = [match_all]
    absent_any = control.get("absent_any") or []
    if isinstance(absent_any, str):
        absent_any = [absent_any]

    passed = True
    reasons: list[str] = []

    if match_any:
        found = _matches_any(match_any, text)
        passed = passed and found
        if not found:
            reasons.append("expected pattern not found")

    if match_all:
        missing = [pattern for pattern in match_all if not _matches_any([pattern], text)]
        passed = passed and not missing
        if missing:
            reasons.append(f"missing {len(missing)} required pattern(s)")

    if absent_any:
        present = [pattern for pattern in absent_any if _matches_any([pattern], text)]
        passed = passed and not present
        if present:
            reasons.append(f"forbidden pattern present: {present[0]}")

    level = _junos_control_level(control, passed)
    detail = control.get("check") or control.get("setting") or control.get("id")
    expected = control.get("expected")
    suffix = f" | expected: {expected}" if expected else ""
    if reasons:
        suffix += f" | evidence: {'; '.join(reasons)}"
    return level, f"{control.get('id', 'JUNOS-CONTROL')} | {control.get('section', 'JUNOS')} | {detail}{suffix}"


def _run_junos_checks(client: paramiko.SSHClient, profile: dict) -> str:
    config_set = _run_junos_cli(client, "show configuration | display set | no-more")
    version = _run_junos_cli(client, "show version | no-more")
    system_uptime = _run_junos_cli(client, "show system uptime | no-more")
    commit = _run_junos_cli(client, "show system commit | no-more")
    op_outputs = {
        "version": version,
        "uptime": system_uptime,
        "commit": commit,
    }

    controls = profile.get("controls") or []
    by_section: dict[str, list[dict]] = {}
    for control in controls:
        if isinstance(control, dict):
            by_section.setdefault(str(control.get("section") or "JUNOS"), []).append(control)

    lines = [
        "=== JUNOS DEVICE INFO ===",
        "[INFO] Source | Juniper Junos SSH CLI",
        f"[INFO] Profile | {profile.get('display_name', 'Juniper Junos')}",
    ]
    if version:
        first_version_line = next((line.strip() for line in version.splitlines() if line.strip()), "")
        lines.append(f"[INFO] Version | {first_version_line}")
    if commit:
        first_commit_line = next((line.strip() for line in commit.splitlines() if line.strip()), "")
        lines.append(f"[INFO] Last commit | {first_commit_line}")

    for section, section_controls in by_section.items():
        lines.append("")
        lines.append(f"=== {section} ===")
        for control in section_controls:
            level, message = _evaluate_junos_control(control, config_set, op_outputs)
            lines.append(f"[{level}] {message}")

    if not controls:
        lines.extend(["", "=== JUNOS PROFILE ===", "[WARN] No Junos controls configured."])

    return "\n".join(lines)


def _run_hardening_with_creds(
    host: str, port: int, username: str,
    password: str | None, ssh_key: str | None, os_type: str,
) -> dict:
    """Run hardening check with explicit per-server credentials (called by dashboard)."""
    import tempfile, os as _os

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs: dict = {"hostname": host, "port": port, "username": username, "timeout": 30}

    key_tmp = None
    if ssh_key:
        key_tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False)
        key_tmp.write(ssh_key)
        key_tmp.flush()
        kwargs["key_filename"] = key_tmp.name
    elif password:
        kwargs["password"] = password

    try:
        client.connect(**kwargs)
        if os_type == "auto":
            os_type = _detect_os(client)
        script_path = OS_SCRIPTS.get(os_type)
        if not script_path or not script_path.exists():
            return {"error": f"No script for OS: {os_type}"}
        profile = _load_hardening_profile(os_type)
        output = _run_script_over_ssh(client, script_path)
        profile_output = _format_profile_for_output(profile)
        raw_output = f"{profile_output}\n\n{output}" if profile_output else output
        return {
            "raw_output": raw_output,
            "os_type": os_type,
            "server": f"{username}@{host}:{port}",
            "profile": profile,
        }
    finally:
        client.close()
        if key_tmp:
            key_tmp.close()
            _os.unlink(key_tmp.name)


def _run_hardening_for_server(server_spec: str) -> dict:
    """
    Core function: SSH into server, detect OS, run check script.
    Returns dict with type, server, os, output, status (or error).
    """
    if "@" not in server_spec:
        return {"type": "hardening", "server": server_spec, "error": "Invalid format — use user@host or user@host:port"}

    user, host_part = server_spec.split("@", 1)
    host_port = host_part.split(":")
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 22

    client = _ssh_connect(host, port, user)
    try:
        os_type = _detect_os(client)
        script_path = OS_SCRIPTS.get(os_type)
        if not script_path or not script_path.exists():
            return {"type": "hardening", "server": server_spec, "error": f"No check script for OS type: {os_type}"}

        profile = _load_hardening_profile(os_type)
        output = _run_script_over_ssh(client, script_path)
        profile_output = _format_profile_for_output(profile)
        raw_output = f"{profile_output}\n\n{output}" if profile_output else output
        return {
            "type": "hardening",
            "server": server_spec,
            "os": os_type,
            "output": raw_output[:12000],  # Cap per server
            "status": "completed",
            "profile": {
                "display_name": profile.get("display_name"),
                "controls_count": len(profile.get("controls", [])),
                "commands_file": profile.get("commands_file"),
            },
        }
    finally:
        client.close()


@tool
def run_hardening_check(server_spec: str) -> str:
    """
    Run security hardening checks on a remote Linux, Windows, or Junos target via SSH.

    Executes pre-configured checks and returns the full output for security analysis.
    Detects Ubuntu 24.04, Windows Server 2022, or Juniper Junos where possible.

    Args:
        server_spec: Connection string — "user@host" or "user@host:port".
                     Examples: "root@192.168.1.10", "ubuntu@10.0.0.5:2222"

    Returns:
        Raw check output from the server for analysis.
    """
    try:
        result = _run_hardening_for_server(server_spec)
        if "error" in result:
            return f"[ERROR] {result['server']}: {result['error']}"
        return (
            f"=== Hardening Check: {result['server']} (OS: {result['os']}) ===\n\n"
            f"{result['output']}"
        )
    except Exception as e:
        logger.error(f"Hardening check failed for {server_spec}: {e}")
        return f"[EXCEPTION] Failed to connect to {server_spec}: {e}"
