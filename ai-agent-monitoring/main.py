"""
AI Alert RCA Agent — GreenNode AgentBase entrypoint.

Receives alert payloads, batches them in a 5-minute window,
then triggers LangGraph workflow for root cause analysis and
sends structured reports to Telegram.

Entrypoint actions (via payload.action):
  - "receive_alert"      : accept alert, queue to batch (default)
  - "list_batches"       : return current batch states
  - "trigger_batch"      : manually fire a batch by batch_id (testing)
  - "health"             : simple status check
  - "chat"               : manual server investigation (no Telegram, returns result inline)
  - "suppress_server"    : add maintenance window for an instance
  - "list_suppressions"  : list active maintenance windows
  - "remove_suppression" : remove a maintenance window
  - "list_inventory"     : return server/device inventory list
  - "upload_inventory"   : import CSV content to update inventory
"""

import os
import threading
from datetime import datetime

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from greennode_agentbase import GreenNodeAgentBaseApp, PingStatus, RequestContext

load_dotenv()

# ---------------------------------------------------------------------------
# Validate required env vars
# ---------------------------------------------------------------------------

LLM_MODEL = os.environ.get("LLM_MODEL", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")

if not all([LLM_MODEL, LLM_BASE_URL, LLM_API_KEY]):
    raise ValueError(
        "LLM_MODEL, LLM_BASE_URL, and LLM_API_KEY are required. "
        "Set them in .env or use /agentbase-llm to create a GreenNode AIP key."
    )

# ---------------------------------------------------------------------------
# Init LLM, graph, batch manager
# ---------------------------------------------------------------------------

from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware

from batching import BatchManager
from models.alert import Alert
from models.batch import AlertBatch
from workflow.agent_graph import build_graph, run_agent
from executors.ssh_executor import SSHExecutor
from executors.command_policy import CommandPolicy
from chat.chat_handler import ChatHandler
from utils.knowledge_loader import list_knowledge_files, read_knowledge_file, save_knowledge_file, delete_knowledge_file
from utils.auth import (
    ensure_default_admin, login as auth_login, logout as auth_logout,
    validate_token, create_user, delete_user, list_users,
)
from utils.suppression import (
    suppress as suppress_server, remove as remove_suppression,
    is_suppressed, list_suppressions,
)
from utils.auto_learn import confirm_save
from utils.inventory import load_inventory, import_csv as import_inventory_csv

# ── Auth mode ─────────────────────────────────────────────────────────────────
# AUTH_ENABLED = True   # <- bật lại để yêu cầu đăng nhập
AUTH_ENABLED = False    # <- tắt để demo public (không cần login)
# ──────────────────────────────────────────────────────────────────────────────

# Bootstrap default admin on first run
_default_pw = ensure_default_admin()
if _default_pw:
    print(f"[AUTH] Default admin created — username: admin | password: {_default_pw}", flush=True)
    print("[AUTH] Hãy đổi mật khẩu ngay sau khi đăng nhập!", flush=True)


def _auth(payload: dict, require_admin: bool = False) -> dict:
    """Validate token. Returns user dict or raises PermissionError.
    Khi AUTH_ENABLED=False, trả về guest admin — bỏ qua mọi kiểm tra.
    """
    if not AUTH_ENABLED:
        return {"username": "guest", "role": "admin"}
    user = validate_token(payload.get("token", ""))
    if not user:
        raise PermissionError("Chưa đăng nhập hoặc phiên đã hết hạn.")
    if require_admin and user["role"] != "admin":
        raise PermissionError("Chỉ admin mới có quyền thực hiện thao tác này.")
    return user


llm = ChatOpenAI(model=LLM_MODEL, base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
graph = build_graph(llm)

ssh_executor = SSHExecutor()
command_policy = CommandPolicy()
chat_handler = ChatHandler(llm=llm, ssh_executor=ssh_executor, command_policy=command_policy)

# ---------------------------------------------------------------------------
# Batch handler — runs in background thread
# ---------------------------------------------------------------------------

def on_batch_ready(batch: AlertBatch) -> None:
    """Called by BatchManager after 5-minute window closes."""
    def _run():
        report = run_agent(batch, graph)
        batch.status = __import__("models.batch", fromlist=["BatchStatus"]).BatchStatus.DONE
        from utils.logger import log_rca_result
        log_rca_result(batch.batch_id, report.root_cause, str(report.confidence))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


batch_manager = BatchManager(on_batch_ready=on_batch_ready)

# ---------------------------------------------------------------------------
# AgentBase App
# ---------------------------------------------------------------------------

app = GreenNodeAgentBaseApp()

_HTML_FILE = Path(__file__).parent / "chat_ui.html"


class _ServeUIMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "GET" and request.url.path == "/":
            return HTMLResponse(_HTML_FILE.read_text(encoding="utf-8"))
        return await call_next(request)


_SAVE_OK_HTML = """<!DOCTYPE html><html lang="vi">
<head><meta charset="UTF-8"><title>Da luu Knowledge</title></head>
<body style="font-family:-apple-system,sans-serif;background:#0f1117;color:#e2e8f0;
             display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
  <div style="text-align:center;background:#1a1d2e;padding:40px 48px;border-radius:16px;
              border:1px solid #166534;max-width:480px">
    <div style="font-size:52px">OK</div>
    <h2 style="color:#4ade80;margin:16px 0 8px">Da luu thanh cong!</h2>
    <p style="color:#94a3b8">File <code style="color:#86efac">{filename}</code> da duoc them vao Knowledge Base.</p>
    <p style="color:#64748b;font-size:13px;margin-top:8px">
      Agent se su dung kien thuc nay trong lan phan tich tiep theo.
    </p>
    <a href="/" style="display:inline-block;margin-top:24px;background:#6366f1;color:white;
       padding:10px 28px;border-radius:8px;text-decoration:none;font-size:14px">Ve trang chu</a>
  </div>
</body></html>"""

_SAVE_CONFIRM_HTML = """<!DOCTYPE html><html lang="vi">
<head><meta charset="UTF-8"><title>Xac nhan luu Knowledge</title></head>
<body style="font-family:-apple-system,sans-serif;background:#0f1117;color:#e2e8f0;
             display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
  <div style="text-align:center;background:#1a1d2e;padding:40px 48px;border-radius:16px;
              border:1px solid #334155;max-width:520px">
    <div style="font-size:52px">?</div>
    <h2 style="color:#a5b4fc;margin:16px 0 8px">Luu bai hoc nay?</h2>
    <p style="color:#94a3b8;line-height:1.6">
      Bam nut ben duoi de them bai hoc RCA nay vao Knowledge Base.
    </p>
    <form method="POST" action="/save-knowledge?token={token}" style="margin-top:24px">
      <button type="submit" style="background:#16a34a;color:white;border:0;
        padding:11px 28px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer">
        Luu vao Knowledge Base
      </button>
    </form>
    <a href="/" style="display:inline-block;margin-top:14px;color:#94a3b8;
       text-decoration:none;font-size:13px">Bo qua</a>
  </div>
</body></html>"""

_SAVE_ERR_HTML = """<!DOCTYPE html><html lang="vi">
<head><meta charset="UTF-8"><title>Luu that bai</title></head>
<body style="font-family:-apple-system,sans-serif;background:#0f1117;color:#e2e8f0;
             display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
  <div style="text-align:center;background:#1a1d2e;padding:40px 48px;border-radius:16px;
              border:1px solid #7c2d12;max-width:480px">
    <div style="font-size:52px">X</div>
    <h2 style="color:#f87171;margin:16px 0 8px">Khong the luu</h2>
    <p style="color:#94a3b8">{message}</p>
    <a href="/" style="display:inline-block;margin-top:24px;background:#6366f1;color:white;
       padding:10px 28px;border-radius:8px;text-decoration:none;font-size:14px">Ve trang chu</a>
  </div>
</body></html>"""


class _SaveKnowledgeMiddleware(BaseHTTPMiddleware):
    """Handle GET /save-knowledge?token=... — confirm auto-learn entries."""
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/save-knowledge" and request.method in ("GET", "POST"):
            token = request.query_params.get("token", "")
            if request.method == "GET":
                return HTMLResponse(_SAVE_CONFIRM_HTML.replace("{token}", token))
            success, msg = confirm_save(token)
            if success:
                return HTMLResponse(_SAVE_OK_HTML.replace("{filename}", msg))
            return HTMLResponse(_SAVE_ERR_HTML.replace("{message}", msg), status_code=400)
        return await call_next(request)


app.add_middleware(_ServeUIMiddleware)
app.add_middleware(_SaveKnowledgeMiddleware)


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    action = payload.get("action", "receive_alert")

    # ── alertmanager_webhook — no auth (called by Prometheus) ─────────────
    if "alerts" in payload and "action" not in payload:
        action = "alertmanager_webhook"

    if action == "alertmanager_webhook":
        firing = [a for a in payload.get("alerts", []) if a.get("status") == "firing"]
        if not firing:
            return {"status": "ok", "message": "No firing alerts, ignored."}
        queued, suppressed_list = [], []
        for am_alert in firing:
            try:
                alert = Alert.from_alertmanager(am_alert)
                if is_suppressed(alert.instance):
                    suppressed_list.append(alert.instance)
                    print(f"[alertmanager_webhook] Suppressed (maintenance): {alert.instance}", flush=True)
                    continue
                batch_id = batch_manager.receive_alert(alert)
                queued.append({"alert_id": alert.alert_id, "alert_name": alert.alert_name,
                                "instance": alert.instance, "batch_id": batch_id})
            except Exception as exc:
                print(f"[alertmanager_webhook] Failed to queue alert: {exc}", flush=True)
        return {"status": "queued", "queued": queued, "count": len(queued),
                "suppressed": suppressed_list, "timestamp": datetime.utcnow().isoformat()}

    # ── health — no auth ───────────────────────────────────────────────────
    if action == "health":
        return {
            "status": "healthy",
            "active_batches": len([b for b in batch_manager.list_batches()
                                   if b.status in ("pending", "processing")]),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── login — no auth (kept for future re-enable) ────────────────────────
    if action == "login":
        username = payload.get("username", "").strip()
        password = payload.get("password", "")
        result = auth_login(username, password)
        if not result:
            return {"status": "error", "message": "Sai username hoac password."}
        return {"status": "ok", **result}

    # ── logout — no auth needed ────────────────────────────────────────────
    if action == "logout":
        auth_logout(payload.get("token", ""))
        return {"status": "ok"}

    # ── All actions below go through _auth (no-op when AUTH_ENABLED=False) ─
    try:
        user = _auth(payload)
    except PermissionError as exc:
        return {"status": "error", "message": str(exc), "auth_required": True}

    # ── receive_alert ──────────────────────────────────────────────────────
    if action == "receive_alert":
        alert_data = payload.get("alert")
        if not alert_data:
            return {"status": "error", "message": "Missing 'alert' in payload."}
        try:
            alert = Alert.from_raw(alert_data)
        except Exception as exc:
            return {"status": "error", "message": f"Invalid alert payload: {exc}"}

        if is_suppressed(alert.instance):
            return {"status": "suppressed", "message": f"Instance {alert.instance} đang trong maintenance window, alert bị bỏ qua."}

        batch_id = batch_manager.receive_alert(alert)
        batch = batch_manager.get_batch(batch_id)
        return {
            "status": "queued",
            "batch_id": batch_id,
            "alert_id": alert.alert_id,
            "batch_size": len(batch.alerts) if batch else 1,
            "window_closes_at": batch.window_closes_at.isoformat() if batch and batch.window_closes_at else None,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── list_batches ───────────────────────────────────────────────────────
    elif action == "list_batches":
        batches = batch_manager.list_batches()
        return {
            "status": "ok",
            "batches": [
                {
                    "batch_id": b.batch_id,
                    "status": b.status,
                    "alert_count": len(b.alerts),
                    "created_at": b.created_at.isoformat(),
                    "window_closes_at": b.window_closes_at.isoformat() if b.window_closes_at else None,
                }
                for b in batches
            ],
        }

    # ── trigger_batch ──────────────────────────────────────────────────────
    elif action == "trigger_batch":
        batch_id = payload.get("batch_id")
        batch = batch_manager.get_batch(batch_id) if batch_id else None
        if not batch:
            return {"status": "error", "message": f"Batch '{batch_id}' not found."}

        from models.batch import BatchStatus
        if batch.status != BatchStatus.PENDING:
            return {"status": "error", "message": f"Batch is already {batch.status}."}

        batch.status = BatchStatus.PROCESSING
        on_batch_ready(batch)
        return {"status": "triggered", "batch_id": batch_id}

    # ── chat ───────────────────────────────────────────────────────────────
    elif action == "chat":
        message = payload.get("message", "").strip()
        if not message:
            return {"status": "error", "message": "Missing 'message' in payload."}

        default_host = payload.get("host")
        result = chat_handler.handle(message=message, default_host=default_host)
        return {
            "status": "ok",
            "action": "chat",
            "host": result["host"],
            "check_type": result["check_type"],
            "summary": result["summary"],
            "commands_run": result.get("commands_run", []),
            "results": [
                {
                    "command": r["command"],
                    "stdout": r["stdout"][:1000],
                    "exit_code": r["exit_code"],
                }
                for r in result.get("results", [])
            ],
            "error": result.get("error"),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── list_knowledge ─────────────────────────────────────────────────────
    elif action == "list_knowledge":
        return {"status": "ok", "files": list_knowledge_files()}

    elif action == "read_knowledge":
        filename = payload.get("filename", "").strip()
        if not filename:
            return {"status": "error", "message": "Missing 'filename'."}
        content = read_knowledge_file(filename)
        if content is None:
            return {"status": "error", "message": f"File not found: {filename}"}
        return {"status": "ok", "filename": filename, "content": content, "size": len(content.encode("utf-8"))}

    # ── upload_knowledge ───────────────────────────────────────────────────
    elif action == "upload_knowledge":
        try:
            _auth(payload, require_admin=True)
        except PermissionError as exc:
            return {"status": "error", "message": str(exc)}
        filename = payload.get("filename", "").strip()
        content = str(payload.get("content") or "")
        if not filename or not content.strip():
            return {"status": "error", "message": "Missing 'filename' or 'content'."}
        saved = save_knowledge_file(filename, content)
        return {"status": "ok", "message": f"Saved as {saved}", "filename": saved}

    # ── delete_knowledge ───────────────────────────────────────────────────
    elif action == "delete_knowledge":
        try:
            _auth(payload, require_admin=True)
        except PermissionError as exc:
            return {"status": "error", "message": str(exc)}
        filename = payload.get("filename", "").strip()
        if not filename:
            return {"status": "error", "message": "Missing 'filename'."}
        ok = delete_knowledge_file(filename)
        return {"status": "ok" if ok else "error",
                "message": f"Deleted {filename}" if ok else f"File not found: {filename}"}

    # ── User management (kept for future re-enable) ────────────────────────
    elif action == "list_users":
        try:
            _auth(payload, require_admin=True)
        except PermissionError as exc:
            return {"status": "error", "message": str(exc)}
        return {"status": "ok", "users": list_users()}

    elif action == "create_user":
        try:
            _auth(payload, require_admin=True)
        except PermissionError as exc:
            return {"status": "error", "message": str(exc)}
        try:
            result = create_user(
                payload.get("username", "").strip(),
                payload.get("password", ""),
                payload.get("role", "user"),
            )
            return {"status": "ok", **result}
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

    elif action == "delete_user":
        try:
            _auth(payload, require_admin=True)
        except PermissionError as exc:
            return {"status": "error", "message": str(exc)}
        try:
            ok = delete_user(payload.get("username", "").strip())
            return {"status": "ok" if ok else "error",
                    "message": "Da xoa user." if ok else "User khong ton tai."}
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

    # ── Suppression / Maintenance Window ──────────────────────────────────
    elif action == "suppress_server":
        try:
            _auth(payload, require_admin=True)
        except PermissionError as exc:
            return {"status": "error", "message": str(exc)}
        instance = payload.get("instance", "").strip()
        if not instance:
            return {"status": "error", "message": "Missing 'instance'."}
        try:
            hours = float(payload.get("hours", 2))
            reason = payload.get("reason", "Maintenance").strip()
            result = suppress_server(instance, hours, reason)
            return {"status": "ok", **result}
        except ValueError as exc:
            return {"status": "error", "message": str(exc)}

    elif action == "list_suppressions":
        return {"status": "ok", "suppressions": list_suppressions()}

    elif action == "remove_suppression":
        try:
            _auth(payload, require_admin=True)
        except PermissionError as exc:
            return {"status": "error", "message": str(exc)}
        instance = payload.get("instance", "").strip()
        if not instance:
            return {"status": "error", "message": "Missing 'instance'."}
        ok = remove_suppression(instance)
        return {
            "status": "ok" if ok else "error",
            "message": "Da xoa maintenance window cho " + instance + "." if ok else "Khong tim thay suppression.",
        }

    # -- list_inventory --------------------------------------------------------
    elif action == "list_inventory":
        filter_type = payload.get("type")   # optional: "server" | "network"
        items = load_inventory(filter_type=filter_type)
        return {"status": "ok", "inventory": items, "count": len(items)}

    # -- upload_inventory -------------------------------------------------------
    elif action == "upload_inventory":
        try:
            _auth(payload, require_admin=True)
        except PermissionError as exc:
            return {"status": "error", "message": str(exc)}
        csv_content = payload.get("csv_content", "").strip()
        if not csv_content:
            return {"status": "error", "message": "Missing 'csv_content' in payload."}
        count, err = import_inventory_csv(csv_content)
        if err:
            return {"status": "error", "message": err}
        return {"status": "ok", "message": f"Da import {count} thiet bi vao inventory.", "count": count}

    # -- simulate_correlated_alerts --------------------------------------------
    elif action == "simulate_correlated_alerts":
        import random, datetime as _dt
        from utils.inventory import load_inventory as _load_inv
        servers = [r for r in _load_inv() if r.get("type") == "server" and r.get("ip", "").strip()]
        if len(servers) < 2:
            return {"status": "error", "message": "Cần ít nhất 2 server trong inventory để chạy mô phỏng."}

        scenarios = [
            {
                "name": "Traffic Spike - Quá tải tầng web",
                "alerts": [
                    {"alert_name": "HighCPU",            "severity": "critical", "service": "web",      "description": "CPU usage > 90% - phát hiện traffic tăng đột biến"},
                    {"alert_name": "HighRequestLatency",  "severity": "warning",  "service": "web",      "description": "P99 latency > 2000ms - dịch vụ suy giảm"},
                    {"alert_name": "HighMemory",          "severity": "warning",  "service": "web",      "description": "Memory usage > 85% - áp lực bộ nhớ tăng cao"},
                ]
            },
            {
                "name": "Database Overload - CSDL bị quá tải",
                "alerts": [
                    {"alert_name": "HighCPU",        "severity": "critical", "service": "database", "description": "DB server CPU > 95% - query load tăng cao"},
                    {"alert_name": "DiskNearFull",   "severity": "warning",  "service": "database", "description": "DB data volume đã đầy 88% - ghi dữ liệu chậm"},
                    {"alert_name": "HighLatency",    "severity": "critical", "service": "backend",  "description": "API latency tăng mạnh - connection pool DB cạn kiệt"},
                ]
            },
            {
                "name": "Memory Leak - Rò rỉ bộ nhớ",
                "alerts": [
                    {"alert_name": "HighMemory",      "severity": "critical", "service": "app",  "description": "Memory > 95% - sắp xảy ra OOM"},
                    {"alert_name": "HighMemory",      "severity": "warning",  "service": "app",  "description": "Memory tăng đều trong 30 phút"},
                    {"alert_name": "ServiceDegraded", "severity": "warning",  "service": "api",  "description": "API suy giảm do áp lực bộ nhớ"},
                ]
            },
            {
                "name": "Disk Full Cascade - Đầy đĩa lan sang nhiều server",
                "alerts": [
                    {"alert_name": "DiskFull",   "severity": "critical", "service": "web",      "description": "Root volume đầy 99% - ghi dữ liệu thất bại"},
                    {"alert_name": "DiskFull",   "severity": "critical", "service": "backend",  "description": "Log volume đầy 97% - lỗi ứng dụng tăng"},
                    {"alert_name": "ServiceDown","severity": "critical", "service": "web",      "description": "Service crash - không còn dung lượng ghi log"},
                ]
            },
        ]

        scenario = random.choice(scenarios)
        n_alerts = len(scenario["alerts"])
        picked = random.sample(servers, min(n_alerts, len(servers)))
        now = _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        scenario_cluster = "sim-" + scenario["name"].split(" - ", 1)[0].lower().replace(" ", "-")

        generated = []
        batch_ids = []
        for i, tmpl in enumerate(scenario["alerts"]):
            srv = picked[i % len(picked)]
            alert = Alert.from_raw({
                "alert_name": tmpl["alert_name"],
                "instance": srv["ip"].strip(),
                "severity": tmpl["severity"],
                "service": tmpl.get("service", ""),
                "description": tmpl["description"],
                "labels": {
                    "env": "production",
                    "hostname": srv.get("hostname", ""),
                    "scenario": scenario["name"],
                    "cluster": scenario_cluster,
                },
                "timestamp": now,
            })
            if not is_suppressed(alert.instance):
                batch_ids.append(batch_manager.receive_alert(alert))
            generated.append({
                "alert_name": alert.alert_name,
                "instance": alert.instance,
                "hostname": srv.get("hostname", ""),
                "severity": alert.severity,
                "service": alert.service,
                "description": alert.description,
            })

        return {
            "status": "ok",
            "scenario": scenario["name"],
            "alerts_sent": len(generated),
            "batch_ids": sorted(set(batch_ids)),
            "alerts": generated,
        }

    else:
        return {"status": "error", "message": f"Unknown action: {action}"}


@app.ping
def health_check() -> PingStatus:
    return PingStatus.HEALTHY


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
