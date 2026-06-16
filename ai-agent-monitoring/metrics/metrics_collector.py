"""
Metrics collector — fetches metrics from Prometheus or direct node exporters.
Analyzes trends from the time-series data.
"""

import os
from dataclasses import dataclass
from typing import Optional

import httpx

from config import config, settings
from security.sanitizer import sanitize


@dataclass
class MetricsTrend:
    source_url: str
    raw_summary: str
    trend_description: str
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "source_url": self.source_url,
            "trend_description": self.trend_description,
            "error": self.error,
        }


class MetricsCollector:
    def __init__(self):
        self.prometheus_url = os.environ.get(config.metrics.prometheus_url_env, "").rstrip("/")
        self.timeout = config.agent.command_timeout_seconds

    def fetch_from_url(self, url: str) -> MetricsTrend:
        """Fetch raw metrics from a direct URL (node exporter, etc.)."""
        if settings.mock_mode:
            return MetricsTrend(
                source_url=url,
                raw_summary="[MOCK] node_cpu_seconds_total{mode='idle'} 12345",
                trend_description="[MOCK] CPU idle time appears stable. No anomalies detected.",
            )
        try:
            resp = httpx.get(url, timeout=self.timeout)
            resp.raise_for_status()
            raw = sanitize(resp.text[:4000])  # cap to avoid huge payloads
            return MetricsTrend(
                source_url=url,
                raw_summary=raw,
                trend_description=self._summarize_raw(raw),
            )
        except Exception as exc:  # noqa: BLE001
            return MetricsTrend(source_url=url, raw_summary="", trend_description="",
                                error=str(exc))

    def query_prometheus(self, promql: str) -> MetricsTrend:
        """Query Prometheus via HTTP API."""
        if not self.prometheus_url:
            return MetricsTrend(source_url="", raw_summary="", trend_description="",
                                error="PROMETHEUS_URL not configured")
        if settings.mock_mode:
            return MetricsTrend(
                source_url=self.prometheus_url,
                raw_summary="[MOCK] value=92",
                trend_description="[MOCK] Metric spiked to 92% and is trending down.",
            )
        url = f"{self.prometheus_url}/api/v1/query"
        try:
            resp = httpx.get(url, params={"query": promql}, timeout=self.timeout, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()
            raw = sanitize(str(data)[:2000])
            return MetricsTrend(
                source_url=url,
                raw_summary=raw,
                trend_description=self._summarize_prometheus(data),
            )
        except Exception as exc:  # noqa: BLE001
            return MetricsTrend(source_url=url, raw_summary="", trend_description="",
                                error=str(exc))

    def collect_for_alert(self, instance: str, metrics_url: Optional[str]) -> list[MetricsTrend]:
        """Auto-collect metrics relevant to an alert."""
        results = []
        if metrics_url:
            results.append(self.fetch_from_url(metrics_url))
        if config.metrics.allow_direct_instance_metrics and instance:
            node_url = f"http://{instance}:9100/metrics"
            results.append(self.fetch_from_url(node_url))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summarize_raw(raw: str) -> str:
        lines = [l for l in raw.splitlines() if l and not l.startswith("#")]
        if not lines:
            return "No metrics data found."
        return f"Collected {len(lines)} metric lines. Sample: {lines[0][:120]}"

    @staticmethod
    def _summarize_prometheus(data: dict) -> str:
        results = data.get("data", {}).get("result", [])
        if not results:
            return "No results returned from Prometheus."
        values = []
        for r in results[:5]:
            metric = r.get("metric", {})
            value = r.get("value", ["", ""])[1]
            values.append(f"{metric}: {value}")
        return "Prometheus data: " + "; ".join(values)
