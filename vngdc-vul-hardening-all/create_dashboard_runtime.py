"""
Build, push, and deploy the all-in-one VNGDC Security runtime to GreenNode AgentBase.

The image contains:
- Python-hosted dashboard UI
- FastAPI dashboard API
- Local agent/model /invocations endpoint
- Hardening, Wazuh, Telegram, and Teams tooling

Usage:
    python create_dashboard_runtime.py           # Create new runtime
    python create_dashboard_runtime.py update    # Update existing runtime
    python create_dashboard_runtime.py status    # Check status + endpoint
    python create_dashboard_runtime.py build     # Build + push only (no deploy)
"""

import json, os, subprocess, sys, urllib.request, ssl

RUNTIME_ID  = "runtime-c2ba617e-2ec0-4cd0-a33d-56af724b59da"
IMAGE       = "vcr.vngcloud.vn/111480-abp111815/vngdc-vul-hardening-all:latest"
FLAVOR_ID   = "runtime-s2-general-4x8"
CR_USER     = "111480-gui111815"
CR_SECRET   = "ajl8gaabXZPyeLxjP8ZlMvIukogdz8jW"
BASE_URL    = "https://agentbase.api.vngcloud.vn/runtime/agent-runtimes"
SCRIPTS_DIR = "../greennode-agentbase-skills/.claude/skills/agentbase/scripts"

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd, **kwargs):
    print(f"$ {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    result = subprocess.run(cmd, **kwargs, shell=isinstance(cmd, str))
    if result.returncode != 0:
        sys.exit(result.returncode)
    return result


def _read_env(path: str) -> dict:
    env: dict = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, v = line.split("=", 1)
                    v = v.strip()
                    if "#" in v:
                        v = v[: v.index("#")].strip()
                    if k.strip() and v:
                        env[k.strip()] = v
    except FileNotFoundError:
        pass
    return env


def get_token() -> str:
    """Fetch IAM token — Basic Auth + form data (same as get_token.sh, no jq)."""
    env = _read_env(os.path.join(HERE, ".env"))
    client_id     = env.get("GREENNODE_CLIENT_ID", "")
    client_secret = env.get("GREENNODE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        try:
            with open(os.path.join(HERE, ".greennode.json"), encoding="utf-8") as f:
                creds = json.load(f)
            # .greennode.json uses snake_case: client_id, client_secret
            client_id     = creds.get("client_id", "")
            client_secret = creds.get("client_secret", "")
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    if not client_id or not client_secret:
        raise RuntimeError("Cannot find credentials in .env or .greennode.json")

    import base64, urllib.parse
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    form_data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()

    req = urllib.request.Request(
        "https://iam.api.vngcloud.vn/accounts-api/v2/auth/token",
        data=form_data,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx) as r:
        body = json.loads(r.read())

    token = body.get("access_token", "")
    if not token:
        raise RuntimeError(f"access_token not found in IAM response: {body}")
    return token


def api(method, url, body=None, token=""):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method=method,
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def get_cr_credentials(token: str) -> tuple[str, str]:
    """Fetch fresh CR credentials from AgentBase API."""
    status, resp = api("GET", "https://agentbase.api.vngcloud.vn/cr/api/v1/registry-credential", token=token)
    if status != 200:
        raise RuntimeError(f"Failed to get CR credentials (HTTP {status}): {resp}")
    username = resp.get("username", "")
    secret   = resp.get("secret", "")
    if not username or not secret:
        raise RuntimeError(f"CR credentials missing in response: {resp}")
    return username, secret


def docker_build_push(token: str, no_cache: bool = False):
    # Must be run from vngdc-vul-hardening-all/ (build context includes dashboard, src, data)
    print("\n=== Step 1: Fetch fresh CR credentials ===")
    cr_user, cr_secret = get_cr_credentials(token)
    print(f"CR user: {cr_user} | secret: {cr_secret[:8]}...")

    print("\n=== Step 2: Docker login ===")
    # Use --password directly (not --password-stdin) — avoids Windows pipe encoding issues
    login = subprocess.run(
        ["docker", "login", "vcr.vngcloud.vn", "--username", cr_user, "--password", cr_secret],
        capture_output=True, text=True, cwd=HERE
    )
    print(login.stdout.strip() or login.stderr.strip())
    if login.returncode != 0:
        raise RuntimeError(f"Docker login failed: {login.stderr}")

    print("\n=== Step 3: Build all-in-one Python image ===")
    build_cmd = ["docker", "build", "--platform", "linux/amd64"]
    if no_cache:
        build_cmd.append("--no-cache")
    build_cmd.extend(["-f", "dashboard/Dockerfile", "-t", IMAGE, "."])
    run(build_cmd, cwd=HERE)

    print("\n=== Step 4: Push image ===")
    run(["docker", "push", IMAGE], cwd=HERE)


def build_body():
    env = _read_env(os.path.join(HERE, ".env.deploy"))
    env.pop("AGENT_URL", None)
    env["LOCAL_AGENT_ENABLED"] = "true"
    env.setdefault("ENABLE_AGENT_DAILY_SCHEDULER", "true")
    return {
        "name": "vngdc-vul-hardening-all",
        "description": "All-in-one security dashboard, agent model runtime, Wazuh analysis, and notification workflow",
        "imageUrl": IMAGE,
        "flavorId": FLAVOR_ID,
        "command": [], "args": [],
        "environmentVariables": env,
        "autoscaling": {"minReplicas": 1, "maxReplicas": 1, "cpuUtilization": 50, "memoryUtilization": 50},
        "imageAuth": {"enabled": True, "username": CR_USER, "password": CR_SECRET},
    }


def build_body_with_cr(cr_user: str, cr_secret: str) -> dict:
    b = build_body()
    b["imageAuth"] = {"enabled": True, "username": cr_user, "password": cr_secret}
    return b


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "create"
    no_cache = "--no-cache" in sys.argv[2:]

    token = get_token()
    print(f"✓ IAM token OK")

    if action == "build":
        docker_build_push(token, no_cache=no_cache)
        return

    if action == "create":
        docker_build_push(token, no_cache=no_cache)
        cr_user, cr_secret = get_cr_credentials(token)
        print("\n=== Step 5: Create runtime ===")
        status, resp = api("POST", BASE_URL, build_body_with_cr(cr_user, cr_secret), token)
        print(f"HTTP {status}")
        print(json.dumps(resp, indent=2, ensure_ascii=False))
        if status == 200:
            rid = resp.get("id", "")
            print(f"\n✓ Runtime ID: {rid}")
            print(f"  → Update RUNTIME_ID in this script: RUNTIME_ID = \"{rid}\"")

    elif action == "update":
        if not RUNTIME_ID:
            print("ERROR: Set RUNTIME_ID at top of script first.")
            sys.exit(1)
        docker_build_push(token, no_cache=no_cache)
        cr_user, cr_secret = get_cr_credentials(token)
        print("\n=== Update runtime ===")
        body = {k: v for k, v in build_body_with_cr(cr_user, cr_secret).items() if k != "name"}
        status, resp = api("PATCH", f"{BASE_URL}/{RUNTIME_ID}", body, token)
        print(f"HTTP {status}")
        print(json.dumps(resp, indent=2, ensure_ascii=False))

    elif action == "delete":
        if not RUNTIME_ID:
            print("ERROR: Set RUNTIME_ID first.")
            sys.exit(1)
        status, resp = api("DELETE", f"{BASE_URL}/{RUNTIME_ID}", token=token)
        print(f"HTTP {status} — runtime deleted")

    elif action == "status":
        if not RUNTIME_ID:
            print("ERROR: Set RUNTIME_ID first.")
            sys.exit(1)
        status, resp = api("GET", f"{BASE_URL}/{RUNTIME_ID}", token=token)
        print(f"Status: {resp.get('status')} | {resp.get('id')}")
        status2, ep = api("GET", f"{BASE_URL}/{RUNTIME_ID}/endpoints", token=token)
        for e in ep.get("listData", []):
            print(f"Endpoint: {e.get('url')} [{e.get('status')}]")
    else:
        print(f"Unknown action: {action}. Use: create | update | status | build")


if __name__ == "__main__":
    main()
