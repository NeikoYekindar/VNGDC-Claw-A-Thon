# 🤖 AI Alert RCA Agent

**AI Agent tự động phân tích nguyên nhân gốc rễ (Root Cause Analysis)** khi hệ thống có cảnh báo.  
Nhận alert từ Prometheus Alertmanager → SSH vào server điều tra → LLM phân tích → Gửi báo cáo Telegram bằng tiếng Việt.

Built for **GreenNode Claw-a-thon 2026** · Powered by **LangGraph + MiniMax M2.5**

---

## Tính năng chính

- **Nhận alert tự động** từ Prometheus Alertmanager hoặc gửi thủ công qua API/Web UI
- **Gom batch 5 phút** — nhiều alert cùng instance được phân tích chung, tránh spam
- **SSH điều tra thực tế** — chạy lệnh chẩn đoán an toàn (allowlist) trên server bị ảnh hưởng
- **LLM phân tích nguyên nhân** — dùng MiniMax M2.5 để đọc output, kết luận nguyên nhân và đề xuất fix
- **Báo cáo Telegram** đẹp — HTML format, tiếng Việt, có icon, phân loại rõ ràng
- **Chat UI web** — giao diện trực quan để chat điều tra server, gửi alert, quản lý knowledge
- **Knowledge Base** — upload file `.md` để agent học thêm kiến thức, không cần redeploy
- **Đăng nhập phân quyền** — Admin có toàn quyền; User thường chỉ xem và chat

---

## Luồng hoạt động

```
Prometheus Alertmanager ──► POST /invocations
                                    │
                             BatchManager
                          (gom alert 5 phút)
                                    │
                    ┌───── LangGraph Workflow ──────┐
                    │                               │
             analyze_alerts                         │
                    │                               │
          evaluate_relevance                        │
                    │                               │
          ┌─────────┴──────────┐                    │
          │ High/Medium        │ Low                │
          ▼                    ▼                    │
      investigate         generate_report           │
    (SSH + Metrics)       (note only)               │
          │                    │                    │
   analyze_root_cause          │                    │
    (LLM, tiếng Việt)          │                    │
          │                    │                    │
     recommend_fix             │                    │
    (LLM, tiếng Việt)          │                    │
          │                    │                    │
     generate_report ◄─────────┘                    │
          │                                         │
     send_to_teams (Telegram HTML)                  │
                    └───────────────────────────────┘
```

---

## Cấu trúc thư mục

```
ai-agent-monitoring/
│
├── main.py                    ⭐ Entrypoint chính — xử lý tất cả action, auth, routing
├── chat_ui.html               ⭐ Web UI — Chat, Send Alert, Knowledge Base, Users (admin)
├── config.yaml                ⭐ Cấu hình agent (batch window, SSH timeout, critical services)
├── .env                          Biến môi trường (không commit)
│
├── workflow/
│   └── agent_graph.py         ⭐ LangGraph workflow — toàn bộ luồng RCA
│
├── analyzers/
│   ├── alert_analyzer.py         Phân tích và tóm tắt danh sách alert
│   ├── relevance_evaluator.py    Đánh giá mức độ liên quan (high/medium/low)
│   ├── root_cause_analyzer.py ⭐ Phân tích nguyên nhân gốc rễ bằng LLM (tiếng Việt)
│   └── fix_recommender.py     ⭐ Đề xuất giải pháp (immediate / long-term / cần duyệt)
│
├── chat/
│   └── chat_handler.py        ⭐ Xử lý chat tự nhiên — NLU → SSH investigate → summary
│
├── executors/
│   ├── ssh_executor.py        ⭐ SSH vào server, chạy lệnh, trả output
│   └── command_policy.py         Allowlist lệnh an toàn, phân loại theo check_type
│
├── reporters/
│   └── telegram_reporter.py   ⭐ Gửi báo cáo HTML qua Telegram Bot API
│
├── batching/
│   └── batch_manager.py          Gom alert theo instance, quản lý timer 5 phút
│
├── models/
│   ├── alert.py                  Model Alert — từ raw JSON hoặc Alertmanager webhook
│   ├── batch.py                  Model AlertBatch — trạng thái batch
│   └── report.py                 Model báo cáo RCA (BatchReport, RecommendedFix...)
│
├── utils/
│   ├── knowledge_loader.py    ⭐ Load tất cả .md từ knowledge/ — inject vào LLM context
│   ├── auth.py                ⭐ Login, session token, user management (JSON store)
│   └── logger.py                 Logging RCA result và report sent
│
├── knowledge/                 ⭐ Thư mục chứa file kiến thức — upload qua Web UI
│   ├── cpu.md                    Ngưỡng CPU, nguyên nhân, lệnh điều tra
│   ├── ram.md                    Ngưỡng RAM/Swap, OOMKiller, memory leak
│   ├── disk.md                   Ngưỡng disk, log rotation, inode, Docker cleanup
│   └── network.md                Packet loss, latency, connection refused, DNS
│
├── data/
│   └── users.json                Danh sách user (tự sinh khi khởi động lần đầu)
│
└── infra/
    ├── userdata_agent.sh         EC2 User Data script — cài Docker, chạy agent
    └── userdata_monitor.sh       EC2 User Data script — cài Prometheus + node_exporter
```

---

## Các file quan trọng cần chú ý

| File | Vai trò |
|------|---------|
| `main.py` | Điểm vào duy nhất, định tuyến tất cả action, kiểm tra auth |
| `workflow/agent_graph.py` | Toàn bộ logic RCA: từ nhận alert đến gửi Telegram |
| `chat/chat_handler.py` | NLU một lần call LLM → quyết định intent → SSH → tóm tắt |
| `utils/knowledge_loader.py` | Load toàn bộ `.md` trong `knowledge/` vào context LLM |
| `utils/auth.py` | Quản lý user, hash password, session token 24h |
| `reporters/telegram_reporter.py` | Escape HTML, chia chunk, retry gửi Telegram |
| `config.yaml` | Tuỳ chỉnh batch window, SSH timeout, critical services |
| `knowledge/*.md` | Kiến thức mới về KB — **upload qua Web UI, không cần redeploy** |

---

## Cấu hình môi trường (`.env`)

```env
# LLM (GreenNode AIP)
LLM_MODEL=minimax/minimax-m2.5
LLM_BASE_URL=https://...
LLM_API_KEY=your_key_here

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# SSH
SSH_USERNAME=monitor
SSH_PRIVATE_KEY_PATH=/app/keys/id_rsa

# Auth — mật khẩu admin mặc định khi tạo lần đầu
ADMIN_DEFAULT_PASSWORD=your_secure_password
```

---

## Cấu hình agent (`config.yaml`)

```yaml
agent:
  batch_window_minutes: 5          # Thời gian gom alert trước khi phân tích
  command_timeout_seconds: 20      # SSH timeout mỗi lệnh

system_context:
  critical_environments: [prod, production, unknown]
  critical_services: [payment-api, auth-service, database, gateway, ...]
```

## Web UI

Truy cập `http://<agent-endpoint>/` → Login → 4 tab:

| Tab | Quyền | Chức năng |
|-----|-------|-----------|
| 💬 **Chat/Investigate** | Tất cả | Chat tự nhiên bằng tiếng Việt, agent tự SSH điều tra server |
| 🚨 **Send Alert** | Tất cả | Gửi alert giả để test pipeline |
| 📚 **Knowledge Base** | Xem: tất cả · Upload/Xóa: Admin | Quản lý file kiến thức `.md` |
| 👥 **Users** | Admin | Tạo/xóa tài khoản, phân role |

## API Actions (POST `/invocations`)

Tất cả request (trừ `login`, `health`, `alertmanager_webhook`) cần gửi kèm `"token"`.

### Public (không cần token)

```jsonc
{ "action": "login",   "username": "admin", "password": "..." }
{ "action": "logout",  "token": "..." }
{ "action": "health" }

// Alertmanager webhook — format chuẩn Prometheus
{ "alerts": [...], "version": "4", ... }
```

### User (cần đăng nhập)

```jsonc
{ "action": "chat",          "message": "check CPU trên 10.0.0.5", "token": "..." }
{ "action": "receive_alert", "alert": { ...AlertSchema... },        "token": "..." }
{ "action": "list_batches",  "token": "..." }
{ "action": "trigger_batch", "batch_id": "...",                     "token": "..." }
{ "action": "list_knowledge","token": "..." }
```

### Admin only

```jsonc
{ "action": "upload_knowledge", "filename": "nginx.md", "content": "...", "token": "..." }
{ "action": "delete_knowledge", "filename": "nginx.md",                   "token": "..." }
{ "action": "create_user",      "username": "...", "password": "...", "role": "user|admin", "token": "..." }
{ "action": "delete_user",      "username": "...",                        "token": "..." }
{ "action": "list_users",       "token": "..." }
```

---

## Knowledge Base

Agent tự động load **toàn bộ** file `.md` trong thư mục `knowledge/` vào LLM context mỗi khi phân tích.

- **Upload qua Web UI** → Agent học ngay, không cần redeploy
- **Không giới hạn chủ đề** — CPU, RAM, Disk, Network, Nginx, Database, thông tin team, runbook...
- **Format**: Markdown tiêu chuẩn, nên có heading rõ ràng để LLM dễ tham chiếu

---

## Báo cáo Telegram — mẫu

```
🚨 CẢNH BÁO: HighCPUUsage

🖥  Server: 54.204.88.9
⏰ Thời gian: 14/06/2026 08:30 UTC
🔴 Mức độ: CRITICAL

━━━━━━━━━━━━━━━━━━━━━━
🔎 KẾT QUẢ KIỂM TRA
━━━━━━━━━━━━━━━━━━━━━━
✅ top -bn1
   ↳ %Cpu(s): 94.2 us, 3.1 sy | load average: 8.4, 7.9, 6.2
✅ ps aux --sort=-%cpu | head -10
   ↳ python3 92.1% | java 4.2%

━━━━━━━━━━━━━━━━━━━━━━
🎯 NGUYÊN NHÂN
━━━━━━━━━━━━━━━━━━━━━━
Process python3 đang chiếm ~92% CPU liên tục — khả năng cao là infinite loop hoặc unindexed DB query.
✅ Độ tin cậy: HIGH

🔧 KHUYẾN NGHỊ
⚡ Ngay lập tức:
  • Kiểm tra và restart service python3 nếu không phản hồi
📅 Dài hạn:
  • Review query không có index trong application code

🤖 Không có auto-remediation.
```

---

## Bảo mật

- Không hardcode credential trong source code — tất cả qua env var
- SSH chỉ chạy lệnh trong allowlist (`config.yaml`) — không có `rm`, `kill`, `reboot`
- Token có TTL 24h, lưu in-memory — tự hết hạn khi restart
- Output SSH không chứa credential trong báo cáo
- Auto-remediation **tắt mặc định**
- Không thể xóa admin duy nhất trong hệ thống

---

## Tech Stack

| Thành phần | Công nghệ |
|------------|-----------|
| Agent Runtime | GreenNode AgentBase SDK |
| Workflow | LangGraph (StateGraph) |
| LLM | MiniMax M2.5 (via GreenNode AIP) |
| Web framework | Starlette (tích hợp AgentBase) |
| SSH | Paramiko |
| HTTP | httpx |
| Schema validation | Pydantic v2 |
| Batch scheduling | APScheduler |
| Notification | Telegram Bot API (HTML mode) |
| Auth | SHA-256 + salt, session token in memory |

---

## Quick Start

```bash
# 1. Clone và setup
cd ai-agent-monitoring
cp .env.example .env
# Điền LLM_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SSH_USERNAME...

# 2. Chạy local với Docker
docker build -t ai-alert-agent .
docker run --env-file .env -p 8080:8080 ai-alert-agent

# 3. Mở Web UI
open http://localhost:8080
# Đăng nhập: admin / (xem log container để lấy mật khẩu mặc định)

# 4. Test gửi alert
curl -X POST http://localhost:8080/invocations \
  -H "Content-Type: application/json" \
  -d '{"alerts":[{"status":"firing","labels":{"alertname":"HighCPU","instance":"10.0.0.1","severity":"critical"},"annotations":{"description":"CPU > 90%"}}]}'
```

---

## Tích hợp Prometheus Alertmanager

Thêm vào `alertmanager.yml`:

```yaml
receivers:
  - name: ai-agent
    webhook_configs:
      - url: http://<agent-endpoint>/invocations
        send_resolved: false

route:
  receiver: ai-agent
```

Agent nhận payload chuẩn Alertmanager, tự detect và xử lý — không cần field `action`.

>**Copyright © 2026 Tô Công Quân.**
