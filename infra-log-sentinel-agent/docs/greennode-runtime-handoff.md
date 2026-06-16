# Greennode Runtime Handoff - 2026-06-14

This note captures the current deployment state for Infra Log Sentinel Agent before pausing to check with Greennode support.

No secrets, tokens, API keys, Gmail app passwords, or Telegram bot tokens are stored here.

## Resolution - 2026-06-15

Greennode fixed the overloaded runtime infrastructure. The main hosted runtime was redeployed successfully instead of using the stuck v34 runtime.

```text
Runtime ID:      runtime-a864917b-1a16-4083-a64c-82f4e79f6602
Endpoint ID:     endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9
Endpoint:        https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9.agentbase-runtime.aiplatform.vngcloud.vn
Image:           vcr.vngcloud.vn/111480-abp111815/infra-log-sentinel-agent:v20260616-ui-history-layout-v41
Image digest:    sha256:279134c8fc3d7c521e16e36cc78df56b0c2e586cd5330b50535cbfd2c9276ffa
Endpoint version: 39
Runtime status:  ACTIVE
Endpoint status: ACTIVE
Replicas:        1
Health:          ok
```

Hosted UI smoke confirmed the Log & RCA chat workspace with Chat Agent Recents under Quick action, Quick action and Quick impact dropdowns, RCA Recent history inside the RCA tab showing Impact/symptom plus time, aligned Chat Agent/RCA side-panel spacing, vertical RCA result blocks, Vietnamese RCA explanations, Action command cards, and timezone-labeled report time.

## Current Code State

- Project: `infra-log-sentinel-agent`
- Agent type: Custom Agent Runtime
- Runtime contract:
  - Docker exposes port `8080`
  - App listens on `PORT` / `RUNTIME_PORT`, default `8080`
  - App exposes `GET /health`
- Latest local feature work:
  - RCA log analyzer with timeline/root-cause/evidence/action report.
  - RCA focus guard to avoid matching unrelated incidents.
  - LLM guidance fallback for unfamiliar RCA or insufficient log evidence.
  - RCA report no longer uses the long "RCA investigation answers" block.
  - Root cause summary is highlighted separately from timeline.
  - Incident generator expanded for demo RCA scenarios.

## Best-Practice Deploy Attempt

Confirmed plan with user before executing.

- Registry: AgentBase managed CR
- Registry auth: `--from-cr`
- Build platform: `linux/amd64`
- Network mode: PUBLIC by default, no explicit `--network-mode PUBLIC`
- Env file: `.env.greennode`
- Flavor: `runtime-s2-general-2x4`
- Autoscaling: min `1`, max `1`, CPU `50`, memory `50`
- Runtime name: `infra-log-sentinel-v34-2x4`

Image built and pushed successfully:

```text
vcr.vngcloud.vn/111480-abp111815/infra-log-sentinel-agent:v20260614-bestpractice-v34
digest: sha256:4ee99a064f01802d726124b1c668eca74a389d6bcafc831703c783dfb416f309
```

Runtime created:

```text
Runtime ID:  runtime-cc637901-67a3-4509-bef1-3e079bd894db
Name:        infra-log-sentinel-v34-2x4
Endpoint ID: endpoint-bc89cc10-174f-4157-9ce7-cd43cb03ed69
Endpoint:    https://endpoint-bc89cc10-174f-4157-9ce7-cd43cb03ed69.agentbase-runtime.aiplatform.vngcloud.vn
Observed:    CREATING, currentReplicaCount=0
Logs:        empty
Events:      empty
Health:      "failure to get a peer from the ring-balancer"
```

## Other Runtime Observations

### Last Known Working Endpoint

Old runtime:

```text
Runtime ID:  runtime-a864917b-1a16-4083-a64c-82f4e79f6602
Name:        infra-log-sentinel-agent
Endpoint ID: endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9
Endpoint:    https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9.agentbase-runtime.aiplatform.vngcloud.vn
Runtime status observed: ERROR
Endpoint version observed: 32
Replica observed earlier: 1
Health observed earlier: OK
RCA smoke observed earlier: LOG-RCA-FOCUS-NOT-FOUND + insufficient_data + llm_guidance=true
```

Note: Control-plane status showed `ERROR`, but the endpoint was still serving during the last successful smoke test.

### Failed / Stuck New Runtimes

v31:

```text
Runtime ID:  runtime-b146f181-ce0e-4ba1-b68f-9564fd17a52e
Name:        infra-log-sentinel-v31-4x8
Endpoint ID: endpoint-68cc77d5-c46b-4282-9e80-848018c24b50
Status:      ERROR
Replica:     0
Health:      "no Route matched with those values"
Logs:        empty
Events:      empty
```

v32:

```text
Runtime ID:  runtime-d920d435-493d-43e1-a4f7-3a89418429a6
Name:        infra-log-sentinel-v32-4x8
Endpoint ID: endpoint-d0e4aa50-4757-450f-ad0c-a811f6525af4
Observed:    ERROR / endpoint DELETING during checks
Replica:     0
Logs/events: unavailable or HTTP 400 during follow-up checks
```

v33:

```text
Runtime ID:  runtime-20b75e4e-2870-496a-af68-3220d56706d6
Name:        infra-log-sentinel-v33-4x8
Endpoint ID: endpoint-13e7ae23-0d3a-4f8a-9ce2-0eaa0ba15bc5
Status:      ERROR
Replica:     0
Logs:        empty
Events:      empty
```

Earlier v33-4x8 attempt:

```text
Runtime ID:  runtime-28d9e98c-bcb4-4573-804c-3942d511f061
Name:        infra-log-sentinel-agent-v33-4x8
Observed:    stuck CREATING, currentReplicaCount=0, no logs/events
```

## Support Hypothesis

The repeated symptom is:

- Runtime metadata is created.
- DEFAULT endpoint is created.
- `currentReplicaCount` remains `0`.
- `/health` cannot route to a backend.
- Endpoint logs are empty.
- Endpoint infrastructure events are empty.

This suggests the container is not reaching the point where app logs can be emitted. Current leading possibilities:

- AgentBase scheduler/provisioning issue.
- Runtime cannot attach a replica to the endpoint.
- Image pull failure that is not surfaced in endpoint events/logs.
- Resource pool/quota/flavor issue.
- Control-plane state issue around `CREATING` -> `ERROR`.

The app itself still appears to satisfy the hard runtime contract: port `8080` and `GET /health`.

## Notes From Skill Audit

- `runtime.sh create/update` does not auto-poll to ACTIVE, even though deploy docs say scripts handle polling automatically. Manual polling is required.
- Avoid running `runtime.sh versions` and pasting raw output because version responses can include environment variables.
- PUBLIC runtime should omit `--network-mode` unless explicitly switching network mode.
- Use helper scripts only:
  - `check_credentials.sh iam`
  - `cr.sh repo get`
  - `cr.sh credentials docker-login`
  - `runtime.sh create/get/endpoints`

## Suggested Message To Greennode Support

```text
Custom Agent runtime is created successfully, and DEFAULT endpoint is created, but endpoint remains currentReplicaCount=0 and never routes to container.

Please check provisioning/scheduler/image-pull/runtime backend for:

Runtime ID: runtime-cc637901-67a3-4509-bef1-3e079bd894db
Endpoint ID: endpoint-bc89cc10-174f-4157-9ce7-cd43cb03ed69
Image: vcr.vngcloud.vn/111480-abp111815/infra-log-sentinel-agent:v20260614-bestpractice-v34
Flavor: runtime-s2-general-2x4
Network: PUBLIC default

Observed:
- Runtime/endpoint stuck at CREATING
- currentReplicaCount=0
- /health returns "failure to get a peer from the ring-balancer"
- endpoint logs empty
- endpoint events empty

The container listens on port 8080 and exposes GET /health.
```

## Continue Checklist

After support responds:

1. Poll the v34 runtime:

```powershell
& 'C:\Program Files\Git\bin\bash.exe' ../greennode-agentbase-skills/.claude/skills/agentbase/scripts/runtime.sh get runtime-cc637901-67a3-4509-bef1-3e079bd894db
& 'C:\Program Files\Git\bin\bash.exe' ../greennode-agentbase-skills/.claude/skills/agentbase/scripts/runtime.sh endpoints list runtime-cc637901-67a3-4509-bef1-3e079bd894db
```

2. If endpoint has `currentReplicaCount > 0`, check health:

```powershell
Invoke-RestMethod -Uri 'https://endpoint-bc89cc10-174f-4157-9ce7-cd43cb03ed69.agentbase-runtime.aiplatform.vngcloud.vn/health' -TimeoutSec 30
```

3. If health is OK, smoke RCA insufficient-data behavior:

```powershell
$body = @{ lookback_hours = 1; impact = 'quantum billing zebra outage' } | ConvertTo-Json
$result = Invoke-RestMethod -Method Post -Uri 'https://endpoint-bc89cc10-174f-4157-9ce7-cd43cb03ed69.agentbase-runtime.aiplatform.vngcloud.vn/rca/logs/analyze' -ContentType 'application/json' -Body $body -TimeoutSec 150
[pscustomobject]@{
  Status=$result.status
  Incident=$result.analysis.incident_id
  AnalysisStatus=$result.analysis.status
  HasGuidance=[bool]$result.analysis.llm_guidance
  Root=$result.analysis.most_likely_root_cause
} | ConvertTo-Json -Depth 5
```

Expected:

```text
Incident: LOG-RCA-FOCUS-NOT-FOUND
AnalysisStatus: insufficient_data
HasGuidance: true
Root: Insufficient log evidence for the requested RCA focus.
```
