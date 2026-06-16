# AgentBase Runtime Readiness

## Step 13 status

Completed:

- Added `infra_log_sentinel.server` runtime wrapper.
- Added `GET /health`, `GET /status`, `POST /invocations`, and `POST /chat`.
- Added `Dockerfile` with `EXPOSE 8080` and `CMD ["python", "-m", "infra_log_sentinel.server"]`.
- Added `.dockerignore` to keep `.env`, `.greennode.json`, credentials, runtime data, reports, and git metadata out of the image.
- Verified `python -m compileall infra_log_sentinel`.
- Verified local runtime API:
  - `GET /health` returned HTTP 200.
  - `GET /status` returned HTTP 200.
  - `POST /invocations` returned HTTP 200.

## Step 14 status

Completed:

- Built Docker image:
  - Image: `infra-log-sentinel-agent:test`
  - Platform: `linux/amd64`
- Started a local container from the image.
- Copied demo logs into `/app/data/logs` inside the container.
- Verified container runtime API:
  - `GET /health` returned HTTP 200.
  - `GET /status` returned HTTP 200.
  - `POST /invocations` returned HTTP 200.
- Verification counts:
  - Raw lines: 56
  - Parsed events: 56
  - Report window events: 54
- Removed the temporary test container after validation.

Note: mounting the Google Drive virtual path directly into Docker returned an empty folder on this workstation. For local Docker testing, use `docker cp` or a normal host folder that Docker Desktop can mount reliably.

## Step 15 status

Completed:

- Added self-contained runtime folder mode:
  - `LOG_SOURCE_MODE=runtime_folder`
  - `LOG_ROOT_PATH=/app/data/logs`
- Runtime now creates the log, report, and state directories on startup.
- Runtime creates domain folders when `LOG_SOURCE_MODE=runtime_folder`:
  - `network`
  - `linux`
  - `windows`
  - `vmware`
- Added bootstrap log generation:
  - `RUNTIME_LOG_BOOTSTRAP_ENABLED`
  - `DEMO_LOG_BOOTSTRAP_COUNT`
- Added background demo log generator:
  - `DEMO_LOG_GENERATOR_ENABLED`
  - `DEMO_LOG_INTERVAL_SECONDS`
  - `DEMO_LOG_DOMAIN`
  - `DEMO_LOG_SEVERITY`
- Added optional runtime scheduler flags:
  - `RUNTIME_SCHEDULER_ENABLED`
  - `RUNTIME_SCHEDULER_DRY_RUN`
  - `RUNTIME_SCHEDULER_MAX_ALERTS`
  - `RUNTIME_SCHEDULER_MAX_ESCALATIONS`
- Added optional Telegram chat bridge flags:
  - `TELEGRAM_CHAT_ENABLED`
  - `TELEGRAM_CHAT_POLL_INTERVAL_SECONDS`
  - `TELEGRAM_CHAT_DRY_RUN`
- Docker image defaults now support a self-contained GreenNode demo:
  - Bootstraps 16 synthetic logs if the runtime log folder is empty.
  - Appends one abnormal synthetic log every 30 seconds.
  - Keeps scheduler disabled by default to avoid accidental Gmail/Telegram delivery.

Verified:

- Local runtime self-contained test:
  - `GET /health` returned HTTP 200.
  - `GET /status` returned HTTP 200.
  - Raw lines increased from 10 to 13 as the generator ran.
  - `POST /invocations` returned HTTP 200.
- Docker runtime self-contained test:
  - No host log mount.
  - No `docker cp`.
  - `GET /health` returned HTTP 200.
  - Raw lines increased from 17 to 18 as the generator ran.
  - `POST /invocations` returned HTTP 200.

## Step 16 safety controls

Completed:

- Added runtime control state in SQLite.
- Runtime control uses `APP_TIMEZONE` for pause timestamps; Docker defaults to `Asia/Ho_Chi_Minh`.
- Chat can pause/resume Telegram alerts.
- Chat can pause/resume scheduled Gmail reports.
- Chat can pause/resume auto log generation.
- Chat can update auto log generation interval while the runtime is running.
- Scheduler respects pause state:
  - When Telegram alerts are paused, realtime alert scans consume the cursor without sending Telegram messages, avoiding alert backlog after resume.
  - When Gmail reports are paused, daily report email is skipped.
- Chat Gmail report action respects Gmail report pause state.
- `/status` includes `runtime_controls`.

Verified:

- CLI chat control status works.
- CLI chat pause alert/report works.
- Scheduler dry-run skips report and alert delivery while paused.
- CLI chat Gmail action is blocked while report pause is active.
- Runtime API can pause auto log generation and resume it without restart.
- Runtime API can update generator interval without restart.

Example chat commands:

```text
trang thai control
tam dung alert va report trong 30 phut
tam dung alert va report den 17:30
tam ngung sinh log trong 10 phut
tam ngung sinh log den 17:30
doi interval sinh log 120 giay
bat lai alert
bat lai report
bat lai sinh log
bat lai tat ca
```

## Step 17 hosted submission runtime

Completed:

- Deployed GreenNode AgentBase runtime:
  - Runtime ID: `runtime-a864917b-1a16-4083-a64c-82f4e79f6602`
  - Endpoint: `https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9.agentbase-runtime.aiplatform.vngcloud.vn`
  - Image: `vcr.vngcloud.vn/111480-abp111815/infra-log-sentinel-agent:v20260616-ui-history-layout-v41`
  - Image digest: `sha256:279134c8fc3d7c521e16e36cc78df56b0c2e586cd5330b50535cbfd2c9276ffa`
  - Endpoint version: `39`
  - Runtime status: `ACTIVE`
  - Endpoint status: `ACTIVE`
  - Current replicas: `1`
- Added Telegram chat bridge for operator questions through Telegram.
- Hardened agent chat logic:
  - Intent routing separates operational questions, report requests, runtime controls, command explanations, and assistant-feedback corrections.
  - Follow-up questions use conversation state instead of being treated as unrelated one-line commands.
  - Requests like "report in chat UI" return inline summaries instead of sending Gmail by default.
- Added professional web UI for the hosted demo:
  - Focused chat console.
  - Priority queue.
  - Runtime controls.
  - Telegram alert delivery state.
  - RCA workspace for impact/window/scenario-driven diagnosis.
- Added Telegram delivery reliability:
  - Alert scan job exception isolation.
- Telegram alerts are one-way notifications; ACK/escalation and alert counter cards are retired.

Verified after v41 deployment on 2026-06-16:

- `GET /health` returned `ok`.
- `GET /status` returned `ok` in `runtime_folder` mode.
- Hosted RCA insufficient-data smoke returned `LOG-RCA-FOCUS-NOT-FOUND`, `insufficient_data`, and `llm_guidance=true`.
- Hosted UI serves the Log & RCA chat workspace with Chat Agent Recents under Quick action, Quick action and Quick impact dropdowns, RCA Recent history inside the RCA tab, aligned Chat Agent/RCA side-panel spacing, editable report time, editable scan interval, and vertical RCA result blocks: Most Likely Root Cause, Evidence, Analyze, Action.
- RCA chat intent routing distinguishes full RCA analysis requests from RCA command/check/runbook requests across all generated RCA cases; command/check questions return runbook commands instead of full RCA reports.
- RCA output uses Vietnamese explanatory text while preserving log identifiers, event types, commands, and technical terms in English.
- RCA Action includes detailed command cards for log inspection, service checks, and platform-specific validation.
- Daily report scheduler registers `REPORT_TIME` in `Asia/Ho_Chi_Minh` instead of container UTC.
- Telegram alert delivery is controlled by the Runtime Controls panel and can be toggled live before a realtime alert demo.
- Hosted UI exposes separate right-panel `Log Sentinel` and `RCA` tabs.
- RCA workspace no longer occupies the chat conversation space.
- Runtime UI exposes `New chat` context reset and RCA workspace `Clear`.
- Runtime RCA/chat smoke returned a compact RCA brief with 11 investigation answers.
- Runtime UI exposes an `Incident generator` runtime control with editable all-scenario incident interval.
- RCA workspace now analyzes current logs only; incident generation is controlled from Runtime Controls.
- RCA current-log analysis now prioritizes the user-provided symptom/focus before unrelated critical events.
- RCA workspace keeps the user's latest focused analysis in browser state so `/status` refreshes cannot overwrite it.
- Runtime container regression suite passed locally: `52 passed`.

## Runtime contract

GreenNode AgentBase Custom Agent requires:

- Container listens on port `8080`.
- `GET /health` returns HTTP 200.

The platform does not require `POST /invocations`, but this project exposes it for a clear chat/action demo endpoint.

## Local commands

Start the runtime:

```powershell
cd "G:\My Drive\8. VNG\07.PYCODE\VNG\AGENT\infra-log-sentinel-agent"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.server
```

Test health:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -UseBasicParsing
```

Test chat/action API:

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8080/invocations" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"message":"tom tat log hom nay"}' `
  -UseBasicParsing
```

Build Docker image:

```powershell
docker build --platform linux/amd64 -t infra-log-sentinel-agent:test .
```

Run Docker image:

```powershell
docker run --rm -p 8080:8080 --env-file .env infra-log-sentinel-agent:test
```

Run the self-contained Docker demo without Google Drive, mount, or copied logs:

```powershell
docker run --rm -p 8080:8080 infra-log-sentinel-agent:test
```

The image defaults create `/app/data/logs`, bootstrap synthetic logs, and append a new abnormal log every 30 seconds.

Enable Telegram chat after bot token and chat ID are configured:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --init-telegram-chat
docker run --rm -p 8080:8080 --env-file .env `
  -e TELEGRAM_CHAT_ENABLED=true `
  infra-log-sentinel-agent:test
```

The bridge uses polling with its Telegram chat cursor, so initialize the cursor before a live demo if the bot has old queued messages.

Enable autonomous scheduler delivery only when Gmail and Telegram env vars are ready:

```powershell
docker run --rm -p 8080:8080 --env-file .env `
  -e LOG_SOURCE_MODE=runtime_folder `
  -e LOG_ROOT_PATH=/app/data/logs `
  -e RUNTIME_LOG_BOOTSTRAP_ENABLED=true `
  -e DEMO_LOG_GENERATOR_ENABLED=true `
  -e RUNTIME_SCHEDULER_ENABLED=true `
  -e RUNTIME_SCHEDULER_DRY_RUN=false `
  infra-log-sentinel-agent:test
```

If Docker Desktop cannot mount the Google Drive path, copy logs into the running container for validation:

```powershell
docker run -d --name infra-log-sentinel-agent-test -p 8080:8080 `
  -e LOG_ROOT_PATH=/app/data/logs `
  -e REPORT_OUTPUT_DIR=/app/reports `
  -e STATE_DB_PATH=/app/state/infra_log_sentinel.sqlite `
  infra-log-sentinel-agent:test

docker cp "G:\My Drive\8. VNG\07.PYCODE\VNG\AGENT\infra-log-sentinel-demo\." `
  infra-log-sentinel-agent-test:/app/data/logs
```

## Important deployment note

The local Google Drive synced folder path `G:\...` does not exist in AgentBase cloud runtime.

For the contest demo, the current recommendation is self-contained runtime mode:

- `LOG_SOURCE_MODE=runtime_folder`
- `LOG_ROOT_PATH=/app/data/logs`
- `RUNTIME_LOG_BOOTSTRAP_ENABLED=true`
- `DEMO_LOG_GENERATOR_ENABLED=true`

Use `.env.greennode.example` as the template for the AgentBase runtime env file. Do not deploy the local `.env` unchanged if it still contains a Windows `G:\...` log path.

For production-style ingestion, choose one:

- Mount or copy logs into a container path and set `LOG_ROOT_PATH` to that path.
- Add Google Drive API ingestion so the deployed container can read the Drive folder directly.

Google Drive API ingestion is more realistic for external log storage, while runtime folder mode is simpler and more reliable for the competition demo.
