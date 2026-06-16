from __future__ import annotations

from collections import Counter
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sys
import threading
import time
import traceback
from typing import Any
from urllib.parse import urlparse

from infra_log_sentinel.analysis.runbook import recommend_commands
from infra_log_sentinel.analysis.time_window import (
    filter_events_by_lookback,
    filter_events_by_time_range,
    format_time_range_label,
    parse_user_datetime,
)
from infra_log_sentinel.chat.llm_assistant import adjudicate_rca_with_llm, suggest_rca_next_steps_with_llm
from infra_log_sentinel.chat.responder import answer_or_execute_chat
from infra_log_sentinel.config import Settings, load_settings
from infra_log_sentinel.ingestion.local_folder import SUPPORTED_EXTENSIONS, iter_log_lines
from infra_log_sentinel.models import LogEvent, RawLogLine
from infra_log_sentinel.parsing.log_parser import parse_raw_lines
from infra_log_sentinel.notifications.telegram_chat import run_telegram_chat_forever
from infra_log_sentinel.notifications.telegram_sender import send_telegram_message
from infra_log_sentinel.rca import (
    RcaIncidentStore,
    analyze_incident,
    format_rca_telegram,
    generate_incident,
    list_scenarios,
)
from infra_log_sentinel.rca.log_analyzer import analyze_log_events, apply_llm_review, log_rca_compact
from infra_log_sentinel.scheduler.runner import run_scheduler_forever
from infra_log_sentinel.simulator.log_generator import (
    DOMAINS,
    INCIDENT_SCENARIOS,
    generate_incident_log_lines,
    generate_log_lines,
    generate_one_log_line,
)
from infra_log_sentinel.state.runtime_control import (
    CONTROL_EMAIL_REPORTS,
    CONTROL_INCIDENT_GENERATION,
    CONTROL_LOG_GENERATION,
    CONTROL_TELEGRAM_ALERTS,
    VALUE_DEMO_LOG_INTERVAL_SECONDS,
    VALUE_INCIDENT_LOG_INTERVAL_SECONDS,
    VALUE_REPORT_TIME,
    VALUE_SCAN_INTERVAL_SECONDS,
    RuntimeControlStore,
)
from infra_log_sentinel.web_ui import render_chat_ui


SERVICE_NAME = "infra-log-sentinel-agent"
MANUAL_CONTROL_OFF_UNTIL = datetime(9999, 12, 31, 23, 59, 59)
RUNTIME_CONTROL_LABELS = {
    CONTROL_TELEGRAM_ALERTS: "Telegram alerts",
    CONTROL_EMAIL_REPORTS: "Gmail reports",
    CONTROL_LOG_GENERATION: "Log generator",
    CONTROL_INCIDENT_GENERATION: "Incident generator",
}
WORKER_STATUS_LOCK = threading.Lock()
WORKER_STATUS: dict[str, dict[str, str]] = {}


def main() -> None:
    _configure_console_encoding()
    settings = load_settings()
    host = os.getenv("RUNTIME_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("RUNTIME_PORT", "8080")))

    _prepare_runtime_storage(settings)
    _bootstrap_runtime_logs(settings)
    _start_background_workers(settings)

    server = ThreadingHTTPServer((host, port), _handler_for(settings))
    print(f"{SERVICE_NAME} runtime listening on {host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Runtime stopped.", flush=True)
    finally:
        server.server_close()


def _handler_for(settings: Settings) -> type[BaseHTTPRequestHandler]:
    class RuntimeHandler(BaseHTTPRequestHandler):
        server_version = "InfraLogSentinelHTTP/1.0"

        def do_GET(self) -> None:
            path = _normalized_path(self.path)
            if path == "/health":
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "status": "ok",
                        "service": SERVICE_NAME,
                    },
                )
                return

            if path == "/status":
                self._write_json(HTTPStatus.OK, _build_status(settings))
                return

            if path in {"/", "/ui"}:
                self._write_html(HTTPStatus.OK, render_chat_ui(SERVICE_NAME))
                return

            if path == "/api":
                self._write_json(
                    HTTPStatus.OK,
                    {
                        "service": SERVICE_NAME,
                        "endpoints": {
                            "health": "GET /health",
                            "status": "GET /status",
                            "invocations": "POST /invocations",
                            "chat": "POST /chat",
                            "runtime_controls": "POST /runtime-controls",
                            "rca_generate": "POST /demo/incidents/generate",
                            "rca_analyze": "POST /incidents/analyze",
                            "rca_latest": "GET /incidents/latest",
                            "rca_telegram_test": "POST /telegram/test",
                            "log_rca_generate": "POST /rca/logs/generate",
                            "log_rca_analyze": "POST /rca/logs/analyze",
                        },
                    },
                )
                return

            if path == "/incidents/latest":
                latest = RcaIncidentStore(settings.state_db_path).latest()
                if latest is None:
                    self._write_error(HTTPStatus.NOT_FOUND, "No RCA incident has been analyzed yet.")
                    return
                self._write_json(HTTPStatus.OK, {"status": "ok", **latest})
                return

            self._write_error(HTTPStatus.NOT_FOUND, f"Unknown path: {path}")

        def do_POST(self) -> None:
            path = _normalized_path(self.path)
            if path == "/demo/incidents/generate":
                payload = self._read_optional_json()
                if payload is None:
                    return
                try:
                    result = _generate_rca_incident(settings, payload)
                except Exception as exc:  # pragma: no cover - defensive API boundary
                    traceback.print_exc()
                    self._write_error(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        f"{type(exc).__name__}: {exc}",
                    )
                    return
                self._write_json(HTTPStatus.OK, result)
                return

            if path == "/rca/logs/generate":
                payload = self._read_optional_json()
                if payload is None:
                    return
                try:
                    result = _generate_log_rca_incident(settings, payload)
                except ValueError as exc:
                    self._write_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                except Exception as exc:  # pragma: no cover - defensive API boundary
                    traceback.print_exc()
                    self._write_error(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        f"{type(exc).__name__}: {exc}",
                    )
                    return
                self._write_json(HTTPStatus.OK, result)
                return

            if path == "/rca/logs/analyze":
                payload = self._read_optional_json()
                if payload is None:
                    return
                try:
                    result = _analyze_current_logs_for_rca(settings, payload)
                except Exception as exc:  # pragma: no cover - defensive API boundary
                    traceback.print_exc()
                    self._write_error(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        f"{type(exc).__name__}: {exc}",
                    )
                    return
                self._write_json(HTTPStatus.OK, result)
                return

            if path == "/incidents/analyze":
                payload = self._read_optional_json()
                if payload is None:
                    return
                try:
                    result = _analyze_rca_incident(settings, payload)
                except ValueError as exc:
                    self._write_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                except Exception as exc:  # pragma: no cover - defensive API boundary
                    traceback.print_exc()
                    self._write_error(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        f"{type(exc).__name__}: {exc}",
                    )
                    return
                self._write_json(HTTPStatus.OK, result)
                return

            if path == "/telegram/test":
                payload = self._read_optional_json()
                if payload is None:
                    return
                try:
                    result = _send_rca_telegram_test(settings, payload)
                except ValueError as exc:
                    self._write_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                except Exception as exc:  # pragma: no cover - defensive API boundary
                    traceback.print_exc()
                    self._write_error(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        f"{type(exc).__name__}: {exc}",
                    )
                    return
                self._write_json(HTTPStatus.OK, result)
                return

            if path == "/runtime-controls":
                payload = self._read_json()
                if payload is None:
                    return
                try:
                    result = _update_runtime_control(settings, payload)
                except ValueError as exc:
                    self._write_error(HTTPStatus.BAD_REQUEST, str(exc))
                    return
                except Exception as exc:  # pragma: no cover - defensive API boundary
                    traceback.print_exc()
                    self._write_error(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        f"{type(exc).__name__}: {exc}",
                    )
                    return
                self._write_json(HTTPStatus.OK, result)
                return

            if path not in {"/invocations", "/chat"}:
                self._write_error(HTTPStatus.NOT_FOUND, f"Unknown path: {path}")
                return

            payload = self._read_json()
            if payload is None:
                return

            question = _extract_question(payload)
            if not question:
                self._write_error(
                    HTTPStatus.BAD_REQUEST,
                    "Request JSON must include one of: message, question, input, prompt, or messages.",
                )
                return

            try:
                channel = _extract_conversation_channel(payload)
                answer = _answer_or_execute_chat(
                    settings=settings,
                    question=question,
                    dry_run=bool(payload.get("dry_run", False)),
                    channel=channel,
                )
            except Exception as exc:  # pragma: no cover - defensive API boundary
                traceback.print_exc()
                self._write_error(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    f"{type(exc).__name__}: {exc}",
                )
                return

            self._write_json(
                HTTPStatus.OK,
                {
                    "service": SERVICE_NAME,
                    "question": question,
                    "answer": answer,
                },
            )

        def log_message(self, format: str, *args: Any) -> None:
            sys.stderr.write("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args))

        def _read_json(self) -> dict[str, Any] | None:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                self._write_error(HTTPStatus.BAD_REQUEST, "Request body must be valid JSON.")
                return None
            if length > 1_000_000:
                self._write_error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body is too large.")
                return None

            raw_body = self.rfile.read(length)
            try:
                payload = json.loads(raw_body.decode("utf-8"))
            except json.JSONDecodeError as exc:
                self._write_error(HTTPStatus.BAD_REQUEST, f"Invalid JSON: {exc}")
                return None

            if not isinstance(payload, dict):
                self._write_error(HTTPStatus.BAD_REQUEST, "Request JSON must be an object.")
                return None
            return payload

        def _read_optional_json(self) -> dict[str, Any] | None:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            return self._read_json()

        def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_html(self, status: HTTPStatus, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _write_error(self, status: HTTPStatus, message: str) -> None:
            self._write_json(status, {"error": status.phrase, "message": message})

    return RuntimeHandler


def _answer_or_execute_chat(
    settings: Settings,
    question: str,
    dry_run: bool,
    channel: str = "web",
) -> str:
    return answer_or_execute_chat(settings, question, dry_run=dry_run, channel=channel)


def _update_runtime_control(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    store = RuntimeControlStore(settings.state_db_path)
    control = payload.get("control")
    if isinstance(control, str) and control:
        if control not in RUNTIME_CONTROL_LABELS:
            raise ValueError("Unsupported runtime control.")
        enabled = _payload_bool(payload.get("enabled"))
        if enabled is None:
            raise ValueError("Runtime control update requires boolean field: enabled.")
        if enabled:
            store.resume(control)
            message = f"{RUNTIME_CONTROL_LABELS[control]} enabled."
        else:
            store.pause_until(control, MANUAL_CONTROL_OFF_UNTIL)
            message = f"{RUNTIME_CONTROL_LABELS[control]} disabled until it is enabled again."
        return {
            "service": SERVICE_NAME,
            "message": message,
            "status": _build_status(settings),
        }

    setting = payload.get("setting")
    if setting == VALUE_DEMO_LOG_INTERVAL_SECONDS:
        seconds = _payload_float(payload.get("seconds"))
        if seconds is None:
            raise ValueError("Generator interval update requires numeric field: seconds.")
        if seconds < 1 or seconds > 86400:
            raise ValueError("Generator interval must be between 1 and 86400 seconds.")
        stored_value = str(int(seconds)) if seconds.is_integer() else f"{seconds:g}"
        store.set_value(VALUE_DEMO_LOG_INTERVAL_SECONDS, stored_value)
        return {
            "service": SERVICE_NAME,
            "message": f"Generator interval saved: {stored_value}s.",
            "status": _build_status(settings),
        }

    if setting == VALUE_INCIDENT_LOG_INTERVAL_SECONDS:
        seconds = _payload_float(payload.get("seconds"))
        if seconds is None:
            raise ValueError("Incident generator interval update requires numeric field: seconds.")
        if seconds < 1 or seconds > 86400:
            raise ValueError("Incident generator interval must be between 1 and 86400 seconds.")
        stored_value = str(int(seconds)) if seconds.is_integer() else f"{seconds:g}"
        store.set_value(VALUE_INCIDENT_LOG_INTERVAL_SECONDS, stored_value)
        return {
            "service": SERVICE_NAME,
            "message": f"Incident generator interval saved: {stored_value}s.",
            "status": _build_status(settings),
        }

    if setting == VALUE_REPORT_TIME:
        report_time = _normalize_report_time(payload.get("value") or payload.get("report_time"))
        if report_time is None:
            raise ValueError("Report time update requires value formatted as HH:MM.")
        store.set_value(VALUE_REPORT_TIME, report_time)
        return {
            "service": SERVICE_NAME,
            "message": f"Report time saved: {report_time}.",
            "status": _build_status(settings),
        }

    if setting == VALUE_SCAN_INTERVAL_SECONDS:
        seconds = _payload_float(payload.get("seconds"))
        if seconds is None:
            raise ValueError("Scan interval update requires numeric field: seconds.")
        if seconds < 1 or seconds > 86400:
            raise ValueError("Scan interval must be between 1 and 86400 seconds.")
        stored_value = str(int(seconds)) if seconds.is_integer() else f"{seconds:g}"
        store.set_value(VALUE_SCAN_INTERVAL_SECONDS, stored_value)
        return {
            "service": SERVICE_NAME,
            "message": f"Scan interval saved: {stored_value}s.",
            "status": _build_status(settings),
        }

    raise ValueError("Request must include a supported control or setting.")


def _payload_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on", "enabled"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", "disabled"}:
            return False
    return None


def _payload_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _normalize_report_time(value: Any) -> str | None:
    text = _payload_text(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


def _generate_rca_incident(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    scenario = _payload_text(payload.get("scenario") or payload.get("type") or payload.get("case"))
    incident = generate_incident(scenario)
    analysis = analyze_incident(incident)
    RcaIncidentStore(settings.state_db_path).save(incident, analysis)
    telegram_message_id = _send_rca_if_requested(settings, payload, analysis)
    return {
        "status": "ok",
        "available_scenarios": list_scenarios(),
        "incident": incident,
        "analysis": analysis,
        "telegram_message_id": telegram_message_id,
    }


def _analyze_rca_incident(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    incident = payload.get("incident") if isinstance(payload.get("incident"), dict) else payload
    if not isinstance(incident, dict) or not incident:
        raise ValueError("Request JSON must include an incident object or incident fields.")
    analysis = analyze_incident(incident)
    RcaIncidentStore(settings.state_db_path).save(incident, analysis)
    telegram_message_id = _send_rca_if_requested(settings, payload, analysis)
    return {
        "status": "ok",
        "incident": incident,
        "analysis": analysis,
        "telegram_message_id": telegram_message_id,
    }


def _send_rca_telegram_test(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    store = RcaIncidentStore(settings.state_db_path)
    incident_id = _payload_text(payload.get("incident_id"))
    record = store.get(incident_id) if incident_id else store.latest()
    if record is None:
        incident = generate_incident(_payload_text(payload.get("scenario")))
        analysis = analyze_incident(incident)
        store.save(incident, analysis)
        record = {"incident": incident, "analysis": analysis}

    analysis = record["analysis"]
    message = _payload_text(payload.get("message")) or format_rca_telegram(analysis)
    dry_run = _payload_bool(payload.get("dry_run")) is True
    if dry_run:
        return {
            "status": "dry_run",
            "incident_id": analysis.get("incident_id"),
            "message": message,
        }

    message_id = send_telegram_message(settings=settings, text=message, parse_mode="HTML")
    return {
        "status": "sent",
        "incident_id": analysis.get("incident_id"),
        "telegram_message_id": message_id,
    }


def _send_rca_if_requested(
    settings: Settings,
    payload: dict[str, Any],
    analysis: dict[str, Any],
) -> int | None:
    if _payload_bool(payload.get("send_telegram")) is not True:
        return None
    return send_telegram_message(
        settings=settings,
        text=format_rca_telegram(analysis),
        parse_mode="HTML",
    )


def _generate_log_rca_incident(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    scenario = _payload_text(payload.get("scenario") or payload.get("type") or payload.get("case"))
    selected_scenario = scenario or "broadcast_loop"
    generated = generate_incident_log_lines(settings.log_root_path, scenario or "broadcast_loop")
    lookback_hours = _payload_float(payload.get("lookback_hours")) or settings.report_lookback_hours
    focus_text = (
        _payload_text(payload.get("focus") or payload.get("impact") or payload.get("description"))
        or selected_scenario.replace("_", " ")
    )
    generated_events = _events_from_generated_log_lines(generated)
    analysis = analyze_log_events(
        generated_events,
        lookback_hours=lookback_hours,
        alert_levels=settings.severity_alert_levels,
        focus_text=focus_text,
        window_label=f"generated {selected_scenario} incident burst",
    )
    _enrich_log_rca_with_llm(settings, focus_text or selected_scenario, analysis, generated_events)
    incident = {
        "incident_id": analysis["incident_id"],
        "source": "log_generator",
        "scenario": selected_scenario,
        "focus_text": focus_text,
        "lookback_hours": lookback_hours,
        "generated_logs": [
            {
                "domain": item.domain,
                "severity": item.severity,
                "path": str(item.path),
                "text": item.text,
            }
            for item in generated
        ],
    }
    RcaIncidentStore(settings.state_db_path).save(incident, analysis)
    telegram_message_id = _send_rca_if_requested(settings, payload, analysis)
    return {
        "status": "ok",
        "available_scenarios": list(INCIDENT_SCENARIOS),
        "scenario": selected_scenario,
        "generated_count": len(generated),
        "generated_logs": incident["generated_logs"],
        "analysis": analysis,
        "telegram_message_id": telegram_message_id,
    }


def _analyze_current_logs_for_rca(settings: Settings, payload: dict[str, Any]) -> dict[str, Any]:
    lookback_hours = _payload_float(payload.get("lookback_hours")) or settings.report_lookback_hours
    focus_text = _payload_text(payload.get("focus") or payload.get("impact") or payload.get("description"))
    start_time = parse_user_datetime(_payload_text(payload.get("start_time") or payload.get("from")), settings.app_timezone)
    end_time = parse_user_datetime(_payload_text(payload.get("end_time") or payload.get("to")), settings.app_timezone)
    analysis = _analyze_logs_for_rca(
        settings,
        lookback_hours=lookback_hours,
        focus_text=focus_text,
        start_time=start_time,
        end_time=end_time,
    )
    recent_events = _events_for_rca_context(
        settings,
        lookback_hours=lookback_hours,
        start_time=start_time,
        end_time=end_time,
    )
    _enrich_log_rca_with_llm(settings, focus_text, analysis, recent_events)
    window_label = analysis.get("scope_label") or f"last {lookback_hours:g}h"
    incident = {
        "incident_id": analysis["incident_id"],
        "source": "current_logs",
        "lookback_hours": lookback_hours,
        "window_label": window_label,
        "focus_text": focus_text,
        "analyzed_events": analysis.get("analyzed_events", 0),
    }
    RcaIncidentStore(settings.state_db_path).save(incident, analysis)
    telegram_message_id = _send_rca_if_requested(settings, payload, analysis)
    return {
        "status": "ok",
        "analysis": analysis,
        "telegram_message_id": telegram_message_id,
    }


def _enrich_log_rca_with_llm(
    settings: Settings,
    question: str,
    analysis: dict[str, Any],
    events: list[LogEvent],
) -> None:
    _adjudicate_log_rca_with_llm(settings, question, analysis)
    if _rca_needs_llm_guidance(analysis):
        guidance = suggest_rca_next_steps_with_llm(
            settings=settings,
            events=events,
            question=question or str(analysis.get("summary") or ""),
            analysis=analysis,
            alert_levels=settings.severity_alert_levels,
        )
        if guidance:
            analysis["llm_guidance"] = guidance
        else:
            analysis["llm_guidance"] = _fallback_log_rca_guidance(analysis)


def _adjudicate_log_rca_with_llm(settings: Settings, question: str, analysis: dict[str, Any]) -> None:
    review = adjudicate_rca_with_llm(
        settings=settings,
        question=question or str(analysis.get("summary") or ""),
        analysis=analysis,
    )
    if review:
        apply_llm_review(analysis, review)


def _rca_needs_llm_guidance(analysis: dict[str, Any]) -> bool:
    confidence = int(analysis.get("confidence") or 0)
    return (
        analysis.get("status") == "insufficient_data"
        or confidence < 70
        or analysis.get("incident_id") == "LOG-RCA-FOCUS-NOT-FOUND"
    )


def _fallback_log_rca_guidance(analysis: dict[str, Any]) -> str:
    missing = analysis.get("missing_data") or []
    missing_lines = "\n".join(f"- {item}" for item in list(missing)[:4])
    if not missing_lines:
        missing_lines = "- Timestamp-aligned application, OS, network, and dependency logs around the impact window."
    return (
        "## LLM guidance: RCA chưa đủ dữ liệu"
        "\n- Kết luận: log hiện tại chưa đủ bằng chứng để xác nhận nguyên nhân gốc."
        "\n- Vì sao chưa đủ: correlation hiện tại không có đủ event liên quan, timestamp hoặc dependency để kết luận chắc chắn."
        "\n- Dữ liệu cần bổ sung:\n"
        f"{missing_lines}"
        "\n- Bước tiếp theo an toàn: mở rộng time window, thu thêm log/metrics theo component bị impact, kiểm tra change record và chạy lại RCA."
    )


def _events_for_rca_context(
    settings: Settings,
    lookback_hours: float,
    start_time: datetime | None,
    end_time: datetime | None,
) -> list[LogEvent]:
    raw_lines = list(iter_log_lines(settings.log_root_path))
    events = parse_raw_lines(raw_lines)
    if start_time is not None and end_time is not None:
        return filter_events_by_time_range(events, start_time=start_time, end_time=end_time)
    return filter_events_by_lookback(events, lookback_hours)


def _analyze_logs_for_rca(
    settings: Settings,
    lookback_hours: float | None = None,
    focus_text: str = "",
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict[str, Any]:
    raw_lines = list(iter_log_lines(settings.log_root_path))
    events = parse_raw_lines(raw_lines)
    selected_lookback_hours = (
        lookback_hours if lookback_hours is not None and lookback_hours > 0 else settings.report_lookback_hours
    )
    if start_time is not None and end_time is not None:
        recent_events = filter_events_by_time_range(events, start_time=start_time, end_time=end_time)
        window_label = format_time_range_label(start_time, end_time)
    else:
        recent_events = filter_events_by_lookback(events, selected_lookback_hours)
        window_label = f"last {selected_lookback_hours:g}h"
    return analyze_log_events(
        recent_events,
        lookback_hours=selected_lookback_hours,
        alert_levels=settings.severity_alert_levels,
        focus_text=focus_text,
        window_label=window_label,
    )


def _events_from_generated_log_lines(generated: list[Any]) -> list[LogEvent]:
    raw_lines = [
        RawLogLine(
            domain=str(item.domain),
            source_file=item.path,
            line_number=index,
            text=str(item.text),
        )
        for index, item in enumerate(generated, start=1)
    ]
    return parse_raw_lines(raw_lines)


def _payload_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _build_status(settings: Settings) -> dict[str, Any]:
    runtime_controls = RuntimeControlStore(settings.state_db_path).snapshot()
    workers = _worker_status_snapshot()
    try:
        raw_lines = list(iter_log_lines(settings.log_root_path))
        events = parse_raw_lines(raw_lines)
    except FileNotFoundError as exc:
        log_rca_analysis = analyze_log_events(
            [],
            lookback_hours=settings.report_lookback_hours,
            alert_levels=settings.severity_alert_levels,
        )
        return {
            "status": "degraded",
            "service": SERVICE_NAME,
            "error": str(exc),
            "config": _safe_config(settings, runtime_controls),
            "runtime_controls": runtime_controls,
            "workers": workers,
            "delivery": _delivery_status(settings, runtime_controls, workers),
            "rca": _rca_status(settings, log_rca_analysis),
            "raw_lines": 0,
            "parsed_events": 0,
            "severity_counts": {},
            "domain_counts": {},
            "top_alerts": [],
        }

    recent_events = filter_events_by_lookback(events, settings.report_lookback_hours)
    log_rca_analysis = analyze_log_events(
        recent_events,
        lookback_hours=settings.report_lookback_hours,
        alert_levels=settings.severity_alert_levels,
    )
    alert_levels = set(settings.severity_alert_levels)
    alert_events = sorted(
        [event for event in recent_events if event.severity in alert_levels],
        key=lambda event: (_severity_rank(event.severity), event.domain, event.source, event.event_type),
    )

    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "config": _safe_config(settings, runtime_controls),
        "runtime_controls": runtime_controls,
        "workers": workers,
        "delivery": _delivery_status(settings, runtime_controls, workers),
        "rca": _rca_status(settings, log_rca_analysis),
        "raw_lines": len(raw_lines),
        "parsed_events": len(events),
        "report_window_events": len(recent_events),
        "severity_counts": dict(sorted(Counter(event.severity for event in recent_events).items())),
        "domain_counts": dict(sorted(Counter(event.domain for event in recent_events).items())),
        "top_alerts": [_event_summary(event) for event in alert_events[:5]],
    }


def _safe_config(settings: Settings, runtime_controls: dict[str, Any] | None = None) -> dict[str, Any]:
    values = {}
    if isinstance(runtime_controls, dict) and isinstance(runtime_controls.get("values"), dict):
        values = runtime_controls["values"]
    report_time = _normalize_report_time(values.get(VALUE_REPORT_TIME)) or settings.report_time
    scan_interval = _payload_float(values.get(VALUE_SCAN_INTERVAL_SECONDS))
    scan_interval_seconds = int(scan_interval) if scan_interval and scan_interval >= 1 else settings.scan_interval_seconds
    return {
        "app_env": settings.app_env,
        "app_timezone": settings.app_timezone,
        "log_source_mode": settings.log_source_mode,
        "log_root_path": str(settings.log_root_path),
        "report_time": report_time,
        "report_lookback_hours": settings.report_lookback_hours,
        "scan_interval_seconds": scan_interval_seconds,
        "severity_alert_levels": list(settings.severity_alert_levels),
        "runtime_log_bootstrap_enabled": settings.runtime_log_bootstrap_enabled,
        "demo_log_bootstrap_count": settings.demo_log_bootstrap_count,
        "demo_log_generator_enabled": settings.demo_log_generator_enabled,
        "demo_log_interval_seconds": settings.demo_log_interval_seconds,
        "demo_log_domain": settings.demo_log_domain,
        "demo_log_severity": settings.demo_log_severity,
        "incident_log_generator_enabled": settings.incident_log_generator_enabled,
        "incident_log_interval_seconds": settings.incident_log_interval_seconds,
        "runtime_scheduler_enabled": settings.runtime_scheduler_enabled,
        "runtime_scheduler_dry_run": settings.runtime_scheduler_dry_run,
        "telegram_alerts_configured": _telegram_alerts_configured(settings),
        "telegram_chat_enabled": settings.telegram_chat_enabled,
        "telegram_chat_poll_interval_seconds": settings.telegram_chat_poll_interval_seconds,
        "telegram_chat_dry_run": settings.telegram_chat_dry_run,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
    }


def _delivery_status(
    settings: Settings,
    runtime_controls: dict[str, Any],
    workers: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    pauses = runtime_controls.get("pauses", {})
    telegram_pause = pauses.get(CONTROL_TELEGRAM_ALERTS, {}) if isinstance(pauses, dict) else {}
    paused = bool(telegram_pause.get("paused")) if isinstance(telegram_pause, dict) else False
    paused_until = telegram_pause.get("paused_until") if isinstance(telegram_pause, dict) else None
    manual_off = bool(telegram_pause.get("manual_off")) if isinstance(telegram_pause, dict) else False
    configured = _telegram_alerts_configured(settings)
    scheduler_worker = (workers or {}).get("runtime_scheduler", {})
    scheduler_worker_state = scheduler_worker.get("state", "unknown")

    if not configured:
        state = "misconfigured"
        label = "config missing"
        detail = "Telegram bot token or chat id is missing/placeholder."
    elif not settings.runtime_scheduler_enabled:
        state = "disabled"
        label = "scheduler off"
        detail = "Runtime scheduler is disabled, so realtime alert scans are not running."
    elif scheduler_worker_state not in {"running", "unknown"}:
        state = "worker_down"
        label = "worker down"
        detail = "Runtime scheduler worker is not running; alert scans are not executing."
    elif settings.runtime_scheduler_dry_run:
        state = "dry_run"
        label = "dry-run"
        detail = "Runtime scheduler is in preview mode and will not send Telegram alerts."
    elif paused and manual_off:
        state = "off"
        label = "off"
        detail = "Telegram alert delivery is off until it is enabled again."
    elif paused:
        state = "paused"
        label = "paused"
        detail = f"Telegram alert delivery is paused until {paused_until}."
    else:
        state = "live"
        label = "live"
        detail = "Runtime scheduler is scanning new logs and sending Telegram alerts."

    return {
        "telegram_alerts": {
            "state": state,
            "label": label,
            "detail": detail,
            "configured": configured,
            "scheduler_enabled": settings.runtime_scheduler_enabled,
            "scheduler_worker_state": scheduler_worker_state,
            "dry_run": settings.runtime_scheduler_dry_run,
            "paused": paused,
            "paused_until": paused_until,
            "manual_off": manual_off,
        }
    }


def _telegram_alerts_configured(settings: Settings) -> bool:
    return _has_real_secret(settings.telegram_bot_token) and _has_real_secret(settings.telegram_chat_id)


def _has_real_secret(value: str) -> bool:
    return value.strip() not in {
        "",
        "replace_with_telegram_bot_token",
        "replace_with_telegram_chat_id",
    }


def _rca_status(settings: Settings, log_rca_analysis: dict[str, Any]) -> dict[str, Any]:
    try:
        latest = RcaIncidentStore(settings.state_db_path).latest()
    except Exception:
        latest = None
    analysis = latest.get("analysis", {}) if isinstance(latest, dict) else {}
    return {
        "available_scenarios": list_scenarios(),
        "available_log_scenarios": list(INCIDENT_SCENARIOS),
        "log_analysis": log_rca_compact(log_rca_analysis),
        "latest_incident_id": analysis.get("incident_id"),
        "latest_status": analysis.get("status"),
        "latest_confidence": analysis.get("confidence"),
    }


def _mark_worker(name: str, state: str, detail: str = "") -> None:
    with WORKER_STATUS_LOCK:
        WORKER_STATUS[name] = {
            "state": state,
            "detail": detail,
            "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }


def _worker_status_snapshot() -> dict[str, dict[str, str]]:
    with WORKER_STATUS_LOCK:
        return {name: dict(status) for name, status in WORKER_STATUS.items()}


def _event_summary(event: LogEvent) -> dict[str, Any]:
    return {
        "timestamp": event.timestamp,
        "domain": event.domain,
        "source": event.source,
        "severity": event.severity,
        "event_type": event.event_type,
        "message": event.message,
        "probable_cause": event.probable_cause,
        "impact": event.impact,
        "recommended_action": event.recommended_action,
        "commands": [
            {
                "phase": command.phase,
                "command": command.command,
                "purpose": command.purpose,
            }
            for command in recommend_commands(event)[:3]
        ],
    }


def _extract_question(payload: dict[str, Any]) -> str:
    for key in ("message", "question", "input", "prompt"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    messages = payload.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    return ""


def _extract_conversation_channel(payload: dict[str, Any]) -> str:
    for key in ("conversation_id", "session_id", "channel"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "web"


def _normalized_path(raw_path: str) -> str:
    path = urlparse(raw_path).path.rstrip("/")
    return path or "/"


def _severity_rank(severity: str) -> int:
    return {"critical": 0, "error": 1, "warning": 2, "info": 3}.get(severity, 99)


def _prepare_runtime_storage(settings: Settings) -> None:
    settings.log_root_path.mkdir(parents=True, exist_ok=True)
    settings.report_output_dir.mkdir(parents=True, exist_ok=True)
    settings.state_db_path.parent.mkdir(parents=True, exist_ok=True)
    if settings.log_source_mode == "runtime_folder":
        for domain in DOMAINS:
            (settings.log_root_path / domain).mkdir(parents=True, exist_ok=True)
    print(f"Runtime log folder ready: {settings.log_root_path}", flush=True)


def _bootstrap_runtime_logs(settings: Settings) -> None:
    if not settings.runtime_log_bootstrap_enabled:
        return
    if settings.demo_log_bootstrap_count <= 0:
        return
    if _log_folder_has_files(settings):
        print("Runtime log bootstrap skipped: existing log files found.", flush=True)
        return

    generated = generate_log_lines(
        log_root_path=settings.log_root_path,
        count=settings.demo_log_bootstrap_count,
        interval_seconds=0,
        domain=settings.demo_log_domain,
        severity=settings.demo_log_severity,
    )
    print(
        f"Runtime log bootstrap generated {len(generated)} synthetic log line(s) "
        f"in {settings.log_root_path}.",
        flush=True,
    )


def _start_background_workers(settings: Settings) -> None:
    if settings.demo_log_generator_enabled:
        thread = threading.Thread(
            target=_run_demo_log_generator,
            args=(settings,),
            name="demo-log-generator",
            daemon=True,
        )
        thread.start()
        print(
            "Demo log generator started: "
            f"interval={settings.demo_log_interval_seconds}s "
            f"domain={settings.demo_log_domain} severity={settings.demo_log_severity}.",
            flush=True,
        )

    if settings.incident_log_generator_enabled:
        thread = threading.Thread(
            target=_run_incident_log_generator,
            args=(settings,),
            name="incident-log-generator",
            daemon=True,
        )
        thread.start()
        print(
            "Incident log generator started: "
            f"interval={settings.incident_log_interval_seconds}s "
            f"scenarios={len(INCIDENT_SCENARIOS)}.",
            flush=True,
        )

    if settings.runtime_scheduler_enabled:
        thread = threading.Thread(
            target=_run_scheduler_background,
            args=(settings,),
            name="runtime-scheduler",
            daemon=True,
        )
        thread.start()
        print(
            "Runtime scheduler started: "
            f"dry_run={settings.runtime_scheduler_dry_run} "
            f"scan_interval={settings.scan_interval_seconds}s.",
            flush=True,
        )

    if settings.telegram_chat_enabled:
        thread = threading.Thread(
            target=_run_telegram_chat_background,
            args=(settings,),
            name="telegram-chat-bridge",
            daemon=True,
        )
        thread.start()
        print(
            "Telegram chat bridge enabled: "
            f"interval={settings.telegram_chat_poll_interval_seconds}s "
            f"dry_run={settings.telegram_chat_dry_run}.",
            flush=True,
        )


def _run_demo_log_generator(settings: Settings) -> None:
    _mark_worker("demo_log_generator", "running")
    control_store = RuntimeControlStore(settings.state_db_path)
    while True:
        interval_seconds = control_store.get_float_value(
            VALUE_DEMO_LOG_INTERVAL_SECONDS,
            settings.demo_log_interval_seconds,
        )
        pause_state = control_store.pause_state(CONTROL_LOG_GENERATION)
        if pause_state.paused:
            print(
                f"Demo log generator paused until {pause_state.paused_until:%Y-%m-%d %H:%M:%S}.",
                flush=True,
            )
            time.sleep(max(min(interval_seconds, 30.0), 1.0))
            continue

        try:
            generated = generate_one_log_line(
                log_root_path=settings.log_root_path,
                domain=settings.demo_log_domain,
                severity=settings.demo_log_severity,
            )
            print(
                "Generated runtime demo log: "
                f"[{generated.severity.upper()}] {generated.domain} -> {generated.path.name}",
                flush=True,
            )
        except Exception:
            traceback.print_exc()
        time.sleep(max(interval_seconds, 1.0))


def _generate_all_incident_log_scenarios(settings: Settings) -> dict[str, Any]:
    scenario_counts: dict[str, int] = {}
    generated_count = 0
    for scenario in INCIDENT_SCENARIOS:
        generated = generate_incident_log_lines(settings.log_root_path, scenario)
        scenario_counts[scenario] = len(generated)
        generated_count += len(generated)
    return {
        "scenario_count": len(scenario_counts),
        "generated_count": generated_count,
        "scenario_counts": scenario_counts,
    }


def _run_incident_log_generator(settings: Settings) -> None:
    _mark_worker("incident_log_generator", "running")
    control_store = RuntimeControlStore(settings.state_db_path)
    while True:
        interval_seconds = control_store.get_float_value(
            VALUE_INCIDENT_LOG_INTERVAL_SECONDS,
            settings.incident_log_interval_seconds,
        )
        pause_state = control_store.pause_state(CONTROL_INCIDENT_GENERATION)
        if pause_state.paused:
            print(
                f"Incident log generator paused until {pause_state.paused_until:%Y-%m-%d %H:%M:%S}.",
                flush=True,
            )
            time.sleep(max(min(interval_seconds, 30.0), 1.0))
            continue

        try:
            result = _generate_all_incident_log_scenarios(settings)
            print(
                "Generated runtime incident log pack: "
                f"{result['scenario_count']} scenarios, {result['generated_count']} log lines.",
                flush=True,
            )
        except Exception:
            traceback.print_exc()
        time.sleep(max(interval_seconds, 1.0))


def _run_scheduler_background(settings: Settings) -> None:
    _mark_worker("runtime_scheduler", "running")
    try:
        run_scheduler_forever(
            settings=settings,
            dry_run=settings.runtime_scheduler_dry_run,
            max_alerts=settings.runtime_scheduler_max_alerts,
        )
    except Exception as exc:
        _mark_worker("runtime_scheduler", "stopped", f"{type(exc).__name__}: {exc}")
        traceback.print_exc()


def _run_telegram_chat_background(settings: Settings) -> None:
    _mark_worker("telegram_chat_bridge", "running")
    try:
        run_telegram_chat_forever(
            settings=settings,
            responder=lambda question: _answer_or_execute_chat(
                settings=settings,
                question=question,
                dry_run=settings.telegram_chat_dry_run,
                channel="telegram",
            ),
            dry_run=settings.telegram_chat_dry_run,
        )
    except Exception as exc:
        _mark_worker("telegram_chat_bridge", "stopped", f"{type(exc).__name__}: {exc}")
        traceback.print_exc()


def _log_folder_has_files(settings: Settings) -> bool:
    return any(
        path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        for path in settings.log_root_path.rglob("*")
    )


def _configure_console_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    main()
