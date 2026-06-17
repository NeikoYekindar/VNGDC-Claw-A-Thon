# VNGDC-247-OPERATION-AGENT

VNGDC-247-OPERATION-AGENT is a unified multi-agent operations platform for modern data
center teams. It brings monitoring intelligence, infrastructure log RCA, and
security hardening into one master dashboard where operators can ask questions,
review system posture, investigate incidents, and coordinate actions across
specialized AI agents.

The project is built around a master-agent architecture. Instead of forcing a
single agent to understand every operational domain, the system delegates work to
focused child agents and lets a master agent route, merge, and synthesize their
answers. This makes the platform practical for NOC, SRE, SecOps, and platform
operations workflows where one incident often spans metrics, logs, server state,
and vulnerability posture.

## Executive Summary

This repository contains a complete multi-agent system for 24/7 data center
operations:

- A Master Agent that receives operator questions, decides which child agents to
  consult, fan-outs requests, and summarizes the result.
- A Unified Dashboard that combines Monitoring, Logging, and Security user
  interfaces into a single left-navigation platform experience.
- A Monitoring Agent for alert RCA, server investigation, inventory, maintenance
  windows, and knowledge-based troubleshooting.
- A Logging Agent for infrastructure log intelligence, event classification,
  runtime controls, incident simulation, and AIOps RCA.
- A Security Agent for hardening posture, Wazuh vulnerability intelligence,
  CVE prioritization, and security remediation planning.

The result is an operations fabric where a user can ask a broad question such as
"what is happening in the system right now?" and the master agent can consult
Monitoring, Logging, and Security together before producing a coordinated
answer.

## Architecture

```text
                         +-------------------------+
                         |        Operator         |
                         |  Web dashboard / chat   |
                         +------------+------------+
                                      |
                                      v
                    +-----------------+-----------------+
                    |          VNGDC Master Agent        |
                    |------------------------------------|
                    | Intent routing                     |
                    | Multi-agent fan-out                |
                    | Conversation memory                |
                    | LLM synthesis                      |
                    | AgentBase health and invocations   |
                    +-----+----------------------+-------+
                          |               |      |
          +---------------+               |      +-----------------------------+
          |                               |                                    |
          v                               v                                    v
+---------+----------+         +----------------------+            +-----------+----------+
| Monitoring Agent   |         | Security Agent       |            | Logging Agent        |
| ai-agent-monitoring|         | vngdc-vul-hardening  |            | infra-log-sentinel   |
+---------+----------+         +----------+-----------+            +-----------+----------+
          |                               |                                    |
          |                               |                                    |
          v                               v                                    v
 Prometheus alerts, RCA,        Hardening, Wazuh, CVE,               Log parsing, severity,
 SSH checks, inventory,         patch priority, reports              RCA workspace, incident
 knowledge base                                                      generation, reports

```

### Master-Agent Routing Model

The master agent supports two interaction modes:

1. Explicit routing through slash commands:

```text
/monitoring check current alerts
/logging analyze current RCA evidence
/security summarize critical CVEs
```

When a slash command is used, the master forwards the question to the selected
child agent and returns the child agent answer without unnecessary rewriting.

2. Intelligent routing through natural language:

```text
Are there any critical problems in the environment right now?
```

The master classifies the question and may consult one, two, or all three child
agents. For broad operational questions, it can query Monitoring, Logging, and
Security together, then synthesize the answer with a clear recommendation.

## Agent Responsibilities

### 1. VNGDC Master Agent

Path: `master-agent/`

The master agent is the coordination layer of the platform. It exposes an
AgentBase-compatible runtime and serves the unified dashboard through the same
deployed endpoint.

Core responsibilities:

- Route user questions to the right specialist agent.
- Ask multiple agents when the question crosses domains.
- Preserve conversation context within the current chat session.
- Provide slash-command routing for direct child-agent access.
- Summarize Monitoring, Logging, and Security findings into one response.
- Expose `/health` and `/invocations` for AgentBase runtime activation.
- Serve the Next.js dashboard and FastAPI backend APIs.

Key files:

```text
master-agent/
├── main.py                         # FastAPI runtime and dashboard API
├── agent_runtime.py                # Master routing and synthesis logic
├── prompts/master_system_prompt.md # Master behavior prompt
├── create_dashboard_runtime.py     # AgentBase deploy/update helper
└── dashboard/                      # Unified dashboard frontend/backend
```

### 2. Monitoring Agent

Path: `ai-agent-monitoring/`

Link github: [Monitoring Agent](https://github.com/quantc31/ai-agent-monitoring)

The monitoring agent focuses on metrics, alerts, server investigation, and
runbook-driven RCA. It can receive alerts from Prometheus Alertmanager, group
related alerts into batches, run safe investigation commands, and generate
Vietnamese RCA reports for operations teams.

Core capabilities:

- Prometheus Alertmanager webhook handling.
- Alert batching to avoid noisy duplicate investigations.
- Server RCA using safe SSH command allowlists.
- CPU, RAM, disk, network, latency, and service investigation.
- Knowledge base management with Markdown runbooks.
- Inventory visibility for monitored assets.
- Maintenance and suppression windows.
- Telegram-ready operational reporting.

How it is used by the master dashboard:

- Monitoring overview and inventory.
- Alert analysis and RCA batches.
- Knowledge Base view/edit/save.
- Maintenance suppression management.
- Direct `/monitoring` chat routing.

### 3. Infrastructure Log Sentinel Agent

Path: `infra-log-sentinel-agent/`

Link github: [Infrastructure Log Sentinel Agent](https://github.com/trangdm/infra-log-sentinel-agent)

The logging agent is an AIOps log intelligence system. It reads infrastructure
logs, detects domains, parses events, classifies severity, and runs root cause
analysis over current or generated incident logs.

Supported log domains include:

- Network infrastructure.
- Linux syslog.
- Windows events.
- VMware and virtualization logs.
- Wazuh/security-style signals.
- Observability and synthetic incident streams.

Core capabilities:

- Log ingestion and normalized event parsing.
- Severity classification: info, warning, error, critical.
- Current log summary and top-alert review.
- RCA workspace with impact, time window, evidence, analysis, and actions.
- Synthetic incident generation for RCA validation.
- Runtime controls for alerting, reporting, and log generation.
- PDF/Gmail reporting and Telegram alert workflows.
- Command-oriented investigation guidance.

How it is used by the master dashboard:

- Logging console with event severity breakdown.
- RCA workspace with From/To windows and full RCA blocks.
- Runtime control page.
- Quick actions and quick impact prompts.
- Direct `/logging` chat routing.

### 4. Security Hardening Agent

Path: `vngdc-vul-hardening-all/`

Link github: [ Security Hardening Agent](https://github.com/NeikoYekindar/Claw-A-Thon)

The security agent focuses on hardening, Wazuh visibility, vulnerability
prioritization, and remediation planning for internal infrastructure. It is
designed for environments where security posture must be evaluated alongside
operational context, not as an isolated scanner output.

Core capabilities:

- Server hardening checks for Ubuntu, Windows Server, and Juniper Junos.
- Managed server inventory.
- Asynchronous hardening check tasks with polling.
- Detailed hardening reports with pass/warn/fail sections.
- Wazuh agent inventory and vulnerability data.
- Vulnerability asset posture.
- Emerging CVE radar using CVE, EPSS, KEV, and local relevance signals.
- Patch priority and remediation planning.
- Telegram or Teams-style security notifications.

How it is used by the master dashboard:

- Hardening posture dashboard.
- Add server, run check, task polling, and detail pages.
- Vulnerability assets and CVE detail pages.
- Emerging CVE radar with relation/risk/EPSS highlighting.
- Direct `/security` chat routing.

## Unified Dashboard

The master dashboard is the central operations cockpit. It is built as a
Next.js frontend backed by a FastAPI API and is deployed with the master agent.

Main navigation areas:

```text
Overview
Master Chat
Monitoring
  - Overview
  - Alerts
  - Inventory
  - Knowledge Base
  - Maintenance
Logging
  - Log Console
  - RCA Workspace
  - Runtime Control
Security
  - Hardening
  - Vulnerability Assets
  - Emerging CVE Radar
```

Dashboard highlights:

- Platform-style left navigation.
- Unified system overview across all child agents.
- Master chat with session history and new conversation support.
- Quick action dropdown filtered by selected agent.
- Raw payload sections hidden by default.
- Agent-specific pages that preserve the original child-agent workflows.
- RCA and security outputs rendered as structured cards for fast scanning.

## Key Workflows

### Incident Triage

1. Operator asks the master agent what is happening.
2. Master routes the question to Monitoring and Logging, and optionally Security.
3. Monitoring reports active alerts, impacted assets, or metric anomalies.
4. Logging correlates logs and provides RCA evidence.
5. Security contributes hardening or vulnerability context if relevant.
6. Master synthesizes the final recommendation.

### Direct RCA

1. Operator opens Logging -> RCA Workspace.
2. Enters impact or symptom.
3. Chooses lookback hours or From/To window.
4. Runs current-log analysis or generates a synthetic incident.
5. Dashboard renders root cause, evidence, analysis, actions, and commands.

### Security Posture Review

1. Operator opens Security -> Hardening.
2. Adds or selects a managed server.
3. Runs a hardening check.
4. Dashboard polls task status and displays the report.
5. Operator reviews vulnerability assets and CVE radar for patch priority.

### Knowledge-Driven Operations

1. Operator opens Monitoring -> Knowledge Base.
2. Selects or edits a Markdown runbook.
3. Saves updated knowledge.
4. Monitoring agent can use the updated runbooks in future RCA responses.

## Runtime and Deployment

The master agent is designed for GreenNode AgentBase custom runtime deployment.

Runtime contract:

```text
GET  /health       # AgentBase health check
POST /invocations  # Agent invocation entrypoint
GET  /             # Unified dashboard
GET  /api/*        # Dashboard API proxy and orchestration APIs
```

Deploy helper:

```powershell
cd master-agent
python create_dashboard_runtime.py create
python create_dashboard_runtime.py status
python create_dashboard_runtime.py update
```

Local backend:

```powershell
cd master-agent
python -m venv .venv
.\.venv\Scripts\pip install -r dashboard\backend\requirements.txt
.\.venv\Scripts\uvicorn main:app --host 127.0.0.1 --port 8000
```

Local frontend:

```powershell
cd master-agent\dashboard\frontend
npm install
$env:API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

Docker:

```powershell
cd master-agent
docker build --platform linux/amd64 -f dashboard/Dockerfile -t vngdc-master-agent:latest .
docker run --rm -p 8080:8080 vngdc-master-agent:latest
```

## LLM Core

The master synthesis layer is configured for an OpenAI-compatible LLM endpoint.
The current recommended model is MiniMax M2.5:

```text
LLM_MODEL=minimax/minimax-m2.5
LLM_BASE_URL=<openai-compatible-base-url>
LLM_API_KEY=<runtime-secret>
MASTER_LLM_SYNTHESIS_ENABLED=true
```

Secrets should be provided through runtime environment variables or local
`.env` files. They are intentionally excluded from Git.

## Repository Layout

```text
VNGDC-Claw-A-Thon/
├── master-agent/                 # Master orchestrator and unified dashboard
├── ai-agent-monitoring/          # Monitoring RCA and alert investigation agent
├── infra-log-sentinel-agent/     # Logging, RCA, reports, and runtime controls
├── vngdc-vul-hardening-all/      # Security hardening and vulnerability agent
├── greennode-agentbase-skills/   # AgentBase deployment and operations skills
├── .gitignore                    # Repository-wide ignore policy
└── README.md                     # This file
```

## Git and Artifact Hygiene

This repository is configured to keep source code and configuration templates in
Git while excluding generated artifacts and secrets.

Ignored by default:

- `node_modules/`
- `.next/`
- `.venv/`
- runtime caches
- `.env` and deploy secret files
- SQLite databases
- generated reports
- local AgentBase state

Commit these instead:

- source code
- dashboard UI files
- `package.json` and `package-lock.json`
- `requirements.txt`
- `.env.example` files
- runbooks, templates, profiles, and documentation

## Why This Project Matters

Traditional operations tools often split the work across dashboards: one view
for monitoring, another for logs, another for hardening, and another for
vulnerabilities. In real incidents, those boundaries disappear. A service outage
may start as a metric anomaly, surface as log errors, and become more urgent
because the affected host has a critical CVE or weak baseline.

VNGDC-Claw-A-Thon treats operations as a coordinated multi-agent problem. Each
agent remains specialized, but the master agent gives operators a single place
to ask, compare, and decide. The design keeps expert context close to the data
while giving the user one clear operational answer.

## Project Status

The repository includes working implementations for:

- Master agent runtime and dashboard.
- Child-agent routing and direct slash-command forwarding.
- Unified Monitoring, Logging, and Security dashboard modules.
- Conversation history and quick actions in the master chat.
- Full Logging RCA workspace rendering.
- Security hardening and vulnerability UI integration.
- Git ignore policy for GitHub publication.

This project is suitable as a foundation for an internal data center operations
assistant, a hackathon submission, or a reference architecture for multi-agent
infrastructure operations.
