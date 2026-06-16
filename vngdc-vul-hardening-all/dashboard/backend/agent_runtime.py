import html
import logging
import os
import re
import time
from datetime import datetime
from typing import Annotated, Any, TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.config import get_config
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

try:
    from langgraph.checkpoint.memory import MemorySaver
except Exception:  # pragma: no cover - depends on langgraph version
    MemorySaver = None

logger = logging.getLogger(__name__)

_RUNTIME: dict[str, Any] | None = None
_SCHEDULER_STARTED = False


class State(TypedDict):
    messages: Annotated[list, add_messages]


def _bool_env(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _read_text(path, fallback: str = "") -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return fallback


def _get_actor_id() -> str:
    try:
        config = get_config()
        return config["configurable"].get("actor_id", "default")
    except Exception:
        return "default"


def _runtime() -> dict[str, Any]:
    global _RUNTIME, _SCHEDULER_STARTED
    if _RUNTIME is not None:
        return _RUNTIME

    load_dotenv()

    from src.config import (
        LLM_API_KEY,
        LLM_BASE_URL,
        LLM_MODEL,
        MEMORY_ID,
        MEMORY_STRATEGY_ID,
        PROMPTS_DIR,
    )
    from src.tools.hardening import run_hardening_check
    from src.tools.teams import send_teams_notification
    from src.tools.telegram import send_telegram_notification
    from src.tools.wazuh import list_wazuh_agents, scan_vulnerabilities

    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY is not configured. Set it in .env.deploy or AgentBase runtime variables.")

    system_prompt = _read_text(
        PROMPTS_DIR / "system_prompt.md",
        "Bạn là VNGDC Security Agent. Trả lời ngắn gọn, có cấu trúc, ưu tiên bằng chứng và hành động khắc phục.",
    )
    telegram_template = _read_text(PROMPTS_DIR.parent / "templates" / "telegram_message_template.md")

    llm = ChatOpenAI(model=LLM_MODEL, base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

    memory_client = None
    checkpointer = None
    if MEMORY_ID:
        try:
            from greennode_agentbase.memory import MemoryClient
            from greennode_agentbase.memory.models import MemoryRecordSearchRequest
            from greennode_agent_bridge import AgentBaseMemoryEvents

            memory_client = MemoryClient()
            checkpointer = AgentBaseMemoryEvents(memory_id=MEMORY_ID)
        except Exception as exc:
            logger.warning("AgentBase memory is unavailable, falling back to in-memory checkpoint: %s", exc)
            MemoryRecordSearchRequest = None
    else:
        MemoryRecordSearchRequest = None

    if checkpointer is None and MemorySaver is not None:
        checkpointer = MemorySaver()

    def _build_namespace(actor_id: str) -> str:
        return f"/strategies/{MEMORY_STRATEGY_ID}/actors/{actor_id}"

    @tool
    def remember(fact: str) -> str:
        """Store an important security finding or operational fact."""
        if not memory_client or not MEMORY_ID:
            return "Memory is not configured in this all-in-one runtime."
        namespace = _build_namespace(_get_actor_id())
        memory_client.insert_memory_records_directly(id=MEMORY_ID, namespace=namespace, request=[fact])
        return f"Remembered: {fact}"

    @tool
    def recall(query: str) -> str:
        """Search long-term memory for past security findings or stored facts."""
        if not memory_client or not MEMORY_ID or MemoryRecordSearchRequest is None:
            return "Memory is not configured in this all-in-one runtime."
        namespace = _build_namespace(_get_actor_id())
        results = memory_client.search_memory_records(
            id=MEMORY_ID,
            namespace=namespace,
            request=MemoryRecordSearchRequest(query=query, limit=10),
        )
        if not results:
            return "No relevant memories found."
        return "\n".join(f"- {r.memory} (score: {r.score:.2f})" for r in results)

    tools = [
        run_hardening_check,
        scan_vulnerabilities,
        list_wazuh_agents,
        send_teams_notification,
        send_telegram_notification,
        remember,
        recall,
    ]
    llm_with_tools = llm.bind_tools(tools)

    def chatbot(state: State) -> dict:
        return {"messages": [llm_with_tools.invoke([SystemMessage(content=system_prompt)] + state["messages"])]}

    graph_builder = StateGraph(State)
    graph_builder.add_node("chatbot", chatbot)
    graph_builder.add_node("tools", ToolNode(tools))
    graph_builder.add_edge(START, "chatbot")
    graph_builder.add_conditional_edges("chatbot", tools_condition)
    graph_builder.add_edge("tools", "chatbot")
    graph = graph_builder.compile(checkpointer=checkpointer)

    if _bool_env("ENABLE_AGENT_DAILY_SCHEDULER", True) and not _SCHEDULER_STARTED:
        try:
            from src.scheduler import start_scheduler

            start_scheduler()
            _SCHEDULER_STARTED = True
        except Exception as exc:
            logger.warning("Daily agent scheduler was not started: %s", exc)

    _RUNTIME = {
        "llm": llm,
        "graph": graph,
        "telegram_template": telegram_template,
    }
    return _RUNTIME


def _handle_hardening_check(payload: dict[str, Any]) -> dict[str, Any]:
    from src.tools.hardening import _run_hardening_with_creds

    runtime = _runtime()
    llm = runtime["llm"]

    host = str(payload.get("host") or "").strip()
    port = int(payload.get("port") or 22)
    username = str(payload.get("username") or "").strip()
    password = payload.get("password") or None
    ssh_key = payload.get("ssh_key") or None
    os_type = str(payload.get("os_type") or "ubuntu").strip()

    if not host or not username:
        return {"status": "error", "error": "host and username are required"}

    started = time.time()
    try:
        result = _run_hardening_with_creds(host, port, username, password, ssh_key, os_type)
    except Exception as exc:
        logger.error("Hardening check failed: %s", exc)
        return {"status": "error", "error": str(exc)}

    raw_output = result.get("raw_output", "")
    fail_count = raw_output.count("[FAIL]")
    warn_count = raw_output.count("[WARN]")
    result["duration_seconds"] = int(time.time() - started)
    result["fail_count"] = fail_count
    result["warn_count"] = warn_count
    result["analysis"] = None

    if fail_count > 0 or warn_count > 0:
        try:
            prompt = f"""Bạn là chuyên gia bảo mật hạ tầng nội bộ. Phân tích kết quả hardening check sau bằng tiếng Việt, có cấu trúc rõ ràng và ưu tiên hành động.

Server: {username}@{host}:{port}
OS: {os_type}
Kết quả kỹ thuật: {fail_count} FAIL, {warn_count} WARN

Raw output:
{raw_output[:6000]}

Yêu cầu:
# Báo cáo Hardening {os_type}

Mở đầu 2-4 câu nêu trạng thái tổng thể, rủi ro chính, nhóm cấu hình cần xử lý trước.

## Tóm tắt trạng thái
Tạo bảng Pass/Fail/Warn nếu có dữ liệu.

## Phát hiện ưu tiên
Mỗi finding quan trọng có: vấn đề, bằng chứng, rủi ro, khắc phục, kiểm tra lại.

## Ưu tiên hành động
Sắp theo P1/P2/Theo dõi. Không bịa finding ngoài raw output."""
            result["analysis"] = llm.invoke([HumanMessage(content=prompt)]).content
        except Exception as exc:
            logger.error("Hardening LLM analysis failed: %s", exc)
            result["analysis"] = f"(Không tạo được phân tích tự động: {exc})"

    for channel_name, sender in (
        ("Teams", _send_teams_hardening_report),
        ("Telegram", _send_telegram_hardening_report),
    ):
        try:
            if sender(host, username, port, os_type, result, raw_output, fail_count, warn_count):
                logger.info("Hardening report sent to %s: %s", channel_name, host)
        except Exception as exc:
            logger.error("%s hardening report failed: %s", channel_name, exc)

    return {"status": "success", "result": result}


def _send_teams_hardening_report(host, username, port, os_type, result, raw_output, fail_count, warn_count) -> bool:
    from src.tools.teams import _send_report

    return bool(_send_report(
        title=f"Hardening Report: {host} - {fail_count} FAIL, {warn_count} WARN",
        sections=[{
            "type": "hardening_alert",
            "server": f"{username}@{host}:{port}",
            "os": result.get("os_type", os_type),
            "fail_count": fail_count,
            "warn_count": warn_count,
            "analysis": result.get("analysis") or "",
            "output": raw_output,
        }],
    ))


def _send_telegram_hardening_report(host, username, port, os_type, result, raw_output, fail_count, warn_count) -> bool:
    from src.tools.telegram import _send_report

    return bool(_send_report(
        title=f"Hardening Report: {host} - {fail_count} FAIL, {warn_count} WARN",
        sections=[{
            "type": "hardening_alert",
            "server": f"{username}@{host}:{port}",
            "os": result.get("os_type", os_type),
            "fail_count": fail_count,
            "warn_count": warn_count,
            "analysis": result.get("analysis") or "",
            "output": raw_output,
        }],
    ))


def _handle_vulnerability_scan(payload: dict[str, Any]) -> dict[str, Any]:
    from src.tools.wazuh import _run_wazuh_scan, _send_vulnerability_report

    runtime = _runtime()
    llm = runtime["llm"]
    agent_name = str(payload.get("agent_name") or "").strip()
    include_analysis = bool(payload.get("include_analysis", True))
    send_report = bool(payload.get("send_report", False))

    started = time.time()
    try:
        result = _run_wazuh_scan(agent_name)
    except Exception as exc:
        logger.error("Vulnerability scan failed: %s", exc)
        return {"status": "error", "error": str(exc), "timestamp": datetime.now().isoformat()}

    result["duration_seconds"] = int(time.time() - started)

    if result.get("status") == "completed" and include_analysis:
        try:
            summary = result.get("summary", {}) if isinstance(result.get("summary"), dict) else {}
            top_items = result.get("items", [])[:30] if isinstance(result.get("items"), list) else []
            compact_items = "\n".join(
                f"- {item.get('severity', '')} | {item.get('cve', 'N/A')} | "
                f"{item.get('package', 'unknown')} {item.get('version', '')} | "
                f"asset: {item.get('agent', 'unknown')} | score: {item.get('score', '')}"
                for item in top_items
                if isinstance(item, dict)
            )
            prompt = f"""Bạn là chuyên gia bảo mật hạ tầng nội bộ. Phân tích kết quả Wazuh Vulnerability Detection bằng tiếng Việt cho dashboard SOC.

Phạm vi: {agent_name or "all agents"}
Tổng số: {result.get("total", 0)}
Critical: {summary.get("Critical", 0)}
High: {summary.get("High", 0)}
Medium: {summary.get("Medium", 0)}
Low: {summary.get("Low", 0)}

Top CVEs:
{compact_items or "No vulnerability items returned."}

Yêu cầu:
# Tổng quan lỗ hổng
Mở đầu 2-4 câu nêu rủi ro tổng thể, tài sản/package nổi bật và ưu tiên xử lý.

## Ưu tiên xử lý
1. P1 - ...
2. P2 - ...
3. Theo dõi - ...

## Khuyến nghị vận hành
Không bịa dữ liệu ngoài danh sách trên."""
            result["analysis"] = llm.invoke([HumanMessage(content=prompt)]).content
        except Exception as exc:
            logger.error("Vulnerability LLM analysis failed: %s", exc)
            result["analysis"] = f"(Không tạo được phân tích tự động: {exc})"

    if send_report and result.get("status") == "completed":
        try:
            result["sent_channels"] = _send_vulnerability_report(result, agent_name)
        except Exception as exc:
            logger.error("Vulnerability report delivery failed: %s", exc)
            result["sent_channels"] = []

    return {"status": "success", "result": result, "timestamp": datetime.now().isoformat()}


def _handle_wazuh_agents(payload: dict[str, Any]) -> dict[str, Any]:
    from src.tools.wazuh import _run_wazuh_agent_inventory

    status = str(payload.get("status") or "").strip()
    search = str(payload.get("search") or "").strip()
    try:
        limit = int(payload.get("limit") or 100)
    except (TypeError, ValueError):
        limit = 100
    try:
        result = _run_wazuh_agent_inventory(status=status, search=search, limit=limit)
    except Exception as exc:
        logger.error("Wazuh agent inventory failed: %s", exc)
        return {"status": "error", "error": str(exc), "timestamp": datetime.now().isoformat()}
    return {"status": "success", "result": result, "timestamp": datetime.now().isoformat()}


def _dig(data: dict, *path: str):
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _plain_text(value) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"^\s*@[\w ._-]+\s+", "", text)
    text = re.sub(r"^\s*/agent\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*agent\s*:\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def _extract_chat_message(payload: dict[str, Any]) -> str:
    candidates = [
        payload.get("message"),
        payload.get("text"),
        payload.get("content"),
        payload.get("plainTextContent"),
        _dig(payload, "body", "plainTextContent"),
        _dig(payload, "body", "content"),
        _dig(payload, "message", "body", "plainTextContent"),
        _dig(payload, "message", "body", "content"),
    ]
    for candidate in candidates:
        text = _plain_text(candidate)
        if text:
            return text
    return ""


def _is_telegram_update(payload: dict[str, Any]) -> bool:
    return "update_id" in payload and (
        isinstance(payload.get("message"), dict) or isinstance(payload.get("edited_message"), dict)
    )


def _telegram_chat_allowed(chat_id) -> bool:
    from src.config import TELEGRAM_ALLOWED_CHAT_IDS

    return not TELEGRAM_ALLOWED_CHAT_IDS or str(chat_id) in TELEGRAM_ALLOWED_CHAT_IDS


def _telegram_command_body(text: str) -> str | None:
    from src.config import TELEGRAM_COMMAND_PREFIX

    value = (text or "").strip()
    if not value:
        return None
    parts = value.split(maxsplit=1)
    command = parts[0].split("@", 1)[0].lower()
    if command != TELEGRAM_COMMAND_PREFIX.lower():
        return None
    return parts[1].strip() if len(parts) > 1 else ""


def _run_agent_chat(message: str, user_id: str, session_id: str, source: str | None = None) -> str:
    runtime = _runtime()
    messages = []
    if source == "telegram" and runtime.get("telegram_template"):
        messages.append(("system", runtime["telegram_template"]))
    messages.append(("user", message))
    result = runtime["graph"].invoke(
        {"messages": messages},
        {"configurable": {"thread_id": session_id, "actor_id": user_id}},
    )
    return result["messages"][-1].content


def _handle_telegram_update(payload: dict[str, Any]) -> dict[str, Any]:
    from src.config import TELEGRAM_BOT_TOKEN, TELEGRAM_COMMAND_PREFIX
    from src.tools.telegram import _send_chat_action, _send_message

    message = payload.get("message") or payload.get("edited_message") or {}
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    chat_id = chat.get("id")
    message_id = message.get("message_id")
    text = message.get("text") or message.get("caption") or ""

    if not chat_id:
        return {"status": "ignored", "reason": "telegram chat_id missing"}
    if not TELEGRAM_BOT_TOKEN:
        return {"status": "error", "error": "TELEGRAM_BOT_TOKEN is not configured"}

    command = text.strip().split(maxsplit=1)[0].split("@", 1)[0].lower() if text.strip() else ""
    if command in {"/start", "/help"}:
        _send_message(
            str(chat_id),
            "VNGDC Security Agent\n\n"
            f"Dùng {TELEGRAM_COMMAND_PREFIX} <nội dung> để chat với agent.\n"
            "Dùng /id để xem chat_id.",
            message_id,
        )
        return {"status": "success", "source": "telegram", "action": "help", "chat_id": str(chat_id)}
    if command == "/id":
        _send_message(str(chat_id), f"chat_id: {chat_id}", message_id)
        return {"status": "success", "source": "telegram", "action": "chat_id", "chat_id": str(chat_id)}

    user_message = _telegram_command_body(text)
    if user_message is None:
        return {"status": "ignored", "source": "telegram", "reason": "message does not use command prefix"}
    if not _telegram_chat_allowed(chat_id):
        _send_message(str(chat_id), "Chat này chưa được phép dùng agent.", message_id)
        return {"status": "blocked", "source": "telegram", "chat_id": str(chat_id)}
    if not user_message:
        _send_message(str(chat_id), f"Cú pháp: {TELEGRAM_COMMAND_PREFIX} <nội dung cần hỏi>", message_id)
        return {"status": "success", "source": "telegram", "action": "usage", "chat_id": str(chat_id)}

    try:
        _send_chat_action(str(chat_id))
    except Exception:
        pass

    user_id = f"telegram-{sender.get('id') or chat_id}"
    session_id = f"telegram-{chat_id}"
    try:
        reply = _run_agent_chat(user_message, user_id, session_id, source="telegram")
    except Exception as exc:
        logger.error("Telegram agent chat failed: %s", exc)
        reply = f"Agent lỗi khi xử lý yêu cầu: {exc}"

    _send_message(str(chat_id), reply or "Agent không trả về nội dung.", message_id)
    return {
        "status": "success",
        "source": "telegram",
        "chat_id": str(chat_id),
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
    }


def invoke_agent(payload: dict[str, Any], user_id: str = "", session_id: str = "") -> dict[str, Any]:
    payload = payload or {}

    if _is_telegram_update(payload):
        return _handle_telegram_update(payload)
    if payload.get("action") == "hardening_check":
        return _handle_hardening_check(payload)
    if payload.get("action") == "vulnerability_scan":
        return _handle_vulnerability_scan(payload)
    if payload.get("action") in {"wazuh_agents", "wazuh_inventory", "agent_inventory"}:
        return _handle_wazuh_agents(payload)

    user_id = str(user_id or payload.get("user_id") or payload.get("userId") or "dashboard-user")
    session_id = str(session_id or payload.get("session_id") or payload.get("sessionId") or "dashboard-session")
    message = _extract_chat_message(payload)
    if not message:
        return {
            "status": "error",
            "error": "Message is required. Provide message, text, content, body.content, or body.plainTextContent.",
        }

    try:
        response_text = _run_agent_chat(message, user_id, session_id)
        status = "success"
    except Exception as exc:
        logger.exception("Agent chat failed")
        response_text = (
            "Agent gặp lỗi khi xử lý yêu cầu này.\n\n"
            "Bạn có thể thử lại sau vài giây. Nếu lỗi lặp lại, kiểm tra LLM_API_KEY, LLM_BASE_URL, MEMORY_ID và log runtime.\n\n"
            f"Chi tiết kỹ thuật: {exc}"
        )
        status = "error"

    return {
        "status": status,
        "response": response_text,
        "text": response_text,
        "reply": response_text,
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
    }
