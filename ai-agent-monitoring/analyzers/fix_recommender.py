"""
Fix Recommendation Engine — suggests immediate mitigations and long-term fixes.
Auto-remediation is OFF by default.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI


_SYSTEM_PROMPT = """Bạn là SRE assistant đề xuất giải pháp khắc phục sự cố hệ thống.

Quy tắc:
- Ưu tiên các hành động an toàn, có thể hoàn tác.
- Không đề xuất lệnh nguy hiểm trừ khi đánh dấu cần phê duyệt.
- Auto-remediation BỊ TẮT — chỉ đề xuất, không thực thi.
- Trả lời bằng tiếng Việt, ngắn gọn và thực tế.
- Tối đa 3 items mỗi mục.

Trả lời ĐÚNG định dạng sau (plain text, không có markdown header):
immediate:
- <hành động 1>
- <hành động 2>
long_term:
- <hành động 1>
need_human_approval:
- <hành động cần phê duyệt>
"""


class FixRecommender:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def recommend(self, root_cause: str, alert_summaries: list[dict], evidence: list[str]) -> dict:
        summaries_text = "\n".join(f"- {s['summary']}" for s in alert_summaries)
        evidence_text = "\n".join(f"- {e}" for e in evidence)

        human_content = (
            f"Root cause: {root_cause}\n\n"
            f"Alert summaries:\n{summaries_text}\n\n"
            f"Evidence:\n{evidence_text}"
        )

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
        response = self.llm.invoke(messages)
        return self._parse_response(response.content)

    @staticmethod
    def _parse_response(text: str) -> dict:
        result = {"immediate": [], "long_term": [], "need_human_approval": []}
        current_key = None
        for line in text.strip().splitlines():
            if line.startswith("immediate:"):
                current_key = "immediate"
            elif line.startswith("long_term:"):
                current_key = "long_term"
            elif line.startswith("need_human_approval:"):
                current_key = "need_human_approval"
            elif line.startswith("- ") and current_key:
                result[current_key].append(line[2:].strip())
        return result
