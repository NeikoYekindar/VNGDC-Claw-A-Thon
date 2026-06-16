# GreenNode Submission Packet

Last updated: 2026-06-16

## Project

Infrastructure Log Sentinel Agent is an AI operations copilot for infrastructure log intelligence. It reads infrastructure, security, monitoring, and observability logs, classifies severity, explains probable cause and impact, recommends runbook actions, sends realtime Telegram alerts, generates PDF reports, and exposes runtime controls plus an RCA workspace through a professional web chat console.

## Links

- Repository: `https://github.com/trangdm/infra-log-sentinel-agent`
- Hosted demo: `https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9.agentbase-runtime.aiplatform.vngcloud.vn`
- Health check: `https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9.agentbase-runtime.aiplatform.vngcloud.vn/health`
- Status API: `https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9.agentbase-runtime.aiplatform.vngcloud.vn/status`
- GreenNode submission page: `https://greennode.ai/events/greennode-claw-a-thon`
- Rulebook: `https://greennode.ai/claw-a-thon-rulebook`
- AgentBase skills: `https://github.com/vngcloud/greennode-agentbase-skills`

## Submission Form Answers

- Team name: `PENDING USER INPUT: fill registered team name`
- Track: `Agentic Assistant` (recommended for the chat/RCA copilot positioning)
- AgentBase project link / GitHub: `https://github.com/trangdm/infra-log-sentinel-agent`
- Running AgentBase demo link: `https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9.agentbase-runtime.aiplatform.vngcloud.vn`
- Demo video link: `PENDING USER INPUT: add 2-3 minute YouTube or OneDrive link shared for VNG domain`
- Department and members: `PENDING USER INPUT: fill 1-3 member names and accdomain@vng.com.vn emails`
- Team avatar: optional, square PNG/JPG at least 512x512 and under 5 MB

Short use case description for the form:

```text
Infrastructure Log Sentinel Agent is an AI operations copilot for infrastructure teams. It analyzes network, Linux, Windows, VMware, observability, and security logs from a self-contained AgentBase runtime, classifies severity, explains probable causes and impact, and recommends safe runbook actions. Operators can use the hosted web console to ask log questions, generate summaries, pause or resume runtime actions, and run RCA from current logs or generated incident bursts. The agent also supports Telegram alerts and Gmail PDF reporting, making routine incident triage faster and more consistent for NOC/SRE teams.
```

## Runtime

- GreenNode AgentBase runtime ID: `runtime-a864917b-1a16-4083-a64c-82f4e79f6602`
- Runtime image: `vcr.vngcloud.vn/111480-abp111815/infra-log-sentinel-agent:v20260616-ui-history-layout-v41`
- Runtime image digest: `sha256:279134c8fc3d7c521e16e36cc78df56b0c2e586cd5330b50535cbfd2c9276ffa`
- Endpoint version: `39`
- Runtime status: `ACTIVE`
- Endpoint status: `ACTIVE`
- Current replicas: `1`
- Runtime mode: `runtime_folder`
- Port: `8080`
- Required contract: `GET /health`
- Extra demo APIs: `GET /status`, `POST /chat`, `POST /invocations`, `POST /runtime-controls`, `POST /rca/logs/analyze`, `POST /rca/logs/generate`

## What To Demo

1. Open the hosted endpoint and show the web console.
2. Ask: `tom tat log hom nay`
3. Ask: `hay report o giao dien chat`
4. Ask: `toi khong hieu lenh nay dung de lam gi hay giai thich y nghia "Get-Service SQLAgent"`
5. Toggle runtime controls:
   - Telegram alerts on/off.
   - Gmail reports on/off.
   - Log generator on/off.
   - Edit generator interval and save.
6. Use the RCA workspace:
   - Enter an impact/symptom.
   - Choose a lookback window.
   - Analyze current logs; use Runtime Controls to generate incident logs when a fresh demo scenario is needed.
7. Trigger or wait for realtime Telegram alerts as one-way operational notifications.

## Key Capabilities

- Multi-source log parsing: Network, Fortigate, Juniper, Aruba, Linux Server, Windows Server, VMware, CheckMK, Cacti, Prometheus, Grafana, ELK, Wazuh, and syslog-style logs.
- Severity classification: info, warning, error, critical.
- Deterministic operational answers for log summaries, report requests, command explanations, and runtime controls.
- Conversation-aware chat logic so follow-up questions stay connected to prior context.
- Professional web UI with priority queue, status indicators, runtime controls, and RCA workspace.
- Telegram realtime alert delivery for warning/error/critical events.
- Gmail PDF report delivery with runtime pause control.
- Self-contained synthetic log generation for reliable hosted demo behavior.
- RCA analysis from current logs or generated incident bursts with confidence, evidence, focus terms, and recommended actions.

## Verification

Verified after deploying v41 on 2026-06-16:

- `/health`: `ok`
- `/status`: `ok`, runtime mode `runtime_folder`
- Hosted RCA insufficient-data smoke: `LOG-RCA-FOCUS-NOT-FOUND`, `insufficient_data`, `llm_guidance=true`
- Runtime control-plane status: runtime `ACTIVE`, endpoint `ACTIVE`, endpoint version `39`, replica count `1`
- Hosted UI: Chat Agent shows `Infrastructure Log & RCA Intelligence`, Recents chat history under Quick action, Quick action and Quick impact dropdowns, RCA Recent history inside the RCA tab showing Impact/symptom plus time, aligned Chat Agent/RCA side-panel spacing, editable report time, editable scan interval, and vertical RCA result blocks: Most Likely Root Cause, Evidence, Analyze, Action.
- RCA chat intent routing: full RCA analysis requests still return RCA reports, while RCA command/check/runbook requests return relevant runbook commands across all generated RCA scenarios.
- RCA output uses Vietnamese explanatory text while preserving log identifiers, event types, commands, and technical terms in English.
- RCA Action includes detailed command cards for log inspection, service checks, and platform-specific validation.
- Daily report scheduler registers `REPORT_TIME` in `Asia/Ho_Chi_Minh` instead of container UTC.
- Runtime timezone: `Asia/Ho_Chi_Minh`
- Telegram delivery: controlled from the Runtime Controls panel; enable it before the realtime Telegram alert demo.
- UI includes separate right-panel `Log Sentinel` and `RCA` tabs
- RCA workspace no longer occupies chat conversation space
- UI exposes `New chat` context reset and RCA workspace `Clear`
- Runtime RCA/chat smoke: compact RCA brief with 11 RCA answers, no duplicated legacy RCA sections
- Core regression tests: `53 passed`

## Pass / Fail Readiness

- AgentBase runtime deployed and accessible: PASS.
- At least one successful hosted request: PASS (`/health`, `/status`, and hosted UI smoke were verified).
- README/use case description present: PASS.
- Demo video 2-3 minutes and accessible by VNG account: PENDING USER INPUT.
- Team name, department, and member emails: PENDING USER INPUT.

## Security Notes

- `.env`, `.env.greennode`, `.greennode.json`, `.agentbase/`, tokens, runtime data, and generated reports are excluded from git and Docker build context.
- The repository contains examples/templates only; live credentials are not committed.
- The hosted runtime uses GreenNode environment variables for secrets.
