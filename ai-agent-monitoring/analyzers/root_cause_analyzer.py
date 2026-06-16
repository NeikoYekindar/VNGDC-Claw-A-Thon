"""
Root Cause Analyzer — synthesizes alert data, command output, and metrics
to determine probable root cause with confidence level.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from models.report import Confidence
from utils.knowledge_loader import get_relevant_knowledge


_SYSTEM_PROMPT = """Bạn là SRE assistant phân tích nguyên nhân gốc rễ của sự cố hệ thống.

Quy tắc:
- Không bao giờ tiết lộ credentials, token, password, private key.
- Nếu bằng chứng không đầy đủ, hãy nói rõ và đánh dấu confidence là low hoặc medium.
- Luôn cung cấp mức độ tin cậy: high, medium, hoặc low.
- Trả lời bằng tiếng Việt, ngắn gọn và thực tế.
- Sử dụng knowledge base (nếu có) để hỗ trợ phân tích.

Trả lời ĐÚNG định dạng sau:
root_cause: <một hoặc hai câu mô tả nguyên nhân gốc rễ bằng tiếng Việt>
evidence:
- <bằng chứng 1>
- <bằng chứng 2>
confidence: <high|medium|low>
missing_data: <thông tin còn thiếu để phân tích tốt hơn, hoặc "none">
"""


class RootCauseAnalyzer:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def analyze(
        self,
        alert_summaries: list[dict],
        investigation_steps: list[dict],
        metrics_trends: list[dict],
    ) -> dict:
        investigation_text = "\n".join(
            f"Host {s.get('host', 'unknown')} | {s.get('command', '')}:\n{s.get('stdout', '')[:500]}"
            for s in investigation_steps
        )
        metrics_text = "\n".join(
            f"- {m.get('trend_description', '')}"
            for m in metrics_trends
            if m.get("trend_description")
        )
        summaries_text = "\n".join(
            f"- [{s['alert_name']}] {s['summary']}" for s in alert_summaries
        )

        # Inject relevant knowledge from knowledge base
        all_alert_names = " ".join(s.get("alert_name", "") for s in alert_summaries)
        all_summaries = " ".join(s.get("summary", "") for s in alert_summaries)
        knowledge_context = get_relevant_knowledge(all_alert_names, all_summaries)
        knowledge_section = (
            f"\n\n## Knowledge Base Context\n{knowledge_context}"
            if knowledge_context
            else ""
        )

        human_content = (
            f"Alert summaries:\n{summaries_text}\n\n"
            f"Command investigation results:\n{investigation_text or 'No commands executed.'}\n\n"
            f"Metrics trends:\n{metrics_text or 'No metrics collected.'}"
            f"{knowledge_section}"
        )

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
        response = self.llm.invoke(messages)
        return self._parse_response(response.content)

    @staticmethod
    def _parse_response(text: str) -> dict:
        result = {
            "root_cause": "Unable to determine root cause.",
            "evidence": [],
            "confidence": Confidence.LOW,
            "missing_data": "",
        }
        lines = text.strip().splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("root_cause:"):
                result["root_cause"] = line.split(":", 1)[1].strip()
            elif line.strip() == "evidence:":
                i += 1
                while i < len(lines) and lines[i].startswith("- "):
                    result["evidence"].append(lines[i][2:].strip())
                    i += 1
                continue
            elif line.startswith("confidence:"):
                val = line.split(":", 1)[1].strip().lower()
                result["confidence"] = Confidence(val) if val in Confidence._value2member_map_ else Confidence.LOW
            elif line.startswith("missing_data:"):
                result["missing_data"] = line.split(":", 1)[1].strip()
            i += 1
        return result
