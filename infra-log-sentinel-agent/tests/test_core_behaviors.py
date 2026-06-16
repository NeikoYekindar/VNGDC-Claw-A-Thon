from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from infra_log_sentinel.chat.actions import try_execute_chat_action
from infra_log_sentinel.chat.intent import (
    INTENT_AMBIGUOUS_OPERATIONAL_CHANGE,
    INTENT_ASSISTANT_FEEDBACK,
    INTENT_LOG_QUESTION,
    INTENT_SAFE_ACTION,
    classify_chat_intent,
    normalize_text,
)
from infra_log_sentinel.chat.conversation import ConversationSnapshot, ConversationStore
from infra_log_sentinel.chat.responder import answer_or_execute_chat, _should_start_new_investigation
from infra_log_sentinel.config import Settings
from infra_log_sentinel.ingestion.local_folder import iter_log_lines
from infra_log_sentinel.models import LogEvent, RawLogLine
from infra_log_sentinel.notifications.telegram_format import format_chat_reply_for_telegram
from infra_log_sentinel.notifications.telegram_chat import process_telegram_chat_updates
from infra_log_sentinel.notifications.telegram_sender import TelegramUpdate, format_alert_message
from infra_log_sentinel.parsing.log_parser import parse_raw_line, parse_raw_lines
from infra_log_sentinel.scheduler.runner import _run_job_safely, _schedule_daily_report_job
from infra_log_sentinel.server import (
    _analyze_rca_incident,
    _analyze_current_logs_for_rca,
    _build_status,
    _delivery_status,
    _extract_question,
    _generate_all_incident_log_scenarios,
    _generate_log_rca_incident,
    _generate_rca_incident,
    _prepare_runtime_storage,
    _send_rca_telegram_test,
    _update_runtime_control,
)
from infra_log_sentinel.rca import (
    RcaIncidentStore,
    analyze_incident,
    format_rca_report,
    format_rca_telegram,
    generate_incident,
    list_scenarios,
)
from infra_log_sentinel.rca.log_analyzer import analyze_log_events
from infra_log_sentinel.simulator.log_generator import INCIDENT_SCENARIOS, generate_incident_log_lines
from infra_log_sentinel.simulator.log_generator import generate_one_log_line
from infra_log_sentinel.simulator.log_generator import DOMAINS
from infra_log_sentinel.state.alert_store import AlertStore
from infra_log_sentinel.state.runtime_control import (
    CONTROL_INCIDENT_GENERATION,
    CONTROL_TELEGRAM_ALERTS,
    VALUE_DEMO_LOG_INTERVAL_SECONDS,
    VALUE_INCIDENT_LOG_INTERVAL_SECONDS,
    VALUE_REPORT_TIME,
    VALUE_SCAN_INTERVAL_SECONDS,
    RuntimeControlStore,
)
from infra_log_sentinel.web_ui import render_chat_ui


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        app_timezone="Asia/Ho_Chi_Minh",
        log_source_mode="runtime_folder",
        log_root_path=tmp_path / "logs",
        runtime_log_bootstrap_enabled=False,
        demo_log_bootstrap_count=0,
        demo_log_generator_enabled=False,
        demo_log_interval_seconds=30,
        demo_log_domain="all",
        demo_log_severity="abnormal",
        incident_log_generator_enabled=False,
        incident_log_interval_seconds=300,
        runtime_scheduler_enabled=False,
        runtime_scheduler_dry_run=True,
        runtime_scheduler_max_alerts=3,
        runtime_scheduler_max_escalations=1,
        report_time="09:00",
        report_lookback_hours=24,
        scan_interval_seconds=60,
        escalation_timeout_seconds=300,
        severity_alert_levels=("warning", "error", "critical"),
        state_db_path=tmp_path / "state.sqlite",
        report_output_dir=tmp_path / "reports",
        gmail_address="",
        gmail_app_password="",
        report_recipient_email="",
        telegram_bot_token="",
        telegram_chat_id="",
        telegram_ack_keywords=("ACK", "ack"),
        telegram_chat_enabled=False,
        telegram_chat_poll_interval_seconds=3,
        telegram_chat_dry_run=False,
        llm_provider="greennode",
        llm_api_base="",
        llm_api_key="",
        llm_model="minimax/minimax-m2.5",
    )


def test_parse_network_power_supply_failure_as_critical() -> None:
    event = parse_raw_line(
        RawLogLine(
            domain="network",
            source_file=Path("network-sample.log"),
            line_number=1,
            text=(
                "2026-06-12T10:00:00Z core-sw01.example.local "
                "%PLATFORM-2-PS_FAIL: Power supply 2 failed or removed"
            ),
        )
    )

    assert event.severity == "critical"
    assert event.event_type == "power_supply_failure"
    assert event.source == "core-sw01.example.local"


def test_ambiguous_interval_change_asks_for_clarification(tmp_path: Path) -> None:
    result = try_execute_chat_action(
        settings=_settings(tmp_path),
        events=[],
        question="doi interval thanh 120 giay",
        dry_run=False,
    )

    assert result.handled is True
    assert "interval" in result.message.lower()
    assert "sinh log" in result.message.lower()


def test_log_generator_interval_dry_run_does_not_mutate_state(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    result = try_execute_chat_action(
        settings=settings,
        events=[],
        question="doi interval sinh log 120 giay",
        dry_run=True,
    )

    assert result.handled is True
    assert "preview" in result.message.lower()
    assert (
        RuntimeControlStore(settings.state_db_path).get_value(VALUE_DEMO_LOG_INTERVAL_SECONDS)
        is None
    )


def test_summary_log_question_is_not_runtime_change_action(tmp_path: Path) -> None:
    result = try_execute_chat_action(
        settings=_settings(tmp_path),
        events=[],
        question="Tóm tắt log hôm nay",
        dry_run=False,
    )

    assert result.handled is False


def test_intent_router_separates_log_questions_from_actions() -> None:
    summary = classify_chat_intent("Tóm tắt log hôm nay")
    command = classify_chat_intent("command xử lý vmware warning")
    email = classify_chat_intent("gửi báo cáo hôm nay qua Gmail")
    ambiguous = classify_chat_intent("đổi interval thành 120 giây")
    feedback = classify_chat_intent(
        "Tôi đang hỏi bạn chứ không phải yêu cầu bạn xuất log warning"
    )
    correction = classify_chat_intent(
        "trong câu hỏi trên không đề cập đến việc thay đổi cấu hình gì cả"
    )

    assert summary.kind == INTENT_LOG_QUESTION
    assert summary.action_candidate is False
    assert summary.rules_first is True
    assert command.kind == INTENT_LOG_QUESTION
    assert command.rules_first is True
    assert email.kind == INTENT_SAFE_ACTION
    assert email.action_candidate is True
    assert ambiguous.kind == INTENT_AMBIGUOUS_OPERATIONAL_CHANGE
    assert ambiguous.action_candidate is True
    assert feedback.kind == INTENT_ASSISTANT_FEEDBACK
    assert feedback.action_candidate is False
    assert feedback.rules_first is False
    assert correction.kind == INTENT_ASSISTANT_FEEDBACK
    assert correction.action_candidate is False
    assert correction.rules_first is False


def test_action_layer_rejects_log_summary_and_user_corrections(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    summary = try_execute_chat_action(
        settings=settings,
        events=[],
        question="tóm tắt log hôm nay",
        dry_run=False,
    )
    correction = try_execute_chat_action(
        settings=settings,
        events=[],
        question="trong câu hỏi trên không đề cập đến việc thay đổi cấu hình gì cả",
        dry_run=False,
    )

    assert summary.handled is False
    assert correction.handled is False


def test_feedback_question_does_not_dump_warning_logs(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    log_file = settings.log_root_path / "linux" / "dynamic-linux.log"
    log_file.write_text(
        (
            "Jun 12 10:00:00 linux-web01.example.local sshd[1842]: "
            "Failed password for invalid user admin from 203.0.113.79 port 51520 ssh2\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "infra_log_sentinel.chat.responder.answer_with_llm",
        lambda *args, **kwargs: None,
    )

    answer = answer_or_execute_chat(
        settings,
        "Tôi đang hỏi bạn chứ không phải yêu cầu bạn xuất log warning",
        dry_run=False,
    )

    assert "không phải yêu cầu truy vấn" in answer
    assert "Failed password" not in answer
    assert "[WARNING]" not in answer


def test_summary_log_question_uses_deterministic_answer_before_llm(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    log_file = settings.log_root_path / "network" / "dynamic-network.log"
    log_file.write_text(
        (
            "2026-06-12T10:00:00Z core-sw01.example.local "
            "%PLATFORM-2-PS_FAIL: Power supply 2 failed or removed\n"
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "infra_log_sentinel.chat.responder.answer_with_llm",
        lambda *args, **kwargs: "WRONG RUNTIME ACTION ANSWER",
    )
    def fail_if_action_layer_is_called(*args, **kwargs):
        raise AssertionError("summary log question should not enter action layer")

    monkeypatch.setattr(
        "infra_log_sentinel.chat.responder.try_execute_chat_action",
        fail_if_action_layer_is_called,
    )

    answer = answer_or_execute_chat(settings, "Tóm tắt log hôm nay", dry_run=False)

    assert "WRONG RUNTIME ACTION ANSWER" not in answer
    assert "Power supply 2 failed or removed" in answer


def test_report_requested_in_chat_stays_inline_without_pdf_or_mail(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log_file = settings.log_root_path / "network" / "dynamic-network.log"
    log_file.write_text(
        (
            f"{timestamp} core-sw01.example.local "
            "%PLATFORM-2-PS_FAIL: Power supply 2 failed or removed\n"
        ),
        encoding="utf-8",
    )

    answer = answer_or_execute_chat(
        settings,
        "hãy report tại giao diện chat",
        dry_run=False,
        channel="test-inline-report",
    )
    normalized = normalize_text(answer)

    assert "khong tao pdf" in normalized
    assert "khong gui gmail" in normalized
    assert "Power supply 2 failed or removed" in answer
    assert list(settings.report_output_dir.glob("*.pdf")) == []


def test_report_chat_followup_uses_previous_context_without_new_delivery(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log_file = settings.log_root_path / "network" / "dynamic-network.log"
    log_file.write_text(
        (
            f"{timestamp} core-sw01.example.local "
            "%PLATFORM-2-PS_FAIL: Power supply 2 failed or removed\n"
        ),
        encoding="utf-8",
    )

    first = answer_or_execute_chat(
        settings,
        "xuất PDF report 24 giờ qua",
        dry_run=False,
        channel="test-report-followup",
    )
    pdfs_after_first = list(settings.report_output_dir.glob("*.pdf"))
    second = answer_or_execute_chat(
        settings,
        "hãy report ở giao diện chat",
        dry_run=False,
        channel="test-report-followup",
    )
    normalized_second = normalize_text(second)

    assert "- File:" in first
    assert len(pdfs_after_first) == 1
    assert list(settings.report_output_dir.glob("*.pdf")) == pdfs_after_first
    assert "cau noi tiep" in normalized_second
    assert "khong tao pdf moi" in normalized_second
    assert "khong gui gmail" in normalized_second
    assert "Power supply 2 failed or removed" in second


def test_command_explanation_does_not_generate_runbook(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log_file = settings.log_root_path / "windows" / "dynamic-windows.log"
    log_file.write_text(
        (
            f"{timestamp} WIN-DB01.example.local "
            'System EventID=7031 Level=Critical Source=Service Control Manager '
            'Message="The SQLAgent service terminated unexpectedly. It has done this 3 time(s)"\n'
        ),
        encoding="utf-8",
    )

    answer = answer_or_execute_chat(
        settings,
        'tôi không hiểu lệnh này dùng để làm gì hay giải thích ý nghĩa "Get-Service SQLAgent"',
        dry_run=False,
        channel="test-command-explain",
    )
    normalized = normalize_text(answer)

    assert "giai thich command" in normalized
    assert "windows service" in normalized
    assert "running" in normalized
    assert "runbook command de xuat" not in normalized
    assert "restart-service sqlagent" not in normalized


def test_runtime_storage_prepares_self_contained_agentbase_folders(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    _prepare_runtime_storage(settings)

    assert settings.log_root_path.is_dir()
    assert settings.report_output_dir.is_dir()
    assert settings.state_db_path.parent.is_dir()
    for domain in DOMAINS:
        assert (settings.log_root_path / domain).is_dir()


def test_log_generator_supports_enterprise_source_families(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    expected_domains = {
        "fortigate",
        "juniper",
        "aruba",
        "linux",
        "windows",
        "vmware",
        "checkmk",
        "cacti",
        "prometheus",
        "grafana",
        "elk",
        "wazuh",
        "syslog",
    }

    for domain in expected_domains:
        generated = generate_one_log_line(settings.log_root_path, domain=domain, severity="critical")
        assert generated.domain == domain
        assert generated.path.parent.name == domain

    events = parse_raw_lines(list(iter_log_lines(settings.log_root_path)))
    domains = {event.domain for event in events}

    assert expected_domains <= set(DOMAINS)
    assert expected_domains <= domains
    assert all(event.severity == "critical" for event in events)
    assert all(event.event_type != "unknown_general_event" for event in events)


def test_runtime_status_summarizes_recent_alerts(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log_file = settings.log_root_path / "network" / "dynamic-network.log"
    log_file.write_text(
        (
            f"{timestamp} core-sw01.example.local "
            "%PLATFORM-2-PS_FAIL: Power supply 2 failed or removed\n"
        ),
        encoding="utf-8",
    )

    status = _build_status(settings)

    assert status["status"] == "ok"
    assert status["raw_lines"] == 1
    assert status["parsed_events"] == 1
    assert status["severity_counts"]["critical"] == 1
    assert status["domain_counts"]["network"] == 1
    assert status["top_alerts"][0]["event_type"] == "power_supply_failure"


def test_runtime_status_does_not_expose_telegram_alert_counters(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)

    status = _build_status(settings)

    assert "telegram_alert_metrics" not in status
    assert "telegram_update_pipeline" not in status


def test_rca_synthetic_generator_covers_required_scenarios() -> None:
    scenarios = list_scenarios()

    assert len(scenarios) == 10
    assert "broadcast_loop" in scenarios
    assert "brute_force_wazuh" in scenarios


def test_rca_analyzer_identifies_broadcast_loop_root_cause() -> None:
    incident = generate_incident("broadcast_loop")

    analysis = analyze_incident(incident)

    assert analysis["incident_id"] == incident["incident_id"]
    assert analysis["status"] == "confirmed"
    assert analysis["confidence"] >= 80
    assert "Broadcast loop" in analysis["most_likely_root_cause"]
    assert analysis["timeline"][0]["type"] == "change"
    assert any("MAC flapping" in item for item in analysis["evidence"])


def test_rca_store_latest_round_trip(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    store = RcaIncidentStore(settings.state_db_path)
    incident = generate_incident("linux_disk_full")
    analysis = analyze_incident(incident)

    store.save(incident, analysis)
    latest = store.latest()

    assert latest is not None
    assert latest["incident"]["incident_id"] == incident["incident_id"]
    assert latest["analysis"]["most_likely_root_cause"] == analysis["most_likely_root_cause"]


def test_rca_chat_request_returns_structured_brief(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)

    answer = answer_or_execute_chat(settings, "synthetic json RCA broadcast loop", dry_run=True)

    assert "AIOps RCA Investigation" in answer
    assert "Root cause:" in answer
    assert "RCA investigation answers" not in answer
    assert "Broadcast loop" in answer
    assert RcaIncidentStore(settings.state_db_path).latest() is not None


def test_rca_report_stays_compact_without_investigation_answers(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    generate_incident_log_lines(settings.log_root_path, "brute_force_wazuh")
    events = parse_raw_lines(list(iter_log_lines(settings.log_root_path)))
    analysis = analyze_log_events(
        events,
        lookback_hours=settings.report_lookback_hours,
        alert_levels=settings.severity_alert_levels,
        focus_text="ssh brute force from internet",
    )

    report = format_rca_report(analysis)
    telegram = format_rca_telegram(analysis)

    assert "AIOps RCA Investigation" in report
    assert "Root cause:" in report
    assert "| Field | Detail |" in report
    assert "| Root cause |" in report
    assert "| Impact |" in report
    assert "Event timeline:" in report
    assert "| Time | Role | Source | Event |" in report
    assert "Action plan:" in report
    assert "RCA investigation answers" not in report
    assert not any(f"**{index}." in report for index in range(1, 12))
    assert len(report.splitlines()) <= 55
    assert "Executive conclusion" not in report
    assert "Recommended actions:" not in report
    assert "<b>Root cause</b>" in telegram
    assert "<b>RCA investigation answers</b>" not in telegram
    assert "<b>Most Likely Root Cause</b>" not in telegram
    assert len(telegram.splitlines()) <= 30


def test_rca_runtime_helpers_generate_analyze_and_dry_run_telegram(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)

    generated = _generate_rca_incident(settings, {"scenario": "windows_service_crash"})
    analyzed = _analyze_rca_incident(settings, {"incident": generated["incident"]})
    telegram = _send_rca_telegram_test(settings, {"dry_run": True})

    assert generated["status"] == "ok"
    assert generated["analysis"]["confidence"] >= 70
    assert analyzed["analysis"]["incident_id"] == generated["incident"]["incident_id"]
    assert telegram["status"] == "dry_run"
    assert "AIOps RCA Alert" in telegram["message"]
    assert "<b>Most Likely Root Cause</b>" not in format_rca_telegram(generated["analysis"])
    assert "<b>RCA investigation answers</b>" not in format_rca_telegram(generated["analysis"])


def test_log_generator_creates_correlated_incident_logs_for_rca(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)

    generated = generate_incident_log_lines(settings.log_root_path, "broadcast_loop")
    events = parse_raw_lines(list(iter_log_lines(settings.log_root_path)))
    analysis = analyze_log_events(
        events,
        lookback_hours=settings.report_lookback_hours,
        alert_levels=settings.severity_alert_levels,
        focus_text="broadcast loop",
    )

    assert len(generated) >= 4
    assert analysis["source"] == "log_correlation"
    assert analysis["confidence"] >= 70
    assert analysis["status"] in {"need_verification", "confirmed"}
    assert analysis["correlated_events"] >= 3
    assert "LOG-RCA" in analysis["incident_id"]
    questions = {item["id"]: item for item in analysis["rca_questions"]}
    assert len(questions) == 11
    assert "Configured" in str(questions["root_candidate_event"]["answer"])
    assert "loopback" in str(questions["symptom_events"]["answer"]) or "flapping" in str(questions["symptom_events"]["answer"])


def test_auto_incident_generator_creates_all_incident_scenarios(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)

    result = _generate_all_incident_log_scenarios(settings)
    events = parse_raw_lines(list(iter_log_lines(settings.log_root_path)))

    assert result["scenario_count"] == len(INCIDENT_SCENARIOS)
    assert set(result["scenario_counts"]) == set(INCIDENT_SCENARIOS)
    assert result["generated_count"] >= len(INCIDENT_SCENARIOS) * 3
    assert len(events) == result["generated_count"]
    assert any(event.domain == "fortigate" for event in events)
    assert any(event.domain == "windows" for event in events)
    assert any(event.domain == "network" for event in events)


def test_log_rca_runtime_helper_generates_logs_then_analyzes(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)

    result = _generate_log_rca_incident(settings, {"scenario": "windows_service_crash"})
    current = _analyze_current_logs_for_rca(settings, {})
    status = _build_status(settings)

    assert result["status"] == "ok"
    assert result["generated_count"] >= 3
    assert result["analysis"]["source"] == "log_correlation"
    assert current["analysis"]["source"] == result["analysis"]["source"]
    assert current["analysis"]["anchor_event"]["source"] == result["analysis"]["anchor_event"]["source"]
    assert status["rca"]["log_analysis"]["anchor_event"]["source"] == result["analysis"]["anchor_event"]["source"]
    assert len(status["rca"]["log_analysis"]["rca_questions"]) == 11


def test_rca_chat_can_generate_incident_logs_before_analysis(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    noise_file = settings.log_root_path / "network" / "dynamic-network.log"
    noise_file.write_text(
        (
            "2026-06-14T10:00:00+07:00 core-sw-noise.example.local "
            "%PLATFORM-2-PS_FAIL: Power supply 2 failed or removed\n"
        ),
        encoding="utf-8",
    )

    answer = answer_or_execute_chat(
        settings,
        "sinh log su co broadcast loop roi phan tich RCA",
        dry_run=True,
    )

    assert "AIOps RCA Investigation" in answer
    assert "Scenario: `broadcast_loop`" in answer
    assert "loopback error" in answer or "BGP" in answer
    assert "power_supply_failure" not in answer
    assert "Power supply 2 failed" not in answer
    assert "Mode: RCA from current parsed logs." not in answer


def test_rca_command_requests_return_runbook_commands_not_full_rca(tmp_path: Path) -> None:
    cases = [
        ("broadcast_loop", "command de check RCA broadcast loop", "show interface"),
        ("mac_flapping", "command de check RCA mac flapping", "show mac address-table"),
        ("fortigate_session_spike", "command de check RCA Fortigate session spike", "diagnose sys session"),
        ("dns_timeout", "command de check RCA DNS timeout", "systemctl status named"),
        ("linux_disk_full", "command de check RCA linux disk full", "df -h"),
        ("windows_service_crash", "command de check RCA SQLAgent service down", "Get-Service"),
        ("vmware_datastore_full", "command de check RCA VMware datastore full snapshot", "Get-Datastore"),
        ("interface_flapping", "command de check RCA interface flapping", "show interface"),
        ("routing_issue", "command de check RCA routing payment subnet", "show ip bgp"),
        ("brute_force_wazuh", "command de check RCA SSH brute force attack", "alerts.log"),
    ]

    for scenario, question, expected_command in cases:
        settings = _settings(tmp_path / scenario)
        _prepare_runtime_storage(settings)
        generate_incident_log_lines(settings.log_root_path, scenario)

        answer = answer_or_execute_chat(settings, question, dry_run=True, channel=scenario)

        assert "command/check trong ngữ cảnh RCA" in answer
        assert "Runbook command" in answer
        assert expected_command in answer
        assert "AIOps RCA Investigation" not in answer
        assert "Event timeline:" not in answer
        assert RcaIncidentStore(settings.state_db_path).latest() is None


def test_log_rca_generator_api_analyzes_only_generated_incident_burst(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    noise_file = settings.log_root_path / "network" / "dynamic-network.log"
    noise_file.write_text(
        (
            "2026-06-14T10:00:00+07:00 core-sw-noise.example.local "
            "%PLATFORM-2-PS_FAIL: Power supply 2 failed or removed\n"
        ),
        encoding="utf-8",
    )

    result = _generate_log_rca_incident(settings, {"scenario": "broadcast_loop"})
    analysis = result["analysis"]
    event_types = {item["event"].split(":", 1)[0] for item in analysis["timeline"]}

    assert result["status"] == "ok"
    assert analysis["scope_label"] == "generated broadcast_loop incident burst"
    assert analysis["correlated_events"] >= 3
    assert "power_supply_failure" not in event_types
    assert any("loopback" in item["event"] or "mac_flapping" in item["event"] for item in analysis["timeline"])


def test_log_rca_generator_api_keeps_fortigate_scenario_isolated(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    noise_file = settings.log_root_path / "network" / "dynamic-network.log"
    noise_file.write_text(
        (
            "2026-06-14T10:00:00+07:00 core-rtr01.example.local "
            "%BGP-5-ADJCHANGE: neighbor 10.255.0.2 Down BGP Notification sent\n"
        ),
        encoding="utf-8",
    )

    result = _generate_log_rca_incident(settings, {"scenario": "fortigate_session_spike"})
    analysis = result["analysis"]
    timeline_text = " ".join(item["event"] for item in analysis["timeline"])
    evidence_text = " ".join(str(item) for item in analysis["evidence"])

    assert result["status"] == "ok"
    assert result["scenario"] == "fortigate_session_spike"
    assert analysis["scope_label"] == "generated fortigate_session_spike incident burst"
    assert "fortigate" in timeline_text.lower() or "fortigate" in evidence_text.lower()
    assert "Session table usage high" in timeline_text or "Session table usage high" in evidence_text
    assert "routing_neighbor_down" not in timeline_text
    assert "routing_neighbor_down" not in evidence_text


def test_rca_chat_diagnoses_when_user_reports_impact_without_rca_keyword(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    generate_incident_log_lines(settings.log_root_path, "windows_service_crash")

    answer = answer_or_execute_chat(
        settings,
        "user bao service SQLAgent down trong 1 gio qua, impact database job khong chay",
        dry_run=True,
    )

    assert "AIOps RCA Investigation" in answer
    assert "Root cause:" in answer
    assert "Event timeline:" in answer
    assert "RCA investigation answers" not in answer
    assert "Scope: `last 1h`" in answer
    assert "SQLAgent" in answer or "service_failure" in answer
    assert "deployed configuration update" in answer
    latest = RcaIncidentStore(settings.state_db_path).latest()
    assert latest is not None
    assert latest["analysis"]["focus_terms"]


def test_rca_chat_applies_llm_adjudication_when_available(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    generate_incident_log_lines(settings.log_root_path, "windows_service_crash")
    calls = {}

    def fake_adjudicator(settings, question, analysis):
        calls["question"] = question
        calls["incident_id"] = analysis["incident_id"]
        return {
            "verdict": "confirmed",
            "root_cause": "SQLAgent plugin deployment change is the most likely root cause before the service crash.",
            "confidence": 92,
            "rationale": ["The deployment event appears before the application crash and SQLAgent termination."],
            "missing_data": ["Windows service dependency status around the incident window."],
            "recommended_actions": ["Verify the plugin version and prepare a rollback if the crash repeats."],
        }

    monkeypatch.setattr("infra_log_sentinel.chat.responder.adjudicate_rca_with_llm", fake_adjudicator)

    answer = answer_or_execute_chat(
        settings,
        "user bao service SQLAgent down trong 1 gio qua, impact database job khong chay",
        dry_run=True,
    )
    latest = RcaIncidentStore(settings.state_db_path).latest()

    assert calls["incident_id"].startswith("LOG-RCA")
    assert "LLM review: `confirmed`" in answer
    assert "SQLAgent plugin deployment change" in answer
    assert latest is not None
    assert latest["analysis"]["llm_review"]["applied"] is True


def test_rca_chat_uses_llm_guidance_when_log_evidence_is_insufficient(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    called = {}

    def fake_guidance(**kwargs):
        called["analysis"] = kwargs["analysis"]
        return "## RCA chưa đủ dữ liệu\n- Kết luận: MiniMax chỉ gợi ý bước điều tra tiếp theo."

    monkeypatch.setattr(
        "infra_log_sentinel.chat.responder.suggest_rca_next_steps_with_llm",
        fake_guidance,
    )

    answer = answer_or_execute_chat(
        settings,
        "user bao app khong truy cap duoc trong 1 gio qua, impact user khong login duoc",
        dry_run=True,
    )

    assert "RCA chưa đủ dữ liệu" in answer
    assert "MiniMax chỉ gợi ý" in answer
    assert "LLM guidance:" in answer
    assert called["analysis"]["status"] == "insufficient_data"


def test_rca_panel_attaches_llm_guidance_when_focus_has_no_evidence(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    generate_incident_log_lines(settings.log_root_path, "vmware_datastore_full")
    called = {}

    def fake_guidance(**kwargs):
        called["analysis"] = kwargs["analysis"]
        return (
            "## LLM guidance: RCA chưa đủ dữ liệu\n"
            "- Kết luận: chưa thể xác nhận root cause cho impact mới lạ này.\n"
            "- Bước tiếp theo an toàn: thu thêm log đúng component bị impact."
        )

    monkeypatch.setattr("infra_log_sentinel.server.suggest_rca_next_steps_with_llm", fake_guidance)

    result = _analyze_current_logs_for_rca(
        settings,
        {
            "lookback_hours": 1,
            "impact": "unknown payment gateway brownout",
        },
    )
    analysis = result["analysis"]
    report = format_rca_report(analysis)

    assert result["status"] == "ok"
    assert analysis["status"] == "insufficient_data"
    assert "LLM guidance" in analysis["llm_guidance"]
    assert "impact mới lạ" in analysis["llm_guidance"]
    assert "LLM guidance:" in report
    assert called["analysis"]["incident_id"] == "LOG-RCA-FOCUS-NOT-FOUND"


def test_rca_panel_analysis_applies_llm_adjudication_when_available(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    generate_incident_log_lines(settings.log_root_path, "mac_flapping")

    monkeypatch.setattr(
        "infra_log_sentinel.server.adjudicate_rca_with_llm",
        lambda settings, question, analysis: {
            "verdict": "needs_verification",
            "root_cause": "Redundant uplink change is the leading candidate for MAC flapping.",
            "confidence": 82,
            "rationale": ["The config event and MAC flapping share the same switch and interface context."],
            "missing_data": ["STP topology-change counter on dist-sw02."],
            "recommended_actions": ["Check STP/LACP state on Gi2/0/21 before remediation."],
        },
    )

    result = _analyze_current_logs_for_rca(
        settings,
        {
            "lookback_hours": 1,
            "impact": "mac flaping",
        },
    )
    analysis = result["analysis"]

    assert result["status"] == "ok"
    assert analysis["llm_review"]["verdict"] == "needs_verification"
    assert "Redundant uplink change" in analysis["most_likely_root_cause"]
    assert any("LLM review" in item for item in analysis["evidence"])


def test_chat_context_can_be_reset_explicitly(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    channel = "test-new-chat"

    first = answer_or_execute_chat(
        settings,
        "sinh log su co broadcast loop roi phan tich RCA",
        dry_run=True,
        channel=channel,
    )
    reset = answer_or_execute_chat(settings, "new chat", dry_run=True, channel=channel)
    snapshot = ConversationStore(settings.state_db_path).get(channel)

    assert "AIOps RCA Investigation" in first
    assert "ngu canh hoi thoai moi" in normalize_text(reset)
    assert snapshot.last_action == "context_reset"
    assert snapshot.last_user_message == "new chat"


def test_chat_context_starts_new_investigation_when_topic_changes() -> None:
    snapshot = ConversationSnapshot(
        channel="web",
        last_user_message="phan tich RCA service SQLAgent down tren windows database",
        last_agent_message="old answer",
        last_intent="rca",
        last_action="rca",
        last_artifact_path="",
        updated_at_ts=1,
    )

    assert _should_start_new_investigation(
        "phan tich RCA wazuh brute force ssh tu internet",
        snapshot,
    )
    assert not _should_start_new_investigation(
        "can kiem tra them du lieu gi cho RCA nay",
        snapshot,
    )


def test_web_ui_moves_rca_workspace_to_right_rail_tabs() -> None:
    html = render_chat_ui("Infra Log Sentinel")
    conversation_start = html.index('<section class="conversation"')
    conversation_end = html.index("</section>", conversation_start)
    conversation_html = html[conversation_start:conversation_end]

    assert "rca-workspace" not in conversation_html
    assert 'data-rail-tab="sentinel"' in html
    assert 'data-rail-tab="rca"' in html
    assert "RCA lens" not in html
    assert html.count('id="rca-workspace-result"') == 1
    assert "rcaWorkspaceHasRun" in html
    assert "rcaWorkspaceAnalysis" in html
    assert "renderRcaWorkspaceAnalysis(state.rcaWorkspaceAnalysis)" in html
    assert 'id="rca-clear"' in html
    assert "clearRcaWorkspace" in html
    assert 'id="new-chat"' in html
    assert "startNewChatSession" in html
    assert "let conversationId = getConversationId();" in html
    assert 'id="quick-impact-select"' in html
    assert "quickImpactSelect" in html
    assert "VLAN 20 internet slow" in html
    assert 'id="rca-history-list"' in html
    assert "Impact / symptom + time" in html
    assert "RCA_HISTORY_KEY" in html
    assert "saveRcaHistory" in html
    assert "loadRcaHistory" in html
    assert "(entry && entry.impact) || analysis.impact" in html
    assert "analysis.most_likely_root_cause || analysis.summary || entry.impact" not in html
    assert "writeRcaHistory(history.slice(0, 5))" not in html
    assert "JSON.stringify(history.slice(0, 5))" in html
    assert 'data-prompt="user bao service SQLAgent down' not in html
    assert '<input id="rca-lookback" type="number" min="0.25" max="168" step="0.25">' in html
    assert '<input id="rca-start" type="datetime-local">' in html
    assert '<input id="rca-end" type="datetime-local">' in html
    assert 'id="rca-scenario"' not in html
    assert 'id="rca-generate"' not in html
    assert 'data-runtime-control="incident_generation"' in html
    assert 'id="control-incident-interval-input"' in html
    assert "All RCA incident scenarios" in html
    assert "Most Likely Root Cause" in html
    assert "<h4>Evidence</h4>" in html
    assert "<h4>Analyze</h4>" in html
    assert "<h4>Action</h4>" in html
    assert "Evidence & Action" not in html
    assert "grid-template-columns: 1fr" in html
    assert "rcaCommandCards" in html
    assert "Chưa có log evidence được chọn." in html
    assert "No log evidence selected yet." not in html


def test_log_rca_api_accepts_focus_and_lookback(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    generate_incident_log_lines(settings.log_root_path, "brute_force_wazuh")

    result = _analyze_current_logs_for_rca(
        settings,
        {
            "lookback_hours": 1,
            "impact": "ssh admin login failures from internet",
        },
    )

    assert result["status"] == "ok"
    assert result["analysis"]["source"] == "log_correlation"
    assert result["analysis"]["focus_terms"]
    assert result["analysis"]["confidence"] >= 70


def test_log_rca_current_logs_prioritizes_focus_over_unrelated_critical_events(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    generate_incident_log_lines(settings.log_root_path, "routing_issue")
    generate_incident_log_lines(settings.log_root_path, "fortigate_session_spike")

    result = _analyze_current_logs_for_rca(
        settings,
        {
            "lookback_hours": 1,
            "impact": "fortigate session spike",
        },
    )
    analysis = result["analysis"]
    timeline_text = " ".join(item["event"] for item in analysis["timeline"])
    evidence_text = " ".join(str(item) for item in analysis["evidence"])

    assert result["status"] == "ok"
    assert analysis["anchor_event"]["domain"] == "fortigate"
    assert "fortigate" in " ".join(item["source"] for item in analysis["timeline"]).lower()
    assert "Session table usage high" in timeline_text or "Session table usage high" in evidence_text
    assert "routing_neighbor_down" not in analysis["most_likely_root_cause"]
    assert "routing_neighbor_down" not in timeline_text


def test_log_rca_focus_correlation_blocks_same_domain_false_root_cause(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    generate_incident_log_lines(settings.log_root_path, "routing_issue")
    generate_incident_log_lines(settings.log_root_path, "mac_flapping")

    result = _analyze_current_logs_for_rca(
        settings,
        {
            "lookback_hours": 1,
            "impact": "mac flaping",
        },
    )
    analysis = result["analysis"]
    timeline_text = " ".join(item["event"] for item in analysis["timeline"])
    evidence_text = " ".join(str(item) for item in analysis["evidence"])
    root_text = analysis["most_likely_root_cause"]

    assert result["status"] == "ok"
    assert analysis["anchor_event"]["event_type"] == "mac_flapping"
    assert "mac_flapping" in timeline_text or "mac_flapping" in root_text
    assert "dist-sw02.example.local" in timeline_text or "dist-sw02.example.local" in root_text
    assert "routing_neighbor_down" not in root_text
    assert "routing_neighbor_down" not in timeline_text
    assert "Configured BGP export policy" not in root_text
    assert "Configured BGP export policy" not in evidence_text


def test_log_rca_focus_miss_does_not_fallback_to_unrelated_incident(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    generate_incident_log_lines(settings.log_root_path, "vmware_datastore_full")

    result = _analyze_current_logs_for_rca(
        settings,
        {
            "lookback_hours": 1,
            "impact": "mac flaping",
        },
    )
    analysis = result["analysis"]

    assert result["status"] == "ok"
    assert analysis["status"] == "insufficient_data"
    assert analysis["incident_id"] == "LOG-RCA-FOCUS-NOT-FOUND"
    assert analysis["analyzed_events"] > 0
    assert analysis["correlated_events"] == 0
    assert "vm_unexpected_poweroff" not in analysis["most_likely_root_cause"]


def test_log_rca_timeline_excludes_same_domain_noise_without_focus(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    generate_incident_log_lines(settings.log_root_path, "dns_timeout")
    log_file = settings.log_root_path / "linux" / "dynamic-linux.log"
    base = datetime.now(timezone.utc).astimezone().replace(microsecond=0)
    stamp = base.strftime("%b %d %H:%M:%S")
    lines = [
        f"{stamp} linux-web01.example.local sshd[1842]: Failed password for invalid user admin from 203.0.113.79 port 51520 ssh2",
        f"{stamp} linux-web02.example.local kernel: TCP: request_sock_TCP: Possible SYN flooding on port 443. Sending cookies.",
        f"{stamp} syslog01.example.local app-worker[2410]: job-runner.service failed with result exit-code",
    ]
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    result = _analyze_current_logs_for_rca(settings, {"lookback_hours": 1, "impact": "dns timeout"})
    analysis = result["analysis"]
    timeline_text = " ".join(item["event"] for item in analysis["timeline"])

    assert result["status"] == "ok"
    assert analysis["anchor_event"]["event_type"] in {"dns_timeout", "application_timeout"}
    assert "DNS query timeout" in timeline_text
    assert "named.service zone configuration update" in timeline_text
    assert "authentication_failure" not in timeline_text
    assert "possible_syn_flood" not in timeline_text
    assert "job-runner.service failed" not in timeline_text


def test_log_rca_api_accepts_absolute_time_range(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)
    log_file = settings.log_root_path / "network" / "dynamic-network.log"
    log_file.write_text(
        "\n".join(
            [
                "2026-06-14T10:00:00+07:00 old-sw.example.local %PLATFORM-2-PS_FAIL: Power supply 2 failed or removed",
                "2026-06-14T10:10:00+07:00 core-sw01.example.local %SYS-5-CONFIG_I: Configured temporary uplink Gi1/0/48",
                "2026-06-14T10:11:00+07:00 access-sw07.example.local %PM-4-ERR_DISABLE: loopback error detected on Gi1/0/48, putting Gi1/0/48 in err-disable state",
                "2026-06-14T11:00:00+07:00 late-sw.example.local %PLATFORM-2-PS_FAIL: Power supply 1 failed or removed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = _analyze_current_logs_for_rca(
        settings,
        {
            "start_time": "2026-06-14T10:05",
            "end_time": "2026-06-14T10:20",
            "impact": "loop on access port",
        },
    )
    analysis = result["analysis"]
    timeline_text = " ".join(item["event"] for item in analysis["timeline"])

    assert result["status"] == "ok"
    assert analysis["analyzed_events"] == 2
    assert "from 10:05:00 14/06/2026 to 10:20:00 14/06/2026" in analysis["scope_label"]
    assert "loopback" in timeline_text
    assert "Power supply" not in timeline_text


def test_runtime_status_exposes_telegram_delivery_state(tmp_path: Path) -> None:
    settings = replace(
        _settings(tmp_path),
        telegram_bot_token="123456:realish-token-for-test",
        telegram_chat_id="1234567890",
        runtime_scheduler_enabled=False,
        runtime_scheduler_dry_run=True,
    )
    _prepare_runtime_storage(settings)

    status = _build_status(settings)
    delivery = status["delivery"]["telegram_alerts"]

    assert delivery["state"] == "disabled"
    assert delivery["scheduler_enabled"] is False
    assert delivery["dry_run"] is True
    assert delivery["configured"] is True


def test_delivery_status_reports_scheduler_worker_down(tmp_path: Path) -> None:
    settings = replace(
        _settings(tmp_path),
        telegram_bot_token="123456:realish-token-for-test",
        telegram_chat_id="1234567890",
        runtime_scheduler_enabled=True,
        runtime_scheduler_dry_run=False,
    )
    runtime_controls = {
        "pauses": {
            CONTROL_TELEGRAM_ALERTS: {
                "paused": False,
                "paused_until": None,
                "manual_off": False,
            }
        }
    }

    delivery = _delivery_status(
        settings,
        runtime_controls,
        {"runtime_scheduler": {"state": "stopped", "detail": "boom"}},
    )["telegram_alerts"]

    assert delivery["state"] == "worker_down"
    assert delivery["label"] == "worker down"
    assert delivery["scheduler_worker_state"] == "stopped"


def test_control_status_distinguishes_pause_from_telegram_delivery(tmp_path: Path) -> None:
    settings = replace(
        _settings(tmp_path),
        telegram_bot_token="123456:realish-token-for-test",
        telegram_chat_id="1234567890",
        runtime_scheduler_enabled=False,
        runtime_scheduler_dry_run=True,
    )

    result = try_execute_chat_action(
        settings=settings,
        events=[],
        question="trang thai control",
        dry_run=False,
    )

    assert result.handled is True
    assert "telegram_alert_pause:" in result.message
    assert "telegram_alert_delivery: disabled" in result.message
    assert "scheduler_worker: disabled" in result.message
    assert "delivery_mode: dry_run" in result.message


def test_scheduler_job_errors_are_logged_without_raising(monkeypatch) -> None:
    messages = []
    monkeypatch.setattr(
        "infra_log_sentinel.scheduler.runner._print_job_result",
        lambda message: messages.append(message),
    )
    monkeypatch.setattr(
        "infra_log_sentinel.scheduler.runner.traceback.print_exc",
        lambda: None,
    )

    _run_job_safely(
        "Alert scan job",
        lambda: (_ for _ in ()).throw(RuntimeError("telegram 409")),
    )

    assert messages == ["Alert scan job failed: RuntimeError: telegram 409"]


def test_daily_report_schedule_uses_configured_timezone(monkeypatch) -> None:
    captured = {}

    class FakeJob:
        @property
        def day(self):
            return self

        def at(self, report_time, timezone_name=None):
            captured["report_time"] = report_time
            captured["timezone_name"] = timezone_name
            return self

        def do(self, job):
            captured["job"] = job
            return self

        def tag(self, tag_name):
            captured["tag"] = tag_name
            return self

    class FakeSchedule:
        def every(self):
            return FakeJob()

    monkeypatch.setattr("infra_log_sentinel.scheduler.runner.schedule", FakeSchedule())

    _schedule_daily_report_job("09:00", "Asia/Ho_Chi_Minh", lambda: "ok")

    assert captured["report_time"] == "09:00"
    assert captured["timezone_name"] == "Asia/Ho_Chi_Minh"
    assert captured["tag"] == "daily-report"


def test_runtime_control_api_toggles_alerts_and_saves_interval(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _prepare_runtime_storage(settings)

    off_result = _update_runtime_control(
        settings,
        {"control": CONTROL_TELEGRAM_ALERTS, "enabled": False},
    )
    telegram_pause = off_result["status"]["runtime_controls"]["pauses"][CONTROL_TELEGRAM_ALERTS]

    assert telegram_pause["paused"] is True
    assert telegram_pause["manual_off"] is True
    assert "disabled until it is enabled again" in off_result["message"]

    on_result = _update_runtime_control(
        settings,
        {"control": CONTROL_TELEGRAM_ALERTS, "enabled": True},
    )
    telegram_pause = on_result["status"]["runtime_controls"]["pauses"][CONTROL_TELEGRAM_ALERTS]

    assert telegram_pause["paused"] is False
    assert telegram_pause["manual_off"] is False

    interval_result = _update_runtime_control(
        settings,
        {"setting": VALUE_DEMO_LOG_INTERVAL_SECONDS, "seconds": 17},
    )

    assert interval_result["message"] == "Generator interval saved: 17s."
    assert RuntimeControlStore(settings.state_db_path).get_value(VALUE_DEMO_LOG_INTERVAL_SECONDS) == "17"

    incident_off = _update_runtime_control(
        settings,
        {"control": CONTROL_INCIDENT_GENERATION, "enabled": False},
    )
    incident_pause = incident_off["status"]["runtime_controls"]["pauses"][CONTROL_INCIDENT_GENERATION]
    assert incident_pause["paused"] is True
    assert incident_pause["manual_off"] is True

    incident_interval = _update_runtime_control(
        settings,
        {"setting": VALUE_INCIDENT_LOG_INTERVAL_SECONDS, "seconds": 240},
    )

    assert incident_interval["message"] == "Incident generator interval saved: 240s."
    assert RuntimeControlStore(settings.state_db_path).get_value(VALUE_INCIDENT_LOG_INTERVAL_SECONDS) == "240"

    report_time = _update_runtime_control(
        settings,
        {"setting": VALUE_REPORT_TIME, "value": "18:30"},
    )
    assert report_time["message"] == "Report time saved: 18:30."
    assert report_time["status"]["config"]["report_time"] == "18:30"
    assert RuntimeControlStore(settings.state_db_path).get_value(VALUE_REPORT_TIME) == "18:30"

    scan_interval = _update_runtime_control(
        settings,
        {"setting": VALUE_SCAN_INTERVAL_SECONDS, "seconds": 45},
    )
    assert scan_interval["message"] == "Scan interval saved: 45s."
    assert scan_interval["status"]["config"]["scan_interval_seconds"] == 45
    assert RuntimeControlStore(settings.state_db_path).get_value(VALUE_SCAN_INTERVAL_SECONDS) == "45"


def test_runtime_extracts_last_chat_message() -> None:
    question = _extract_question(
        {
            "messages": [
                {"role": "system", "content": "ignore system setup"},
                {"role": "user", "content": "tom tat log hom nay"},
            ]
        }
    )

    assert question == "tom tat log hom nay"


def test_telegram_chat_ack_is_handled_as_regular_message(tmp_path: Path, monkeypatch) -> None:
    settings = _settings(tmp_path)
    alert_store = AlertStore(settings.state_db_path)
    alert_id = alert_store.upsert_pending_alert(
        event=_log_event(),
        telegram_message_id=10,
        sent_at_ts=205,
        due_at_ts=400,
    )
    sent_messages = []
    responder_calls = []

    monkeypatch.setattr(
        "infra_log_sentinel.notifications.telegram_chat.send_telegram_message",
        lambda settings, text, parse_mode=None: sent_messages.append((text, parse_mode)) or 123,
    )

    result = process_telegram_chat_updates(
        settings=settings,
        alert_store=alert_store,
        updates=[TelegramUpdate(update_id=20, message_date_ts=200, text="ACK")],
        responder=lambda question: responder_calls.append(question) or "answer",
        dry_run=False,
    )

    assert result.processed_count == 1
    assert result.answered_count == 1
    assert alert_store.get_alert_status(alert_id) == "pending"
    assert alert_store.get_chat_update_id() == 20
    assert responder_calls == ["ACK"]
    assert len(sent_messages) == 1
    assert "INFRA-LOG-SENTINEL" in sent_messages[0][0]
    assert "answer" in sent_messages[0][0]
    assert sent_messages[0][1] == "HTML"


def test_telegram_chat_question_sends_responder_answer_and_advances_cursor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = _settings(tmp_path)
    alert_store = AlertStore(settings.state_db_path)
    sent_messages = []

    monkeypatch.setattr(
        "infra_log_sentinel.notifications.telegram_chat.send_telegram_message",
        lambda settings, text, parse_mode=None: sent_messages.append((text, parse_mode)) or 123,
    )

    result = process_telegram_chat_updates(
        settings=settings,
        alert_store=alert_store,
        updates=[TelegramUpdate(update_id=21, message_date_ts=200, text="tom tat log hom nay")],
        responder=lambda question: f"answer for: {question}",
        dry_run=False,
    )

    assert result.processed_count == 1
    assert result.answered_count == 1
    assert alert_store.get_chat_update_id() == 21
    assert len(sent_messages) == 1
    assert "INFRA-LOG-SENTINEL" in sent_messages[0][0]
    assert "answer for: tom tat log hom nay" in sent_messages[0][0]
    assert sent_messages[0][1] == "HTML"


def test_telegram_alert_message_is_one_way_without_ack_prompt() -> None:
    message = format_alert_message(_log_event(), index=1, total=1, alert_id="ALS-TEST")

    assert "ALS-TEST" in message
    assert "Reply <b>ACK</b>" not in message
    assert "escalation timeout" not in message


def test_telegram_summary_formatter_adds_professional_sections() -> None:
    answer = "\n".join(
        [
            "Tóm tắt theo câu hỏi",
            "- Tổng số event phù hợp: 46",
            "- Theo severity: {'critical': 13, 'error': 16, 'warning': 17}",
            "- Theo domain: {'linux': 10, 'network': 13, 'vmware': 13, 'windows': 10}",
            "",
            "Top alert cần xem:",
            (
                "- [CRITICAL] network/core-rtr01.example.local routing_neighbor_down: "
                "%BGP-5-ADJCHANGE: neighbor 10.255.0.105 Down"
            ),
        ]
    )

    formatted = format_chat_reply_for_telegram("Tóm tắt log hôm nay", answer)

    assert "INFRA-LOG-SENTINEL" in formatted
    assert "Brief" in formatted
    assert "Overview" in formatted
    assert "Priority Findings" in formatted
    assert "Suggested Next Step" in formatted
    assert "🔴 CRITICAL" in formatted


def _log_event() -> LogEvent:
    return LogEvent(
        timestamp="2026-06-12T10:00:00Z",
        domain="network",
        source="core-sw01.example.local",
        severity="critical",
        event_type="power_supply_failure",
        message="Power supply 2 failed or removed",
        raw="raw",
        source_file=Path("network-sample.log"),
        line_number=1,
        probable_cause="Power module failure",
        impact="Redundancy degraded",
        recommended_action="Replace the failed PSU",
    )
