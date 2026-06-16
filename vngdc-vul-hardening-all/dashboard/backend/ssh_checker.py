"""Delegate hardening checks to the local or external security agent."""
import json
import os
import time
import urllib.error
import urllib.request
import uuid

from parser import parse_output

AGENT_URL = os.environ.get("AGENT_URL", "").rstrip("/")
AGENT_INVOCATIONS_URL = (
    AGENT_URL if AGENT_URL.endswith("/invocations") else f"{AGENT_URL}/invocations"
) if AGENT_URL else ""
LOCAL_AGENT_ENABLED = os.environ.get("LOCAL_AGENT_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
AGENT_TIMEOUT_SECONDS = int(os.environ.get("HARDENING_AGENT_TIMEOUT_SECONDS", "360"))


def run_check(host: str, port: int, username: str,
              password: str | None, ssh_key: str | None, os_type: str) -> dict:
    payload: dict = {
        "action": "hardening_check",
        "host": host,
        "port": port,
        "username": username,
        "os_type": os_type,
    }
    if password:
        payload["password"] = password
    if ssh_key:
        payload["ssh_key"] = ssh_key

    start = time.time()

    if not AGENT_INVOCATIONS_URL:
        if not LOCAL_AGENT_ENABLED:
            raise RuntimeError("Agent runtime is disabled. Set LOCAL_AGENT_ENABLED=true or AGENT_URL.")
        from agent_runtime import invoke_agent

        data = invoke_agent(
            payload,
            user_id="dashboard",
            session_id=f"dashboard-{uuid.uuid4().hex[:12]}",
        )
        if data.get("status") == "error":
            raise RuntimeError(data.get("error") or data.get("response") or "Agent returned error")
        result = data.get("result", {})
        raw_output = result.get("raw_output", "")
        duration = result.get("duration_seconds", int(time.time() - start))
        parsed = parse_output(raw_output)
        return {
            "status": parsed["status"],
            "sections": parsed["sections"],
            "raw_output": raw_output,
            "duration_seconds": duration,
            "analysis": result.get("analysis"),
        }

    req = urllib.request.Request(
        AGENT_INVOCATIONS_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "X-GreenNode-AgentBase-User-Id": "dashboard",
            "X-GreenNode-AgentBase-Session-Id": f"dashboard-{uuid.uuid4().hex[:12]}",
        },
        method="POST",
    )

    import ssl
    ctx = ssl.create_default_context()
    # Retry up to 3 times — agent may be cold-starting from 0 replicas
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=AGENT_TIMEOUT_SECONDS) as r:
                data = json.loads(r.read())
            last_err = None
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode('utf-8', errors='replace')
            if e.code in (404, 503, 502) and attempt < 2:
                time.sleep(15)   # wait for cold-start
                continue
            raise RuntimeError(f"Agent HTTP {e.code}: {body}")
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(10)
                continue
            raise
    if last_err:
        raise last_err

    if data.get("status") == "error":
        raise RuntimeError(data.get("error", "Agent returned error"))

    result = data.get("result", {})
    raw_output = result.get("raw_output", "")
    duration = result.get("duration_seconds", int(time.time() - start))

    parsed = parse_output(raw_output)
    return {
        "status": parsed["status"],
        "sections": parsed["sections"],
        "raw_output": raw_output,
        "duration_seconds": duration,
        "analysis": result.get("analysis"),
    }
