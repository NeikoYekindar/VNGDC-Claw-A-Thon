# Infrastructure Log Sentinel Agent

Infrastructure Log Sentinel Agent is a Claw-a-thon 2026 agent for analyzing raw infrastructure logs from a personal Google Drive folder. It supports Network, Windows, Linux, and VMware logs.

## MVP scope

- Read log files from a Google Drive synced local folder.
- Detect the log domain: network, windows, linux, or vmware.
- Parse raw lines into normalized events.
- Classify severity: info, warning, error, critical.
- Analyze summary, probable cause, impact, and recommended action.
- Send realtime Telegram alerts for new warning/error/critical log lines.
- Generate a daily 24-hour PDF report at 09:00 and send it through Gmail.
- Provide a web chat console for log questions, report actions, runtime controls, and runbook commands.
- Perform AIOps RCA on synthetic incidents with timeline, evidence, hypotheses, confidence scoring, safe actions, and Telegram-ready RCA output.

## Hosted demo

GreenNode AgentBase endpoint:

```text
https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9.agentbase-runtime.aiplatform.vngcloud.vn
```

The hosted demo runs in `runtime_folder` mode. It creates `/app/data/logs`, bootstraps sample infrastructure logs, and can generate new synthetic abnormal logs for realtime alert testing. The web console is optimized for desktop demo: chat stays fixed at the bottom, the priority queue scrolls internally, and the right-side runtime panels remain visible in one viewport.

## AIOps RCA MVP

The agent includes a deterministic RCA workflow that can analyze the current parsed logs or generate a correlated incident log burst first:

```text
Log generator incident burst -> Parser -> Timeline -> Correlation -> Root cause hypothesis -> Evidence -> Actions -> Telegram-ready RCA brief
```

Supported log-generator RCA scenarios:

- `broadcast_loop`
- `mac_flapping`
- `fortigate_session_spike`
- `dns_timeout`
- `linux_disk_full`
- `windows_service_crash`
- `vmware_datastore_full`
- `interface_flapping`
- `routing_issue`
- `brute_force_wazuh`

Example chat prompts:

```text
sinh log su co broadcast loop roi phan tich RCA
phan tich RCA tu log hien tai
gui RCA Telegram fortigate
synthetic json RCA broadcast loop
```

RCA API endpoints:

```text
POST /rca/logs/generate
POST /rca/logs/analyze
POST /demo/incidents/generate
POST /incidents/analyze
GET /incidents/latest
POST /telegram/test
```

Example:

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8080/rca/logs/generate" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"scenario":"broadcast_loop"}' `
  -UseBasicParsing
```

## Final submission snapshot

- Project: Infrastructure Log Sentinel Agent.
- Repository: `https://github.com/trangdm/infra-log-sentinel-agent`.
- GreenNode AgentBase runtime ID: `runtime-a864917b-1a16-4083-a64c-82f4e79f6602`.
- Hosted endpoint: `https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9.agentbase-runtime.aiplatform.vngcloud.vn`.
- Submitted runtime image: `vcr.vngcloud.vn/111480-abp111815/infra-log-sentinel-agent:v20260616-ui-history-layout-v41`.
- Submitted runtime image digest: `sha256:279134c8fc3d7c521e16e36cc78df56b0c2e586cd5330b50535cbfd2c9276ffa`.
- Endpoint version: `39`.
- Runtime mode: `runtime_folder`, self-contained synthetic infrastructure log demo.
- Verification on 2026-06-16: runtime `ACTIVE`, endpoint `ACTIVE`, endpoint version `39`, replica count `1`, `/health` returned `ok`, `/status` returned `ok` in `runtime_folder` mode, hosted UI served the Log & RCA chat workspace with Chat Agent Recents under Quick action, RCA Recent history inside the RCA tab, aligned Chat Agent/RCA side-panel spacing, vertical RCA result blocks, Vietnamese RCA output, and command details in Action; local regression suite passed with `53 passed`.

For the copy-ready GreenNode submission packet, see `docs/submission.md`.

## Local workspace

```text
G:\My Drive\8. VNG\07.PYCODE\VNG\AGENT
├── infra-log-sentinel-demo
├── infra-log-sentinel-agent
└── greennode-agentbase-skills
```

## Sample logs

Sample logs are stored in:

```text
samples/logs/network/network-sample.log
samples/logs/windows/windows-event-sample.log
samples/logs/linux/linux-syslog-sample.log
samples/logs/vmware/vmware-vcenter-sample.log
```

For the local MVP, copy or sync them to:

```text
G:\My Drive\8. VNG\07.PYCODE\VNG\AGENT\infra-log-sentinel-demo
```

## Configuration

Copy `.env.example` to `.env` and fill in local secrets. Do not commit `.env`.

```powershell
copy .env.example .env
```

Required for local demo:

- `LOG_ROOT_PATH`
- `REPORT_LOOKBACK_HOURS`
- `GMAIL_ADDRESS`
- `GMAIL_APP_PASSWORD`
- `REPORT_RECIPIENT_EMAIL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional Telegram chat bridge:

- `TELEGRAM_CHAT_ENABLED`
- `TELEGRAM_CHAT_POLL_INTERVAL_SECONDS`
- `TELEGRAM_CHAT_DRY_RUN`

Optional for GreenNode MaaS analysis:

- `LLM_API_BASE`
- `LLM_API_KEY`
- `LLM_MODEL`

## Run local smoke test

```powershell
python -m infra_log_sentinel.main
```

On this workstation, dependencies are installed in a local cache venv to avoid Google Drive sync overhead:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --scan
```

Run automated smoke tests:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m pytest -q
```

Generate a local PDF report:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --report
```

The PDF report uses the last `REPORT_LOOKBACK_HOURS` hours. The default is 24 hours.

Ask the agent a question about the parsed logs:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "Có critical network nào không và command xử lý là gì?"
```

Ask the agent to execute safe log actions:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "xuất báo cáo PDF 24 giờ gần nhất"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "export alert critical network ra file csv"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "kiểm tra có log mới bất thường không"
```

Send a report through Gmail from chat:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "gửi báo cáo hôm nay qua Gmail"
```

Preview the Gmail chat action without sending:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "gửi báo cáo hôm nay qua Gmail" --dry-run
```

Start interactive local log chat:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat
```

Runtime control chat examples:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "trang thai control"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "tam dung alert va report trong 30 phut"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "tam dung alert va report den 17:30"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "tam ngung sinh log trong 10 phut"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "doi interval sinh log 120 giay"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "bat lai alert"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "bat lai report"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --chat "bat lai sinh log"
```

Preview Gmail delivery without sending:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --email-report --dry-run
```

Send the PDF report through Gmail after `.env` has valid Gmail values:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --email-report
```

Preview Telegram alerts without sending:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --telegram-alerts --dry-run --max-alerts 3
```

Test Telegram connectivity and chat delivery:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --telegram-health
```

Chat with the agent through the configured Telegram chat:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --init-telegram-chat
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --telegram-chat
```

If the bridge was started in the background, check it with:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*infra_log_sentinel.main*' -and $_.CommandLine -like '*--telegram-chat*' }
```

Stop all matching bridge processes with:

```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*infra_log_sentinel.main*' -and $_.CommandLine -like '*--telegram-chat*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId }
```

Process one Telegram chat cycle for testing:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --telegram-chat-once --dry-run
```

When the bridge is running, send messages like `tom tat log hom nay`, `co critical network nao khong?`, or `command xu ly vmware warning` to the configured Telegram chat.

Telegram chat replies use the same HTML visual language as realtime alerts: severity/domain icons, bold labels, compact code values, priority findings, and suggested next steps.

Send a limited Telegram alert test:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --telegram-alerts --max-alerts 3
```

Telegram messages use severity/domain icons and HTML emphasis. Telegram does not support arbitrary colored text in native bot messages, so colored status icons are used for visual emphasis.

Baseline the current log folder before realtime alerting:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --init-log-cursor
```

Send Telegram alerts only for newly appended log lines:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --telegram-alerts --new-only --max-alerts 3
```

Send all warning/error/critical Telegram alerts from the folder for manual testing:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --telegram-alerts
```

Run one scheduler cycle safely without sending messages:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --scheduler-once --dry-run --max-alerts 3
```

Run one real scheduler cycle for local verification:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --scheduler-once --max-alerts 3
```

The scheduler uses the realtime cursor for alert scans. Run `--init-log-cursor` first if you want it to ignore existing historical log lines and alert only on newly appended log lines.

Start the local scheduler loop:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --scheduler
```

## Realtime simulation

Use two PowerShell terminals to verify realtime alerting with dynamic logs.

Terminal A - baseline existing logs, then start the scheduler:

```powershell
cd "G:\My Drive\8. VNG\07.PYCODE\VNG\AGENT\infra-log-sentinel-agent"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --init-log-cursor
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --scheduler
```

Terminal B - append synthetic abnormal logs over time:

```powershell
cd "G:\My Drive\8. VNG\07.PYCODE\VNG\AGENT\infra-log-sentinel-agent"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --generate-logs 10 --generate-log-interval 5 --generate-log-severity abnormal
```

Generate targeted test cases:

```powershell
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --generate-logs 1 --generate-log-domain network --generate-log-severity critical
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --generate-logs 1 --generate-log-domain linux --generate-log-severity critical
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --generate-logs 1 --generate-log-domain windows --generate-log-severity error
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.main --generate-logs 1 --generate-log-domain vmware --generate-log-severity critical
```

The generator appends to `dynamic-*.log` files under `LOG_ROOT_PATH`. The scheduler reads only new appended lines after the cursor baseline.

## AgentBase runtime API

The custom runtime wrapper is provided by `infra_log_sentinel.server`. It keeps the CLI intact and adds HTTP endpoints required for GreenNode AgentBase Custom Agent packaging.

Local runtime test:

```powershell
cd "G:\My Drive\8. VNG\07.PYCODE\VNG\AGENT\infra-log-sentinel-agent"
C:\Users\LAP14917-local\Documents\Codex\.venvs\infra-log-sentinel-agent\Scripts\python.exe -m infra_log_sentinel.server
```

Health check:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8080/health" -UseBasicParsing
```

Runtime status:

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:8080/status" -UseBasicParsing
```

Chat/invocation API:

```powershell
Invoke-WebRequest `
  -Uri "http://127.0.0.1:8080/invocations" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Body '{"message":"tom tat log hom nay"}' `
  -UseBasicParsing
```

Docker build for AgentBase Runtime:

```powershell
docker build --platform linux/amd64 -t infra-log-sentinel-agent:test .
```

Docker local run:

```powershell
docker run --rm -p 8080:8080 --env-file .env infra-log-sentinel-agent:test
```

Notes:

- The platform requires only `GET /health` on port `8080`.
- `POST /invocations` and `POST /chat` accept `message`, `question`, `input`, `prompt`, or a chat-style `messages` list.
- `.dockerignore` excludes `.env`, `.greennode.json`, `.agentbase/`, credentials, runtime data, reports, and git metadata.
- For the self-contained GreenNode demo, the Docker image uses `LOG_SOURCE_MODE=runtime_folder`, creates `/app/data/logs`, bootstraps synthetic logs, and appends a new abnormal log every 30 seconds.
- Scheduler delivery is disabled by default in Docker. Enable `RUNTIME_SCHEDULER_ENABLED=true` and `RUNTIME_SCHEDULER_DRY_RUN=false` only after Gmail and Telegram env vars are ready.
- Runtime control chat commands can pause Telegram alerts, scheduled Gmail reports, or auto log generation until a relative duration or a clock time. Examples: `tam dung alert va report trong 30 phut`, `tam ngung sinh log den 17:30`, `doi interval sinh log 120 giay`.
- To enable Telegram chat in the hosted runtime, set `TELEGRAM_CHAT_ENABLED=true` after `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are configured. The runtime uses polling with its Telegram chat cursor, so run `--init-telegram-chat` locally or start from a fresh bot/chat queue before enabling it for a live demo.

## Documentation

- GreenNode submission packet: `docs/submission.md`
- Log and report format: `docs/log-and-report-format.md`
- AgentBase runtime readiness: `docs/agentbase-runtime.md`
