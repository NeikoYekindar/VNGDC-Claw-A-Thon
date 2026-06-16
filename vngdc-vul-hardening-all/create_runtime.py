"""
Create or update the vngdc-vul-hardening runtime on GreenNode AgentBase.

Usage:
    python create_runtime.py           # Create new runtime
    python create_runtime.py update    # Update existing runtime (need RUNTIME_ID below)
"""

import json, os, subprocess, sys, urllib.request, ssl

RUNTIME_ID  = "runtime-e7a45d47-3948-43f4-bfeb-5f39db5f3463"
IMAGE_URL   = "vcr.vngcloud.vn/111480-abp111815/vngdc-vul-hardening:latest"
FLAVOR_ID   = "runtime-s2-general-2x4"
CR_USER     = "111480-gui111815"
CR_SECRET   = "ajl8gaabXZPyeLxjP8ZlMvIukogdz8jW"
ENV_FILE    = ".env.deploy"
BASE_URL    = "https://agentbase.api.vngcloud.vn/runtime/agent-runtimes"

HERE = os.path.dirname(os.path.abspath(__file__))


def get_token() -> str:
    """Fetch IAM token — Basic Auth + form data, no bash/jq needed."""
    import base64, urllib.parse
    env = read_env(".env")
    client_id     = env.get("GREENNODE_CLIENT_ID", "")
    client_secret = env.get("GREENNODE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        try:
            with open(os.path.join(HERE, ".greennode.json"), encoding="utf-8") as f:
                creds = json.load(f)
            client_id     = creds.get("client_id", "")
            client_secret = creds.get("client_secret", "")
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    if not client_id or not client_secret:
        raise RuntimeError("Cannot find credentials in .env or .greennode.json")

    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    form_data   = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    req = urllib.request.Request(
        "https://iam.api.vngcloud.vn/accounts-api/v2/auth/token",
        data=form_data,
        headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx) as r:
        body = json.loads(r.read())
    token = body.get("access_token", "")
    if not token:
        raise RuntimeError(f"access_token not in IAM response: {body}")
    return token


def read_env(path=ENV_FILE):
    env = {}
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
    return env


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
    """Fetch fresh CR credentials — avoids using hardcoded secret that may expire."""
    status, resp = api("GET", "https://agentbase.api.vngcloud.vn/cr/api/v1/registry-credential", token=token)
    if status != 200:
        raise RuntimeError(f"CR credentials fetch failed (HTTP {status}): {resp}")
    return resp["username"], resp["secret"]


def build_body(env, cr_user: str, cr_secret: str):
    return {
        "name": "vngdc-vul-hardening",
        "description": "Security hardening & vulnerability analysis agent",
        "imageUrl": IMAGE_URL,
        "flavorId": FLAVOR_ID,
        "command": [],
        "args": [],
        "environmentVariables": env,
        "autoscaling": {
            "minReplicas": 1,
            "maxReplicas": 1,
            "cpuUtilization": 50,
            "memoryUtilization": 50,
        },
        "imageAuth": {"enabled": True, "username": cr_user, "password": cr_secret},
    }


def docker_build_push(cr_user: str, cr_secret: str):
    print("\n=== Docker login ===")
    login = subprocess.run(
        ["docker", "login", "vcr.vngcloud.vn", "--username", cr_user, "--password", cr_secret],
        capture_output=True, text=True, cwd=HERE,
    )
    print(login.stdout.strip() or login.stderr.strip())
    if login.returncode != 0:
        raise RuntimeError(f"Docker login failed: {login.stderr}")

    print("\n=== Build image ===")
    subprocess.run(
        ["docker", "build", "--platform", "linux/amd64", "-t", IMAGE_URL, "."],
        check=True, cwd=HERE,
    )
    print("\n=== Push image ===")
    subprocess.run(["docker", "push", IMAGE_URL], check=True, cwd=HERE)


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "create"
    token  = get_token()
    env    = read_env()
    cr_user, cr_secret = get_cr_credentials(token)

    print(f"✓ Token OK | CR user: {cr_user}")
    print(f"ENV keys loaded: {list(env.keys())}")

    if action == "create":
        docker_build_push(cr_user, cr_secret)
        cr_user, cr_secret = get_cr_credentials(token)  # refresh after long build
        status, resp = api("POST", BASE_URL, build_body(env, cr_user, cr_secret), token)
        print(f"HTTP {status}")
        print(json.dumps(resp, indent=2, ensure_ascii=False))
        if status == 200:
            print(f"\nRuntime ID: {resp.get('id')}")
            print("Update RUNTIME_ID in this script after creation.")

    elif action == "update":
        if not RUNTIME_ID:
            print("ERROR: Set RUNTIME_ID at top of script first.")
            sys.exit(1)
        docker_build_push(cr_user, cr_secret)
        cr_user, cr_secret = get_cr_credentials(token)  # refresh after long build
        body = build_body(env, cr_user, cr_secret)
        body.pop("name", None)
        status, resp = api("PATCH", f"{BASE_URL}/{RUNTIME_ID}", body, token)
        print(f"HTTP {status}")
        print(json.dumps(resp, indent=2, ensure_ascii=False))

    elif action == "status":
        status, resp = api("GET", f"{BASE_URL}/{RUNTIME_ID}", None, token)
        print(f"Status: {resp.get('status')} | ID: {resp.get('id')}")
        # Get endpoint
        status2, ep = api("GET", f"{BASE_URL}/{RUNTIME_ID}/endpoints", None, token)
        for e in ep.get("listData", []):
            print(f"Endpoint: {e.get('url')} [{e.get('status')}]")

    else:
        print(f"Unknown action: {action}. Use: create | update | status")
        sys.exit(1)


if __name__ == "__main__":
    main()
