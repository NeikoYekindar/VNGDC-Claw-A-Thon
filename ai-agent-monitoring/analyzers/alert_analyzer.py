"""
Alert Analyzer — reads alert payload and produces a structured summary.
Uses LLM to interpret alert meaning.
"""

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

from config import settings
from models.alert import Alert


_SYSTEM_PROMPT = """You are an SRE assistant. Analyze the given monitoring alert and produce a concise summary.
Answer these questions:
1. What is this alert about?
2. What instance/service is affected?
3. What is the severity?
4. What type of issue is this: resource, network, application, database, service, filesystem, or external dependency?
5. Could this alert impact users or production systems?

Be concise. Output plain text, no markdown.
"""


class AlertAnalyzer:
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def analyze(self, alert: Alert) -> dict:
        """Analyze a single alert and return a summary dict."""
        alert_text = (
            f"Alert Name: {alert.alert_name}\n"
            f"Severity: {alert.severity}\n"
            f"Instance: {alert.instance}\n"
            f"Service: {alert.service}\n"
            f"Environment: {alert.environment}\n"
            f"Description: {alert.description}\n"
            f"Labels: {alert.labels}\n"
            f"Annotations: {alert.annotations}"
        )

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=alert_text),
        ]

        response = self.llm.invoke(messages)
        return {
            "alert_id": alert.alert_id,
            "alert_name": alert.alert_name,
            "instance": alert.instance,
            "service": alert.service,
            "severity": alert.severity,
            "summary": response.content.strip(),
        }

    def analyze_batch(self, alerts: list[Alert]) -> list[dict]:
        return [self.analyze(a) for a in alerts]
