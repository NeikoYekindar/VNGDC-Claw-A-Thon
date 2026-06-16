from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

import httpx


LLM_LOCAL_ENV_KEYS = {
    "LLM_API_KEY",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "MASTER_LLM_SYNTHESIS_ENABLED",
    "MASTER_LLM_TIMEOUT_SECONDS",
    "MASTER_LLM_TEMPERATURE",
    "MASTER_LLM_MAX_TOKENS",
}
HERE = Path(__file__).resolve().parent


def _load_local_llm_env() -> None:
    candidate_files = (
        HERE / ".env",
        HERE / ".env.deploy",
        HERE.parent / "vngdc-vul-hardening-all" / ".env",
        HERE.parent / "vngdc-vul-hardening-all" / ".env.deploy",
        HERE.parent / "vngdc-vul-hardening" / ".env",
        HERE.parent / "vngdc-vul-harrdening" / ".env",
    )
    for path in candidate_files:
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
                    if key in LLM_LOCAL_ENV_KEYS and value:
                        os.environ.setdefault(key, value)
        except FileNotFoundError:
            continue


_load_local_llm_env()

PROMPT_PATH = Path(os.getenv("MASTER_AGENT_PROMPT_PATH", Path(__file__).parent / "prompts" / "master_system_prompt.md"))
DEFAULT_LLM_MODEL = "minimax/minimax-m2.5"
DEFAULT_LLM_BASE_URL = "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1"
LLM_TIMEOUT_SECONDS = float(os.getenv("MASTER_LLM_TIMEOUT_SECONDS", "60"))

ROUTING_KEYWORDS: dict[str, tuple[str, ...]] = {
    "monitoring": (
        "monitor",
        "monitoring",
        "metric",
        "metrics",
        "cpu",
        "ram",
        "memory",
        "disk",
        "alert",
        "prometheus",
        "grafana",
        "instance",
        "server",
        "batch",
        "ssh",
        "latency",
        "availability",
        "resource",
        "tài nguyên",
        "tai nguyen",
        "cảnh báo",
        "canh bao",
        "hiệu năng",
        "hieu nang",
        "giám sát",
        "giam sat",
    ),
    "logging": (
        "log",
        "logs",
        "logging",
        "rca",
        "root cause",
        "incident",
        "sự cố",
        "su co",
        "nhật ký",
        "nhat ky",
        "syslog",
        "windows event",
        "vmware",
        "network",
        "flapping",
        "telegram",
        "gmail",
        "report",
        "báo cáo",
        "bao cao",
        "event",
        "runbook",
    ),
    "security": (
        "security",
        "hardening",
        "vul",
        "vulnerability",
        "vulnerabilities",
        "cve",
        "wazuh",
        "cis",
        "patch",
        "compliance",
        "bảo mật",
        "bao mat",
        "lỗ hổng",
        "lo hong",
        "scan",
        "kiểm tra",
        "kiem tra",
        "audit",
        "baseline",
    ),
}

BROAD_KEYWORDS = (
    "tổng quan",
    "tong quan",
    "tổng hợp",
    "tong hop",
    "tất cả",
    "tat ca",
    "all agents",
    "agent",
    "agents",
    "hệ thống",
    "he thong",
    "dashboard",
    "master",
    "trạng thái",
    "trang thai",
    "status",
    "overall",
    "báo cáo tổng",
    "bao cao tong",
)

SLASH_AGENT_COMMANDS = {
    "monitoring": "monitoring",
    "monitor": "monitoring",
    "mon": "monitoring",
    "logging": "logging",
    "log": "logging",
    "logs": "logging",
    "security": "security",
    "sec": "security",
}

DEFAULT_AGENT_QUESTIONS = {
    "monitoring": "Hãy cho biết tổng quan trạng thái monitoring hiện tại và các cảnh báo đáng chú ý.",
    "logging": "Hãy cho biết tổng quan trạng thái logging hiện tại và các sự cố/log đáng chú ý.",
    "security": "Hãy cho biết tổng quan trạng thái security hiện tại, bao gồm hardening, Wazuh và lỗ hổng đáng chú ý.",
}


def load_master_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return (
            "Bạn là VNGDC Master Agent. Hãy điều phối câu hỏi tới các agent con phù hợp, "
            "tự suy luận trên dữ liệu nhận được, và trả lời bằng tiếng Việt tự nhiên, rõ nguồn."
        )


def route_agents(
    message: str,
    available_agents: dict[str, Any],
    target_agents: list[str] | None = None,
) -> list[str]:
    if target_agents:
        selected = [key for key in target_agents if isinstance(key, str) and key in available_agents]
        if selected:
            return _dedupe(selected)

    text = _fold_text(message)
    selected: list[str] = []
    for key, keywords in ROUTING_KEYWORDS.items():
        if key in available_agents and any(_fold_text(keyword) in text for keyword in keywords):
            selected.append(key)

    if any(_fold_text(keyword) in text for keyword in BROAD_KEYWORDS):
        if not selected or len(selected) == 1:
            return list(available_agents)

    return _dedupe(selected) if selected else list(available_agents)


def extract_agent_directive(
    message: str,
    available_agents: dict[str, Any],
) -> tuple[str, list[str] | None, str | None]:
    match = re.match(r"^\s*/([a-zA-Z][\w-]*)(?:\s+([\s\S]*))?$", message)
    if not match:
        return message, None, None

    command = match.group(1).lower()
    agent_key = SLASH_AGENT_COMMANDS.get(command)
    if not agent_key or agent_key not in available_agents:
        return message, None, None

    cleaned_message = (match.group(2) or "").strip()
    if not cleaned_message:
        cleaned_message = DEFAULT_AGENT_QUESTIONS.get(agent_key, "Hãy cho biết tổng quan trạng thái hiện tại.")
    return cleaned_message, [agent_key], command


def build_child_message(message: str, agent_key: str, session_id: str) -> dict[str, Any]:
    if agent_key == "monitoring":
        return {"action": "chat", "message": message, "session_id": session_id}
    if agent_key == "logging":
        return {"message": message, "session_id": session_id, "conversation_id": session_id}
    return {"message": message, "session_id": session_id}


async def synthesize_master_response(
    message: str,
    routed_agents: list[str],
    results: list[Any],
    agent_registry: dict[str, Any],
    conversation_messages: list[dict[str, str]] | None = None,
) -> str:
    if _bool_env("MASTER_LLM_SYNTHESIS_ENABLED", True):
        try:
            llm_response = await _synthesize_with_llm(message, routed_agents, results, agent_registry, conversation_messages)
            if llm_response:
                return llm_response
        except Exception:
            pass
    return synthesize_master_response_fallback(message, routed_agents, results, agent_registry)


def synthesize_master_response_fallback(
    message: str,
    routed_agents: list[str],
    results: list[Any],
    agent_registry: dict[str, Any],
) -> str:
    ok_results = [result for result in results if result.ok]
    failed_results = [result for result in results if not result.ok]
    sections = ", ".join(agent_registry[key].section for key in routed_agents)

    lines = [
        "# Master Agent",
        "",
        f"**Routing:** {sections}.",
        "",
        "## Tổng hợp nhanh",
    ]

    if ok_results:
        for result in ok_results:
            summary = _first_meaningful_line(result.answer)
            latency = f" ({result.latency_ms} ms)" if result.latency_ms is not None else ""
            lines.append(f"- **{result.section}{latency}:** {summary}")
    if failed_results:
        for result in failed_results:
            lines.append(f"- **{result.section}:** không nhận được câu trả lời ({result.error}).")
    if not ok_results:
        lines.append("- Chưa có agent con nào trả lời thành công. Hãy kiểm tra endpoint/runtime của các agent con.")

    lines.extend(["", "## Nhận định của master"])
    lines.append(_master_reasoning_hint(message, routed_agents, results))

    lines.extend(["", "## Chi tiết từ agent con"])
    for result in results:
        lines.extend(
            [
                "",
                f"### {result.section} - {result.name}",
                "",
                result.answer.strip() or "(Không có nội dung trả lời.)",
            ]
        )

    lines.extend(["", "## Gợi ý điều phối", _next_step_hint(routed_agents, results)])
    return "\n".join(lines).strip()


async def _synthesize_with_llm(
    message: str,
    routed_agents: list[str],
    results: list[Any],
    agent_registry: dict[str, Any],
    conversation_messages: list[dict[str, str]] | None = None,
) -> str:
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key:
        return ""

    model = os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL).strip() or DEFAULT_LLM_MODEL
    base_url = os.getenv("LLM_BASE_URL", DEFAULT_LLM_BASE_URL).strip().rstrip("/") or DEFAULT_LLM_BASE_URL
    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"

    payload = {
        "model": model,
        "temperature": float(os.getenv("MASTER_LLM_TEMPERATURE", "0.15")),
        "max_tokens": int(os.getenv("MASTER_LLM_MAX_TOKENS", "3500")),
        "messages": [
            {"role": "system", "content": load_master_prompt()},
            {"role": "user", "content": _build_llm_synthesis_context(message, routed_agents, results, agent_registry, conversation_messages)},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
        response = await client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    message_obj = choices[0].get("message")
    if isinstance(message_obj, dict):
        content = message_obj.get("content")
        if isinstance(content, str):
            return content.strip()
    text = choices[0].get("text")
    return text.strip() if isinstance(text, str) else ""


def _build_llm_synthesis_context(
    message: str,
    routed_agents: list[str],
    results: list[Any],
    agent_registry: dict[str, Any],
    conversation_messages: list[dict[str, str]] | None = None,
) -> str:
    registry = []
    for key in routed_agents:
        agent = agent_registry[key]
        registry.append(
            {
                "key": key,
                "name": agent.name,
                "section": agent.section,
                "description": agent.description,
            }
        )

    child_results = []
    for result in results:
        child_results.append(
            {
                "key": result.key,
                "name": result.name,
                "section": result.section,
                "ok": result.ok,
                "latency_ms": result.latency_ms,
                "error": result.error,
                "answer": _limit_text(result.answer, 9000),
            }
        )

    context = {
        "user_question": message,
        "conversation_memory": _compact_conversation_messages(conversation_messages or []),
        "routed_agents": routed_agents,
        "agent_registry": registry,
        "child_results": child_results,
    }
    return (
        "Hãy tổng hợp câu trả lời cuối cùng cho người dùng từ JSON bên dưới. "
        "Bạn được phép tự suy luận từ câu hỏi, danh sách agent, và kết quả agent con, "
        "nhưng không được bịa số liệu hoặc trạng thái không có trong dữ liệu.\n\n"
        f"```json\n{json.dumps(context, ensure_ascii=False, indent=2)}\n```"
    )


def _compact_conversation_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    compacted = []
    for item in messages[-12:]:
        role = str(item.get("role") or "")
        content = str(item.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        compacted.append(
            {
                "role": role,
                "content": _limit_text(content, 1200),
                "created_at": str(item.get("created_at") or item.get("timestamp") or ""),
            }
        )
    return compacted


def _master_reasoning_hint(message: str, routed_agents: list[str], results: list[Any]) -> str:
    if any(not result.ok for result in results):
        return (
            "Một phần dữ liệu từ agent con chưa sẵn sàng, nên kết luận cần được xem là tạm thời. "
            "Master vẫn tổng hợp các phản hồi còn lại và chỉ ra phần cần kiểm tra lại."
        )
    if len(routed_agents) == 1:
        return "Câu hỏi đang thuộc một domain chính, nên master ưu tiên câu trả lời từ agent chuyên trách và không mở rộng nếu chưa cần."
    return "Câu hỏi cần nhìn đa miền, nên master đối chiếu Monitoring, Logging và Security trước khi đưa ra hướng xử lý."


def _next_step_hint(routed_agents: list[str], results: list[Any]) -> str:
    if any(not result.ok for result in results):
        return "Kiểm tra lại endpoint, `/health`, và `/invocations` của các agent đang lỗi trước khi đưa ra kết luận vận hành."
    if len(routed_agents) == 1:
        return "Nếu cần phân tích chéo, hãy hỏi theo hướng tổng hợp với domain khác để master gọi nhiều agent cùng lúc."
    return "Dùng các mục chi tiết bên dưới để đối chiếu metrics, logs, và posture bảo mật trước khi quyết định xử lý."


def _first_meaningful_line(text: str) -> str:
    clean = re.sub(r"\s+", " ", text.replace("#", " ")).strip()
    if not clean:
        return "Đã trả lời nhưng không có nội dung tóm tắt."
    return clean[:220] + ("..." if len(clean) > 220 else "")


def _limit_text(value: str, limit: int) -> str:
    value = value.strip()
    return value[:limit] + ("..." if len(value) > limit else "")


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _fold_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value.lower())
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", without_marks)


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result
