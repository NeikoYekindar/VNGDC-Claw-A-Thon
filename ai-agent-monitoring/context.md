# AI Agent Monitoring — Context & Progress

## Mục tiêu
Build **AI Alert RCA Agent** cho GreenNode Claw-a-thon 2026 (deadline: 17/06/2026 12:00 VN).

Agent nhận monitoring alerts → batch 10 phút → SSH vào server → chạy diagnostic commands → LLM phân tích root cause → gửi báo cáo về Telegram.

---

## Tech Stack
| Thành phần | Công nghệ |
|---|---|
| Agent framework | GreenNode AgentBase SDK (`GreenNodeAgentBaseApp extends Starlette`) |
| Workflow | LangGraph `StateGraph` |
| Batching | APScheduler `BackgroundScheduler` |
| SSH | Paramiko (key/password auth, bastion support) |
| LLM | `ChatOpenAI` → GreenNode AIP endpoint → `minimax/minimax-m2.5` |
| Notification | Telegram Bot API (MarkdownV2, 4096-char split) |
| Deploy | Docker → GreenNode Container Registry |

---

## Cấu trúc thư mục
```
ai-agent-monitoring/
├── main.py                     # Entrypoint: actions receive_alert / list_batches / trigger_batch / health / chat
├── config.py                   # Pydantic AppConfig (pydantic-settings)
├── config.yaml                 # Runtime config: batch_window, SSH allowlist, telegram
├── Dockerfile                  # python:3.11-slim, EXPOSE 8080
├── requirements.txt
├── .env                        # Secrets (gitignored)
├── chat_ui.html                # Web Chat UI (served via Starlette middleware GET /)
│
├── workflow/
│   └── agent_graph.py          # LangGraph StateGraph: analyze→evaluate→investigate→RCA→fix→report→send
│
├── batching/
│   └── batch_manager.py        # APScheduler, groups alerts by instance/service/fingerprint
│
├── analyzers/
│   ├── alert_analyzer.py       # LLM: tóm tắt alert
│   ├── relevance_evaluator.py  # LLM: high/medium/low relevance + fast-path keyword check
│   ├── root_cause_analyzer.py  # LLM: root_cause + evidence + confidence (inject knowledge base)
│   └── fix_recommender.py      # LLM: immediate + long_term + need_human_approval
│
├── executors/
│   ├── ssh_executor.py         # Paramiko SSH, mock mode, bastion, timeout, sanitize output
│   └── command_policy.py       # Allowlist + blocklist (rm -rf, reboot, kill -9, ...)
│
├── reporters/
│   └── telegram_reporter.py    # Gửi Telegram, MarkdownV2 escape, dedup by batch_id, retry 3x
│
├── chat/
│   └── chat_handler.py         # Manual investigation: LLM extract intent → SSH → LLM summarize
│
├── models/
│   ├── alert.py                # Alert Pydantic model, Severity enum, Environment enum
│   ├── batch.py                # AlertBatch, is_related() grouping logic
│   └── report.py               # BatchReport, Confidence, RecommendedFix
│
├── knowledge/
│   ├── cpu.md                  # CPU thresholds, causes, commands, mitigation
│   ├── ram.md                  # Memory thresholds, OOM detection, commands
│   └── disk.md                 # Disk thresholds, log paths, inode issues, safe cleanup
│
├── utils/
│   ├── knowledge_loader.py     # Đọc .md files, match keyword → inject vào RCA prompt
│   ├── logger.py               # Structured JSON logging
│   └── sanitizer.py            # Redact passwords, tokens, API keys khỏi log/report
│
└── security/
    └── sanitizer.py
```

---

## Env vars (.env)
```
GREENNODE_CLIENT_ID=...
GREENNODE_CLIENT_SECRET=...
LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
LLM_API_KEY=...
LLM_MODEL=minimax/minimax-m2.5
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
SSH_USERNAME=monitor
SSH_PASSWORD=...
MOCK_MODE=false
CONFIG_PATH=config.yaml
```

---

## Deployment
- **AgentBase endpoint**: `https://endpoint-dbd6717d-569f-413e-b9da-b63ceda13b22.agentbase-runtime.aiplatform.vngcloud.vn`
- **Container Registry**: `vcr.vngcloud.vn/111480-abp111815/ai-agent-monitoring`
- Deploy bằng Claude Code → `/agentbase-deploy` → Redeploy

---

## API Usage

### Gửi alert (trigger RCA flow)
```bash
curl -X POST <endpoint> \
  -H "Content-Type: application/json" \
  -d '{
    "action": "receive_alert",
    "alert": {
      "alert_name": "HighCPU",
      "instance": "10.0.0.5",
      "severity": "critical",
      "service": "payment-api",
      "description": "CPU usage > 90%",
      "labels": {"env": "production"}
    }
  }'
```

### Chat / điều tra manual
```bash
curl -X POST <endpoint> \
  -H "Content-Type: application/json" \
  -d '{"action": "chat", "message": "check disk usage on 10.0.0.5"}'
```
→ Không gửi Telegram, trả response thẳng trong API.

### Xem batches đang chờ
```bash
curl -X POST <endpoint> -d '{"action": "list_batches"}'
```

### Trigger batch thủ công (test)
```bash
curl -X POST <endpoint> -d '{"action": "trigger_batch", "batch_id": "..."}'
```

---

## Features đã hoàn thành
- [x] Alert batching (10-minute window, group by instance/service/fingerprint)
- [x] SSH investigation (Paramiko, key/password, bastion, allowlist, mock mode)
- [x] LangGraph RCA workflow (4 LLM analyzers: alert → relevance → root cause → fix)
- [x] Telegram reporter (MarkdownV2, split >4096 chars, dedup, retry)
- [x] Knowledge base (cpu.md / ram.md / disk.md injected vào RCA prompt)
- [x] Chat handler (natural language → SSH → LLM summary, no Telegram)
- [x] Security: command allowlist, output sanitizer, no credential in log
- [x] Web Chat UI (`chat_ui.html`) — dark mode, 2 tab: Chat + Send Alert

---

## Root cause — Web Chat UI POST routing (ĐÃ FIX)

**SDK AgentBase v1.0.3** đăng ký routes như sau (đọc từ source `greennode_agentbase/runtime/app.py`):
```python
routes = [
    Route("/invocations", self._handle_invocation, methods=["POST"]),  # ← POST endpoint!
    Route("/health", self._handle_ping, methods=["GET"]),
]
```

**Bug**: `chat_ui.html` POST tới `window.location.origin` (root `/`), nhưng SDK chỉ handle POST tại `/invocations`.

**Fix** (1 dòng trong `chat_ui.html`):
```javascript
// Trước (sai):
const ENDPOINT = window.location.origin;
// Sau (đúng):
const ENDPOINT = window.location.origin + '/invocations';
```

**Middleware** (`_ServeUIMiddleware`) phục vụ HTML khi GET `/` — hoạt động đúng, không ảnh hưởng POST `/invocations`.

---

## Security constraints (không thay đổi)
- Không hardcode username/password/token trong source code
- Không in credential ra log hoặc report
- Command execution phải có timeout
- Chỉ chạy command trong allowlist
- Auto-remediation tắt mặc định

---

## Next steps
1. ~~Fix Web Chat UI POST routing~~ ✅ Fixed — POST to `/invocations`
2. Test local: `python main.py` → mở browser `http://localhost:8080`
3. Deploy: build Docker image → push → redeploy trên GreenNode
4. Tạo 2 EC2 AWS với public IP để test SSH thật sự
5. Test end-to-end: gửi alert → batch → SSH → RCA → Telegram
