from __future__ import annotations

import asyncio
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent_runtime import build_child_message, extract_agent_directive, load_master_prompt, route_agents, synthesize_master_response


DEFAULT_MONITORING_URL = (
    "https://endpoint-dbd6717d-569f-413e-b9da-b63ceda13b22."
    "agentbase-runtime.aiplatform.vngcloud.vn"
)
DEFAULT_LOGGING_URL = (
    "https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9."
    "agentbase-runtime.aiplatform.vngcloud.vn"
)
DEFAULT_SECURITY_URL = (
    "https://endpoint-c73f7b5b-2611-4304-90bc-c503feb4af38."
    "agentbase-runtime.aiplatform.vngcloud.vn"
)

REQUEST_TIMEOUT_SECONDS = float(os.getenv("MASTER_CHILD_TIMEOUT_SECONDS", "90"))
STATUS_TIMEOUT_SECONDS = float(os.getenv("MASTER_STATUS_TIMEOUT_SECONDS", "8"))


class ChildAgent(BaseModel):
    key: Literal["monitoring", "logging", "security"]
    name: str
    section: str
    description: str
    base_url: str
    health_path: str = "/health"
    status_path: str | None = None

    @property
    def invocations_url(self) -> str:
        return _url_join(self.base_url, "/invocations")


AGENTS: dict[str, ChildAgent] = {
    "monitoring": ChildAgent(
        key="monitoring",
        name="ai-agent-monitoring",
        section="Monitoring",
        description="Metrics, alerts, server inventory, SSH investigation, RCA batches.",
        base_url=os.getenv("MONITORING_AGENT_URL", DEFAULT_MONITORING_URL).rstrip("/"),
        status_path=None,
    ),
    "logging": ChildAgent(
        key="logging",
        name="infra-log-sentinel-agent",
        section="Logging",
        description="Infrastructure logs, runtime controls, incident RCA, reports.",
        base_url=os.getenv("LOGGING_AGENT_URL", DEFAULT_LOGGING_URL).rstrip("/"),
        status_path="/status",
    ),
    "security": ChildAgent(
        key="security",
        name="vngdc-vul-hardening",
        section="Security",
        description="Hardening checks, Wazuh vulnerability posture, CVE analysis.",
        base_url=os.getenv("SECURITY_AGENT_URL", DEFAULT_SECURITY_URL).rstrip("/"),
        status_path="/api/agent/status",
    ),
}

SECURITY_ALLOWED_PREFIXES = (
    "stats",
    "servers",
    "tasks",
    "reports",
    "vulnerabilities",
    "agent/status",
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = "master-session"
    target_agents: list[str] | None = None


class ChatSessionCreateRequest(BaseModel):
    title: str | None = None


class ChatSessionSummary(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class StoredChatMessage(BaseModel):
    id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: str


class AgentStatus(BaseModel):
    key: str
    name: str
    section: str
    connected: bool
    active: bool
    url: str
    latency_ms: int | None = None
    status: str = "unknown"
    detail: str = ""
    checked_at: str


class ChildResult(BaseModel):
    key: str
    name: str
    section: str
    ok: bool
    answer: str
    raw: Any = None
    error: str | None = None
    latency_ms: int | None = None


class MasterChatResponse(BaseModel):
    status: str
    response: str
    routed_agents: list[str]
    child_results: list[ChildResult]
    timestamp: str


CHAT_HISTORY: dict[str, list[StoredChatMessage]] = defaultdict(list)
CHAT_SESSIONS: dict[str, ChatSessionSummary] = {}

app = FastAPI(title="VNGDC Master Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
@app.get("/ping")
@app.post("/ping")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "service": "vngdc-master-agent",
        "timestamp": _now_iso(),
        "agents": list(AGENTS),
    }


@app.get("/api/agents/status", response_model=list[AgentStatus])
async def agents_status() -> list[AgentStatus]:
    return await _check_all_agents()


@app.get("/api/master/prompt")
async def master_prompt() -> dict[str, Any]:
    return {
        "prompt": load_master_prompt(),
        "source": os.getenv("MASTER_AGENT_PROMPT_PATH", "prompts/master_system_prompt.md"),
    }


@app.get("/api/overview")
async def overview() -> dict[str, Any]:
    statuses = await _check_all_agents()
    monitoring, logging, security = await asyncio.gather(
        _safe_monitoring_snapshot(),
        _safe_logging_snapshot(),
        _safe_security_snapshot(),
    )
    return {
        "generated_at": _now_iso(),
        "agents": [status.model_dump() for status in statuses],
        "monitoring": monitoring,
        "logging": logging,
        "security": security,
    }


@app.get("/api/master/chat/{session_id}/messages", response_model=list[StoredChatMessage])
async def master_chat_history(session_id: str) -> list[StoredChatMessage]:
    return CHAT_HISTORY.get(session_id, [])[-200:]


@app.get("/api/master/chat/sessions", response_model=list[ChatSessionSummary])
async def master_chat_sessions() -> list[ChatSessionSummary]:
    return _list_chat_sessions()


@app.post("/api/master/chat/sessions", response_model=ChatSessionSummary)
async def master_chat_create_session(body: ChatSessionCreateRequest | None = None) -> ChatSessionSummary:
    session_id = f"master-{uuid.uuid4().hex[:12]}"
    return _ensure_chat_session(session_id, (body.title if body else None) or "")


@app.post("/api/master/chat", response_model=MasterChatResponse)
async def master_chat(body: ChatRequest) -> MasterChatResponse:
    session_id = body.session_id or f"master-{uuid.uuid4().hex[:12]}"
    _ensure_chat_session(session_id, body.message)
    _rename_empty_chat_session(session_id, body.message)
    user_message = StoredChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=body.message,
        created_at=_now_iso(),
    )
    CHAT_HISTORY[session_id].append(user_message)
    _touch_chat_session(session_id)

    result = await _run_master_agent(
        message=body.message,
        session_id=session_id,
        target_agents=body.target_agents,
    )
    assistant_message = StoredChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="assistant",
        content=result.response,
        created_at=result.timestamp,
    )
    CHAT_HISTORY[session_id].append(assistant_message)
    _touch_chat_session(session_id, result.timestamp)
    return result


@app.post("/invocations")
async def invocations(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"message": str(payload)}

    message = _extract_message(payload)
    if not message:
        return {
            "status": "error",
            "error": "Message is required. Provide message, question, input, prompt, or messages.",
            "timestamp": _now_iso(),
        }

    session_id = (
        request.headers.get("X-GreenNode-AgentBase-Session-Id")
        or payload.get("session_id")
        or payload.get("sessionId")
        or f"agentbase-{uuid.uuid4().hex[:12]}"
    )
    target_agents = payload.get("target_agents")
    if target_agents is not None and not isinstance(target_agents, list):
        target_agents = None

    _ensure_chat_session(str(session_id), message)
    _rename_empty_chat_session(str(session_id), message)
    CHAT_HISTORY[str(session_id)].append(
        StoredChatMessage(
            id=str(uuid.uuid4()),
            session_id=str(session_id),
            role="user",
            content=message,
            created_at=_now_iso(),
        )
    )
    _touch_chat_session(str(session_id))

    result = await _run_master_agent(
        message=message,
        session_id=str(session_id),
        target_agents=target_agents,
    )
    CHAT_HISTORY[str(session_id)].append(
        StoredChatMessage(
            id=str(uuid.uuid4()),
            session_id=str(session_id),
            role="assistant",
            content=result.response,
            created_at=result.timestamp,
        )
    )
    _touch_chat_session(str(session_id), result.timestamp)
    return {
        "status": result.status,
        "response": result.response,
        "text": result.response,
        "reply": result.response,
        "routed_agents": result.routed_agents,
        "child_results": [child.model_dump() for child in result.child_results],
        "timestamp": result.timestamp,
    }


@app.post("/api/child/{agent_key}/invoke")
async def child_invoke(agent_key: str, request: Request) -> dict[str, Any]:
    agent = _agent_or_404(agent_key)
    payload = await _optional_json(request)
    return await _call_child_invocation(agent, payload, session_id=f"proxy-{uuid.uuid4().hex[:10]}")


@app.get("/api/monitoring/inventory")
async def monitoring_inventory(type: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"action": "list_inventory"}
    if type:
        payload["type"] = type
    return await _call_child_invocation(AGENTS["monitoring"], payload)


@app.post("/api/monitoring/inventory/upload")
async def monitoring_upload_inventory(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    csv_content = str(payload.get("csv_content") or "").strip()
    if not csv_content:
        raise HTTPException(400, "csv_content is required")
    return await _call_child_invocation(
        AGENTS["monitoring"],
        {"action": "upload_inventory", "csv_content": csv_content},
    )


@app.get("/api/monitoring/batches")
async def monitoring_batches() -> dict[str, Any]:
    return await _call_child_invocation(AGENTS["monitoring"], {"action": "list_batches"})


@app.post("/api/monitoring/alert")
async def monitoring_receive_alert(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    alert = payload.get("alert") if isinstance(payload.get("alert"), dict) else payload
    if not isinstance(alert, dict) or not alert:
        raise HTTPException(400, "alert payload is required")
    return await _call_child_invocation(AGENTS["monitoring"], {"action": "receive_alert", "alert": alert})


@app.get("/api/monitoring/suppressions")
async def monitoring_suppressions() -> dict[str, Any]:
    return await _call_child_invocation(AGENTS["monitoring"], {"action": "list_suppressions"})


@app.post("/api/monitoring/suppressions")
async def monitoring_create_suppression(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    instance = str(payload.get("instance") or "").strip()
    if not instance:
        raise HTTPException(400, "instance is required")
    hours = payload.get("hours", 2)
    reason = str(payload.get("reason") or "Maintenance").strip() or "Maintenance"
    return await _call_child_invocation(
        AGENTS["monitoring"],
        {"action": "suppress_server", "instance": instance, "hours": hours, "reason": reason},
    )


@app.post("/api/monitoring/suppressions/remove")
async def monitoring_remove_suppression(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    instance = str(payload.get("instance") or "").strip()
    if not instance:
        raise HTTPException(400, "instance is required")
    return await _call_child_invocation(
        AGENTS["monitoring"],
        {"action": "remove_suppression", "instance": instance},
    )


@app.get("/api/monitoring/knowledge")
async def monitoring_knowledge() -> dict[str, Any]:
    return await _call_child_invocation(AGENTS["monitoring"], {"action": "list_knowledge"})


@app.post("/api/monitoring/knowledge/read")
async def monitoring_read_knowledge(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    filename = str(payload.get("filename") or "").strip()
    if not filename:
        raise HTTPException(400, "filename is required")
    return await _call_child_invocation(
        AGENTS["monitoring"],
        {"action": "read_knowledge", "filename": filename},
    )


@app.post("/api/monitoring/knowledge/upload")
async def monitoring_upload_knowledge(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    filename = str(payload.get("filename") or "").strip()
    content = str(payload.get("content") or "")
    if not filename or not content.strip():
        raise HTTPException(400, "filename and content are required")
    return await _call_child_invocation(
        AGENTS["monitoring"],
        {"action": "upload_knowledge", "filename": filename, "content": content},
    )


@app.post("/api/monitoring/knowledge/delete")
async def monitoring_delete_knowledge(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    filename = str(payload.get("filename") or "").strip()
    if not filename:
        raise HTTPException(400, "filename is required")
    return await _call_child_invocation(
        AGENTS["monitoring"],
        {"action": "delete_knowledge", "filename": filename},
    )


@app.post("/api/monitoring/simulate")
async def monitoring_simulate() -> dict[str, Any]:
    return await _call_child_invocation(AGENTS["monitoring"], {"action": "simulate_correlated_alerts"})


@app.post("/api/monitoring/trigger-batch")
async def monitoring_trigger_batch(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    batch_id = str(payload.get("batch_id") or "").strip()
    if not batch_id:
        raise HTTPException(400, "batch_id is required")
    return await _call_child_invocation(AGENTS["monitoring"], {"action": "trigger_batch", "batch_id": batch_id})


@app.get("/api/logging/status")
async def logging_status() -> dict[str, Any]:
    return await _request_json("GET", _url_join(AGENTS["logging"].base_url, "/status"), timeout=STATUS_TIMEOUT_SECONDS)


@app.get("/api/logging/incidents/latest")
async def logging_latest_incident() -> dict[str, Any]:
    return await _request_json("GET", _url_join(AGENTS["logging"].base_url, "/incidents/latest"), timeout=STATUS_TIMEOUT_SECONDS)


@app.post("/api/logging/incidents/generate")
async def logging_incident_generate(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    return await _request_json(
        "POST",
        _url_join(AGENTS["logging"].base_url, "/demo/incidents/generate"),
        json_body=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


@app.post("/api/logging/incidents/analyze")
async def logging_incident_analyze(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    return await _request_json(
        "POST",
        _url_join(AGENTS["logging"].base_url, "/incidents/analyze"),
        json_body=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


@app.post("/api/logging/telegram/test")
async def logging_telegram_test(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    return await _request_json(
        "POST",
        _url_join(AGENTS["logging"].base_url, "/telegram/test"),
        json_body=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


@app.post("/api/logging/rca/analyze")
async def logging_rca_analyze(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    return await _request_json(
        "POST",
        _url_join(AGENTS["logging"].base_url, "/rca/logs/analyze"),
        json_body=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


@app.post("/api/logging/rca/generate")
async def logging_rca_generate(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    return await _request_json(
        "POST",
        _url_join(AGENTS["logging"].base_url, "/rca/logs/generate"),
        json_body=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


@app.post("/api/logging/runtime-control")
async def logging_runtime_control(request: Request) -> dict[str, Any]:
    payload = await _optional_json(request)
    return await _request_json(
        "POST",
        _url_join(AGENTS["logging"].base_url, "/runtime-controls"),
        json_body=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


@app.api_route("/api/security/{child_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def security_proxy(child_path: str, request: Request) -> Any:
    normalized = child_path.strip("/")
    if not normalized or not normalized.startswith(SECURITY_ALLOWED_PREFIXES):
        raise HTTPException(404, "Unsupported security proxy path")
    method = request.method.upper()
    payload = None
    if method in {"POST", "PUT", "DELETE"}:
        payload = await _optional_json(request)
    query = request.url.query
    path = f"/api/{normalized}"
    if query:
        path = f"{path}?{query}"
    return await _request_proxy(
        method,
        _url_join(AGENTS["security"].base_url, path),
        json_body=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


async def _run_master_agent(
    message: str,
    session_id: str,
    target_agents: list[str] | None = None,
) -> MasterChatResponse:
    effective_message, command_targets, command = extract_agent_directive(message, AGENTS)
    conversation_context = _conversation_context(session_id)
    routed_agents = route_agents(effective_message, AGENTS, command_targets or target_agents)
    child_results = await asyncio.gather(
        *[_ask_child_agent(AGENTS[key], effective_message, session_id) for key in routed_agents],
    )
    if command and command_targets and len(command_targets) == 1:
        child = child_results[0]
        response = child.answer if child.answer else _compact_json(child.raw)
        return MasterChatResponse(
            status="success" if child.ok else "error",
            response=response,
            routed_agents=routed_agents,
            child_results=list(child_results),
            timestamp=_now_iso(),
        )

    response = await synthesize_master_response(
        effective_message,
        routed_agents,
        list(child_results),
        AGENTS,
        conversation_messages=conversation_context,
    )
    status = "success" if any(result.ok for result in child_results) else "error"
    return MasterChatResponse(
        status=status,
        response=response,
        routed_agents=routed_agents,
        child_results=list(child_results),
        timestamp=_now_iso(),
    )


async def _ask_child_agent(agent: ChildAgent, message: str, session_id: str) -> ChildResult:
    started = time.perf_counter()
    payload = build_child_message(message, agent.key, session_id)
    try:
        raw = await _call_child_invocation(agent, payload, session_id=session_id)
        latency_ms = int((time.perf_counter() - started) * 1000)
        answer = _extract_answer(raw)
        if not answer:
            answer = _compact_json(raw)
        return ChildResult(
            key=agent.key,
            name=agent.name,
            section=agent.section,
            ok=True,
            answer=answer,
            raw=raw,
            latency_ms=latency_ms,
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return ChildResult(
            key=agent.key,
            name=agent.name,
            section=agent.section,
            ok=False,
            answer=f"Không gọi được {agent.section}: {exc}",
            error=str(exc),
            latency_ms=latency_ms,
        )


async def _check_all_agents() -> list[AgentStatus]:
    return await asyncio.gather(*[_check_agent_status(agent) for agent in AGENTS.values()])


async def _check_agent_status(agent: ChildAgent) -> AgentStatus:
    started = time.perf_counter()
    checked_at = _now_iso()
    try:
        data = await _request_json(
            "GET",
            _url_join(agent.base_url, agent.health_path),
            timeout=STATUS_TIMEOUT_SECONDS,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        status_value = str(data.get("status") or data.get("state") or "ok")
        connected = status_value.lower() not in {"error", "failed", "unhealthy", "down"}
        return AgentStatus(
            key=agent.key,
            name=agent.name,
            section=agent.section,
            connected=connected,
            active=connected,
            url=agent.base_url,
            latency_ms=latency_ms,
            status=status_value,
            detail=_extract_answer(data) or _compact_json(data, limit=600),
            checked_at=checked_at,
        )
    except Exception as exc:
        return AgentStatus(
            key=agent.key,
            name=agent.name,
            section=agent.section,
            connected=False,
            active=False,
            url=agent.base_url,
            status="offline",
            detail=str(exc),
            checked_at=checked_at,
        )


async def _safe_monitoring_snapshot() -> dict[str, Any]:
    inventory, batches, suppressions, knowledge = await asyncio.gather(
        _safe_call(lambda: _call_child_invocation(AGENTS["monitoring"], {"action": "list_inventory"})),
        _safe_call(lambda: _call_child_invocation(AGENTS["monitoring"], {"action": "list_batches"})),
        _safe_call(lambda: _call_child_invocation(AGENTS["monitoring"], {"action": "list_suppressions"})),
        _safe_call(lambda: _call_child_invocation(AGENTS["monitoring"], {"action": "list_knowledge"})),
    )
    return {
        "inventory_count": _list_count(inventory, "inventory"),
        "batch_count": _list_count(batches, "batches"),
        "suppression_count": _list_count(suppressions, "suppressions"),
        "knowledge_count": _list_count(knowledge, "files"),
        "inventory": inventory,
        "batches": batches,
        "suppressions": suppressions,
        "knowledge": knowledge,
    }


async def _safe_logging_snapshot() -> dict[str, Any]:
    return await _safe_call(lambda: _request_json("GET", _url_join(AGENTS["logging"].base_url, "/status"), timeout=STATUS_TIMEOUT_SECONDS))


async def _safe_security_snapshot() -> dict[str, Any]:
    stats, vuln = await asyncio.gather(
        _safe_call(lambda: _request_json("GET", _url_join(AGENTS["security"].base_url, "/api/stats"), timeout=STATUS_TIMEOUT_SECONDS)),
        _safe_call(lambda: _request_json("GET", _url_join(AGENTS["security"].base_url, "/api/vulnerabilities/summary"), timeout=STATUS_TIMEOUT_SECONDS)),
    )
    return {"stats": stats, "vulnerabilities": vuln}


async def _safe_call(fn):
    try:
        return await fn()
    except Exception as exc:
        return {"error": str(exc)}


async def _call_child_invocation(
    agent: ChildAgent,
    payload: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    headers = {
        "X-GreenNode-AgentBase-User-Id": "vngdc-master-agent",
        "X-GreenNode-AgentBase-Session-Id": session_id or f"master-{uuid.uuid4().hex[:12]}",
    }
    return await _request_json(
        "POST",
        agent.invocations_url,
        json_body=payload,
        headers=headers,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


async def _request_json(
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.request(method, url, json=json_body, headers=headers)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"{url} request failed: {exc}") from exc

    raw_text = response.text
    try:
        data = response.json()
    except ValueError:
        data = {"raw": raw_text[:8000]}

    if response.status_code >= 400:
        detail = _extract_answer(data) or raw_text[:800]
        raise RuntimeError(f"HTTP {response.status_code} from {url}: {detail}")
    if isinstance(data, dict):
        return data
    return {"value": data}


async def _request_proxy(
    method: str,
    url: str,
    *,
    json_body: dict[str, Any] | None = None,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> Any:
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.request(method, url, json=json_body)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"{url} request failed: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    raw_text = response.text if "application/json" in content_type or response.status_code >= 400 else ""
    try:
        data = response.json()
    except ValueError:
        data = None

    if response.status_code >= 400:
        detail = _extract_answer(data) if isinstance(data, dict) else raw_text[:800]
        raise RuntimeError(f"HTTP {response.status_code} from {url}: {detail}")

    if response.status_code == 204:
        return Response(status_code=204)
    if data is not None:
        return data

    headers = {}
    content_disposition = response.headers.get("content-disposition")
    if content_disposition:
        headers["content-disposition"] = content_disposition
    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=content_type or "application/octet-stream",
        headers=headers,
    )


async def _optional_json(request: Request) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {"value": payload}


def _agent_or_404(agent_key: str) -> ChildAgent:
    agent = AGENTS.get(agent_key)
    if not agent:
        raise HTTPException(404, f"Unknown agent: {agent_key}")
    return agent


def _extract_message(payload: dict[str, Any]) -> str:
    for key in ("message", "question", "input", "prompt", "content", "text"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return _plain_text(value)
    messages = payload.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict):
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    return _plain_text(content)
    body = payload.get("body")
    if isinstance(body, dict):
        for key in ("plainTextContent", "content"):
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return _plain_text(value)
    return ""


def _extract_answer(data: Any) -> str:
    if isinstance(data, str):
        return data.strip()
    if not isinstance(data, dict):
        return ""

    for key in ("response", "answer", "summary", "message", "text", "reply", "analysis", "error"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    result = data.get("result")
    if isinstance(result, dict):
        for key in ("response", "answer", "summary", "message", "analysis", "raw_output"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _plain_text(value: str) -> str:
    text = value.strip()
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"^\s*@[\w ._-]+\s+", "", text)
    return text.strip()


def _compact_json(value: Any, limit: int = 2000) -> str:
    import json

    try:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    except TypeError:
        text = str(value)
    return text[:limit] + ("..." if len(text) > limit else "")


def _list_count(value: Any, key: str) -> int:
    if isinstance(value, dict) and isinstance(value.get(key), list):
        return len(value[key])
    if isinstance(value, dict) and isinstance(value.get("count"), int):
        return int(value["count"])
    return 0


def _ensure_chat_session(session_id: str, title_source: str = "") -> ChatSessionSummary:
    session = CHAT_SESSIONS.get(session_id)
    if session:
        return session

    now = _now_iso()
    session = ChatSessionSummary(
        session_id=session_id,
        title=_chat_title(title_source) or "New conversation",
        created_at=now,
        updated_at=now,
        message_count=len(CHAT_HISTORY.get(session_id, [])),
    )
    CHAT_SESSIONS[session_id] = session
    return session


def _touch_chat_session(session_id: str, updated_at: str | None = None) -> None:
    session = _ensure_chat_session(session_id)
    session.updated_at = updated_at or _now_iso()
    session.message_count = len(CHAT_HISTORY.get(session_id, []))


def _list_chat_sessions() -> list[ChatSessionSummary]:
    for session_id, messages in list(CHAT_HISTORY.items()):
        _ensure_chat_session(session_id)
        session = CHAT_SESSIONS[session_id]
        session.message_count = len(messages)
        if messages:
            session.updated_at = messages[-1].created_at
    return sorted(CHAT_SESSIONS.values(), key=lambda item: item.updated_at, reverse=True)


def _conversation_context(session_id: str, limit: int = 12) -> list[dict[str, str]]:
    return [
        {
            "role": message.role,
            "content": message.content,
            "created_at": message.created_at,
        }
        for message in CHAT_HISTORY.get(session_id, [])[-limit:]
    ]


def _chat_title(value: str, limit: int = 56) -> str:
    title = _plain_text(value)
    title = re.sub(r"^/(monitoring|monitor|mon|logging|log|logs|security|sec)\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r"\s+", " ", title).strip()
    if not title:
        return ""
    return title[:limit].rstrip() + ("..." if len(title) > limit else "")


def _rename_empty_chat_session(session_id: str, title_source: str) -> None:
    session = _ensure_chat_session(session_id, title_source)
    if session.message_count == 0 and session.title == "New conversation":
        title = _chat_title(title_source)
        if title:
            session.title = title


def _url_join(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
