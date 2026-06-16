# VNGDC Master Agent

Master agent and unified dashboard for the three deployed child agents:

- Monitoring: `ai-agent-monitoring`
- Logging: `infra-log-sentinel-agent`
- Security: `vngdc-vul-hardening`

## Runtime contract

- Public port: `8080`
- Health check: `GET /health`
- Agent invocation: `POST /invocations`
- Dashboard API: `/api/*`
- Deploy entrypoint: `main.py`
- Master orchestration code: `agent_runtime.py`
- Master behavior prompt: `prompts/master_system_prompt.md`

The backend keeps the AgentBase-compatible `/health` and `/invocations` routes so the custom runtime can become active while the Next.js dashboard is served through the same public endpoint.

For deployment, run `main.py` through ASGI/uvicorn. Do not run `agent_runtime.py` directly; it is the master orchestration module imported by `main.py`.

## Local backend

```powershell
cd master-agent
python -m venv .venv
.\.venv\Scripts\pip install -r dashboard\backend\requirements.txt
.\.venv\Scripts\uvicorn main:app --host 127.0.0.1 --port 8000
```

## Local frontend

```powershell
cd master-agent\dashboard\frontend
npm install
$env:API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

## Docker

```powershell
cd master-agent
docker build --platform linux/amd64 -f dashboard/Dockerfile -t vngdc-master-agent:latest .
docker run --rm -p 8080:8080 vngdc-master-agent:latest
```

## AgentBase deploy

Copy `.env.deploy.example` to `.env.deploy`, add `GREENNODE_CLIENT_ID` and `GREENNODE_CLIENT_SECRET` in `.env` or `.greennode.json`, then run:

```powershell
cd master-agent
python create_dashboard_runtime.py create
python create_dashboard_runtime.py status
python create_dashboard_runtime.py update
```

After first create, set `MASTER_RUNTIME_ID` in `.env.deploy` before running `update` or `status`.

## Master routing

The master backend classifies each question and fans out to one or more child agents:

- Monitoring keywords: metrics, CPU/RAM/disk, alerts, batches, inventory.
- Logging keywords: logs, RCA, incident, event, report, runtime controls.
- Security keywords: hardening, Wazuh, vulnerabilities, CVE, patch, compliance.
- Broad system questions are sent to all three agents.

The routing and response behavior are implemented in `agent_runtime.py`.
The editable system prompt is loaded from `prompts/master_system_prompt.md`.
You can override the prompt path at runtime with `MASTER_AGENT_PROMPT_PATH`.

You can force a single child agent from the master chat by starting the message with:

```text
/monitoring kiểm tra cảnh báo hiện tại
/logging phân tích sự cố gần nhất
/security tổng hợp lỗ hổng nghiêm trọng
```

The master chat keeps in-memory conversation context per `session_id`. The dashboard exposes a chat history column, lets users create a new conversation, and sends recent messages to the LLM synthesis step as `conversation_memory`.

## Monitoring Dashboard Coverage

The master dashboard mirrors the current `ai-agent-monitoring` backend actions:

- Inventory: list and upload CSV via `list_inventory` / `upload_inventory`.
- Alert RCA: simulate correlated alerts and trigger batches.
- Maintenance: list, create, and remove suppressions via `list_suppressions`, `suppress_server`, and `remove_suppression`.
- Knowledge Base: list, upload, and delete Markdown runbooks via `list_knowledge`, `upload_knowledge`, and `delete_knowledge`.

## Master LLM core

The master synthesis layer uses the OpenAI-compatible MiniMax endpoint when `LLM_API_KEY` is available:

```powershell
LLM_MODEL=minimax/minimax-m2.5
LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
MASTER_LLM_SYNTHESIS_ENABLED=true
```

`create_dashboard_runtime.py` can reuse these LLM values from `../vngdc-vul-hardening-all/.env`, or you can set them directly in `master-agent/.env.deploy`.
