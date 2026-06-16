"""
Build, push, and deploy the all-in-one VNGDC Master Agent runtime to GreenNode AgentBase.

The image contains:
- FastAPI master agent backend
- AgentBase-compatible /health and /invocations routes
- Next.js unified dashboard
- Nginx public reverse proxy on port 8080

Usage:
    python create_dashboard_runtime.py           # Create new runtime
    python create_dashboard_runtime.py update    # Update existing runtime
    python create_dashboard_runtime.py status    # Check status + endpoint
    python create_dashboard_runtime.py build     # Build + push only
    python create_dashboard_runtime.py delete    # Delete runtime

Configuration:
    - Put GREENNODE_CLIENT_ID and GREENNODE_CLIENT_SECRET in .env, .greennode.json,
      or reuse ../vngdc-vul-hardening-all/.env from this workspace.
    - Put runtime environment values in .env.deploy.
    - Set MASTER_RUNTIME_ID after first create, or export it before update/status/delete.
"""

from __future__ import annotations

import base64
import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent

DEFAULT_IMAGE = "vcr.vngcloud.vn/111480-abp111815/vngdc-master-agent:latest"
DEFAULT_FLAVOR_ID = "runtime-s2-general-4x8"
DEFAULT_RUNTIME_NAME = "vngdc-master-agent"
BASE_URL = "https://agentbase.api.vngcloud.vn/runtime/agent-runtimes"
CR_CREDENTIAL_URL = "https://agentbase.api.vngcloud.vn/cr/api/v1/registry-credential"
IAM_TOKEN_URL = "https://iam.api.vngcloud.vn/accounts-api/v2/auth/token"

DEPLOYMENT_ONLY_ENV_KEYS = {
    "GREENNODE_CLIENT_ID",
    "GREENNODE_CLIENT_SECRET",
    "MASTER_RUNTIME_ID",
    "MASTER_IMAGE",
    "MASTER_FLAVOR_ID",
    "MASTER_RUNTIME_NAME",
}

DEFAULT_RUNTIME_ENV = {
    "MONITORING_AGENT_URL": (
        "https://endpoint-dbd6717d-569f-413e-b9da-b63ceda13b22."
        "agentbase-runtime.aiplatform.vngcloud.vn"
    ),
    "LOGGING_AGENT_URL": (
        "https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9."
        "agentbase-runtime.aiplatform.vngcloud.vn"
    ),
    "SECURITY_AGENT_URL": (
        "https://endpoint-c73f7b5b-2611-4304-90bc-c503feb4af38."
        "agentbase-runtime.aiplatform.vngcloud.vn"
    ),
    "MASTER_CHILD_TIMEOUT_SECONDS": "90",
    "MASTER_STATUS_TIMEOUT_SECONDS": "8",
    "MASTER_LLM_SYNTHESIS_ENABLED": "true",
    "MASTER_LLM_TIMEOUT_SECONDS": "60",
    "MASTER_LLM_TEMPERATURE": "0.15",
    "MASTER_LLM_MAX_TOKENS": "3500",
    "LLM_MODEL": "minimax/minimax-m2.5",
    "LLM_BASE_URL": "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1",
    "NEXT_TELEMETRY_DISABLED": "1",
    "PYTHONUNBUFFERED": "1",
}

LLM_ENV_KEYS = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")


def run(cmd: list[str], **kwargs):
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, **kwargs)
    if result.returncode != 0:
        sys.exit(result.returncode)
    return result


def read_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    try:
        with path.open(encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if "#" in value:
                    value = value[: value.index("#")].strip()
                if key and value:
                    env[key] = value
    except FileNotFoundError:
        pass
    return env


def load_local_config() -> dict[str, str]:
    config = {}
    config.update(read_env_file(HERE.parent / ".env"))
    config.update(read_env_file(HERE.parent / "vngdc-vul-hardening-all" / ".env"))
    config.update(read_env_file(HERE.parent / "vngdc-vul-hardening" / ".env"))
    config.update(read_env_file(HERE.parent / "vngdc-vul-harrdening" / ".env"))
    config.update(read_env_file(HERE / ".env"))
    config.update(read_env_file(HERE / ".env.deploy"))
    return config


def deploy_value(key: str, default: str = "") -> str:
    config = load_local_config()
    return os.getenv(key) or config.get(key, default)


def load_greennode_json() -> dict[str, str]:
    try:
        with (HERE / ".greennode.json").open(encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {
        "GREENNODE_CLIENT_ID": str(data.get("client_id") or ""),
        "GREENNODE_CLIENT_SECRET": str(data.get("client_secret") or ""),
    }


def get_token() -> str:
    config = load_local_config()
    if not config.get("GREENNODE_CLIENT_ID") or not config.get("GREENNODE_CLIENT_SECRET"):
        config.update({k: v for k, v in load_greennode_json().items() if v})

    client_id = config.get("GREENNODE_CLIENT_ID") or os.getenv("GREENNODE_CLIENT_ID", "")
    client_secret = config.get("GREENNODE_CLIENT_SECRET") or os.getenv("GREENNODE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError(
            "Cannot find GREENNODE_CLIENT_ID/GREENNODE_CLIENT_SECRET in master-agent/.env, "
            "master-agent/.env.deploy, master-agent/.greennode.json, ../vngdc-vul-hardening-all/.env, "
            "or environment."
        )

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    form_data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        IAM_TOKEN_URL,
        data=form_data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, context=ssl.create_default_context()) as resp:
        body = json.loads(resp.read())
    token = body.get("access_token", "")
    if not token:
        raise RuntimeError(f"access_token not found in IAM response: {body}")
    return token


def api(method: str, url: str, body: dict[str, Any] | None = None, token: str = "") -> tuple[int, dict[str, Any]]:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, context=ssl.create_default_context()) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read() or b"{}")
        except json.JSONDecodeError:
            payload = {"error": exc.reason}
        return exc.code, payload


def get_cr_credentials(token: str) -> tuple[str, str]:
    status, resp = api("GET", CR_CREDENTIAL_URL, token=token)
    if status != 200:
        raise RuntimeError(f"Failed to get CR credentials (HTTP {status}): {resp}")
    username = str(resp.get("username") or "")
    secret = str(resp.get("secret") or "")
    if not username or not secret:
        raise RuntimeError(f"CR credentials missing in response: {resp}")
    return username, secret


def docker_build_push(token: str, no_cache: bool = False) -> tuple[str, str]:
    image = deploy_value("MASTER_IMAGE", DEFAULT_IMAGE)

    print("\n=== Step 1: Fetch fresh Container Registry credentials ===")
    cr_user, cr_secret = get_cr_credentials(token)
    print(f"CR user: {cr_user}")

    print("\n=== Step 2: Docker login ===")
    login = subprocess.run(
        ["docker", "login", "vcr.vngcloud.vn", "--username", cr_user, "--password-stdin"],
        capture_output=True,
        input=cr_secret,
        text=True,
        cwd=HERE,
    )
    print(login.stdout.strip() or login.stderr.strip())
    if login.returncode != 0:
        raise RuntimeError(f"Docker login failed: {login.stderr}")

    print("\n=== Step 3: Build all-in-one master runtime image ===")
    build_cmd = ["docker", "build", "--platform", "linux/amd64"]
    if no_cache:
        build_cmd.append("--no-cache")
    build_cmd.extend(["-f", "dashboard/Dockerfile", "-t", image, "."])
    run(build_cmd, cwd=HERE)

    print("\n=== Step 4: Push image ===")
    run(["docker", "push", image], cwd=HERE)
    return cr_user, cr_secret


def build_runtime_env() -> dict[str, str]:
    env = dict(DEFAULT_RUNTIME_ENV)
    local_config = load_local_config()
    for key in LLM_ENV_KEYS:
        value = os.getenv(key) or local_config.get(key)
        if value:
            env[key] = value
    env.update(read_env_file(HERE / ".env.deploy"))
    for key in DEPLOYMENT_ONLY_ENV_KEYS:
        env.pop(key, None)
    return env


def build_body(cr_user: str, cr_secret: str) -> dict[str, Any]:
    return {
        "name": deploy_value("MASTER_RUNTIME_NAME", DEFAULT_RUNTIME_NAME),
        "description": "VNGDC Master Agent: unified multi-agent dashboard and orchestrator for Monitoring, Logging, and Security agents",
        "imageUrl": deploy_value("MASTER_IMAGE", DEFAULT_IMAGE),
        "flavorId": deploy_value("MASTER_FLAVOR_ID", DEFAULT_FLAVOR_ID),
        "command": [],
        "args": [],
        "environmentVariables": build_runtime_env(),
        "autoscaling": {
            "minReplicas": 1,
            "maxReplicas": 1,
            "cpuUtilization": 50,
            "memoryUtilization": 50,
        },
        "imageAuth": {"enabled": True, "username": cr_user, "password": cr_secret},
    }


def require_runtime_id() -> str:
    runtime_id = deploy_value("MASTER_RUNTIME_ID")
    if not runtime_id:
        raise RuntimeError("MASTER_RUNTIME_ID is empty. Set it after create before update/status/delete.")
    return runtime_id


def print_json(status: int, payload: dict[str, Any]) -> None:
    print(f"HTTP {status}")
    print(json.dumps(_redact_sensitive(payload), indent=2, ensure_ascii=False))


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        env_key = str(value.get("key") or value.get("name") or "").upper()
        if env_key and any(marker in env_key for marker in ("SECRET", "PASSWORD", "TOKEN", "API_KEY")):
            return {
                key: ("***REDACTED***" if str(key).lower() in {"value", "secret", "password"} else _redact_sensitive(item))
                for key, item in value.items()
            }

        redacted = {}
        for key, item in value.items():
            upper_key = str(key).upper()
            if any(marker in upper_key for marker in ("SECRET", "PASSWORD", "TOKEN", "API_KEY")):
                redacted[key] = "***REDACTED***"
            else:
                redacted[key] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def main() -> None:
    action = sys.argv[1] if len(sys.argv) > 1 else "create"
    no_cache = "--no-cache" in sys.argv[2:]

    token = get_token()
    print("IAM token OK")

    if action == "build":
        docker_build_push(token, no_cache=no_cache)
        return

    if action == "create":
        cr_user, cr_secret = docker_build_push(token, no_cache=no_cache)
        cr_user, cr_secret = get_cr_credentials(token)
        print("\n=== Step 5: Create AgentBase runtime ===")
        status, resp = api("POST", BASE_URL, build_body(cr_user, cr_secret), token)
        print_json(status, resp)
        if status == 200:
            runtime_id = resp.get("id", "")
            print(f"\nRuntime ID: {runtime_id}")
            print(f'Set MASTER_RUNTIME_ID="{runtime_id}" in .env.deploy before running update/status.')
        return

    if action == "update":
        runtime_id = require_runtime_id()
        cr_user, cr_secret = docker_build_push(token, no_cache=no_cache)
        cr_user, cr_secret = get_cr_credentials(token)
        print("\n=== Update AgentBase runtime ===")
        body = build_body(cr_user, cr_secret)
        body.pop("name", None)
        status, resp = api("PATCH", f"{BASE_URL}/{runtime_id}", body, token)
        print_json(status, resp)
        return

    if action == "status":
        runtime_id = require_runtime_id()
        status, resp = api("GET", f"{BASE_URL}/{runtime_id}", token=token)
        print_json(status, resp)
        status_ep, ep = api("GET", f"{BASE_URL}/{runtime_id}/endpoints", token=token)
        print("\n=== Endpoints ===")
        print_json(status_ep, ep)
        for endpoint in ep.get("listData", []):
            print(f"Endpoint: {endpoint.get('url')} [{endpoint.get('status')}]")
        return

    if action == "delete":
        runtime_id = require_runtime_id()
        status, resp = api("DELETE", f"{BASE_URL}/{runtime_id}", token=token)
        print_json(status, resp)
        return

    print("Unknown action. Use: create | update | status | build | delete")
    sys.exit(1)


if __name__ == "__main__":
    main()
