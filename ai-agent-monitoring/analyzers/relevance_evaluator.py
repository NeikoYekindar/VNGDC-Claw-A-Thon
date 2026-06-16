"""
Relevance Evaluator — decides if an alert batch needs deep investigation
based on environment, service criticality, and system context.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from config import config
from models.alert import Alert
from models.report import Relevance, Impact


_SYSTEM_PROMPT = """You are an SRE assistant evaluating alert relevance.
Given a batch of alerts and the system context, determine:
1. relevance: "high", "medium", or "low"
2. impact: "critical", "major", "minor", or "informational"
3. reason: one sentence explaining your decision

Respond in this exact format (no markdown, no extra text):
relevance: <high|medium|low>
impact: <critical|major|minor|informational>
reason: <one sentence>

Rules:
- DEFAULT to "medium" relevance unless there is a clear reason to mark low
- Low relevance ONLY when: alert keyword explicitly matches low_relevance_keywords list
- Medium relevance: warning severity on any server/instance, unknown environment, empty service
- High relevance: critical severity, prod environment, or service in critical list
- Any resource alert (CPU, memory, disk) on a running server is at least medium relevance
"""


class RelevanceEvaluator:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self._ctx = config.system_context

    def evaluate(self, alerts: list[Alert], alert_summaries: list[dict]) -> dict:
        """Return relevance, impact, and reason for the batch."""
        # Fast-path: check low-relevance keywords without LLM
        all_text = " ".join(
            f"{a.alert_name} {a.description} {a.labels}"
            for a in alerts
        ).lower()

        for kw in self._ctx.low_relevance_keywords:
            if kw.lower() in all_text:
                # Double-check: not a critical service
                services = [a.service for a in alerts]
                if not any(s in self._ctx.critical_services for s in services):
                    return {
                        "relevance": Relevance.LOW,
                        "impact": Impact.INFORMATIONAL,
                        "reason": f"Alert matches low-relevance keyword '{kw}' and service is not critical.",
                    }

        # LLM evaluation
        context_info = (
            f"Infrastructure type: {self._ctx.infrastructure_type}\n"
            f"Critical environments: {self._ctx.critical_environments}\n"
            f"Critical services: {self._ctx.critical_services}\n"
            f"Low relevance keywords: {self._ctx.low_relevance_keywords}"
        )
        summaries_text = "\n".join(
            f"- [{s['alert_name']}] {s['summary']}" for s in alert_summaries
        )
        human_content = (
            f"System context:\n{context_info}\n\n"
            f"Alert summaries:\n{summaries_text}"
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
            "relevance": Relevance.MEDIUM,
            "impact": Impact.MINOR,
            "reason": "Could not parse LLM response.",
        }
        for line in text.strip().splitlines():
            if line.startswith("relevance:"):
                val = line.split(":", 1)[1].strip().lower()
                result["relevance"] = Relevance(val) if val in Relevance._value2member_map_ else Relevance.MEDIUM
            elif line.startswith("impact:"):
                val = line.split(":", 1)[1].strip().lower()
                result["impact"] = Impact(val) if val in Impact._value2member_map_ else Impact.MINOR
            elif line.startswith("reason:"):
                result["reason"] = line.split(":", 1)[1].strip()
        return result
