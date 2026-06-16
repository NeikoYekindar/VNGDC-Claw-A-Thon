# 📖 Hướng dẫn triển khai AI Alert RCA Agent

## Mục lục

1. [Tổng quan kiến trúc hệ thống](#1-tổng-quan-kiến-trúc-hệ-thống)
2. [Cách thức hoạt động chi tiết](#2-cách-thức-hoạt-động-chi-tiết)
3. [Yêu cầu chuẩn bị](#3-yêu-cầu-chuẩn-bị)
4. [Bước 1 — Tạo Telegram Bot](#bước-1--tạo-telegram-bot)
5. [Bước 2 — Chuẩn bị SSH Key](#bước-2--chuẩn-bị-ssh-key)
6. [Bước 3 — Cấu hình EC2 Target (máy chủ cần giám sát)](#bước-3--cấu-hình-ec2-target-máy-chủ-cần-giám-sát)
7. [Bước 4 — Cấu hình EC2 Monitor (Prometheus + Alertmanager)](#bước-4--cấu-hình-ec2-monitor-prometheus--alertmanager)
8. [Bước 5 — Deploy AI Agent lên GreenNode AgentBase](#bước-5--deploy-ai-agent-lên-greennode-agentbase)
9. [Bước 6 — Kết nối Alertmanager với Agent](#bước-6--kết-nối-alertmanager-với-agent)
10. [Bước 7 — Đăng nhập Web UI & thiết lập ban đầu](#bước-7--đăng-nhập-web-ui--thiết-lập-ban-đầu)
11. [Kiểm tra toàn bộ hệ thống](#kiểm-tra-toàn-bộ-hệ-thống)
12. [Xử lý sự cố thường gặp](#xử-lý-sự-cố-thường-gặp)

---

## 1. Tổng quan kiến trúc hệ thống

```
┌─────────────────────────────────────────────────────────────────────┐
│                          HẠ TẦNG AWS                                │
│                                                                     │
│  ┌─────────────────────┐        ┌──────────────────────────────┐   │
│  │  EC2 #1 — Monitor   │        │  EC2 #2 — Target Server      │   │
│  │                     │        │                              │   │
│  │  Prometheus :9090   │◄──────►│  node_exporter :9100         │   │
│  │  Alertmanager :9093 │  scrape│  (thu thập metrics CPU/RAM)  │   │
│  │                     │  15s   │                              │   │
│  │  prometheus.yml     │        │  SSH user: monitor           │   │
│  │  alert_rules.yml    │        │  (cho phép password auth)    │   │
│  └──────────┬──────────┘        └──────────────────────────────┘   │
│             │ webhook                          ▲                    │
│             │ (khi alert firing)               │ SSH               │
└─────────────┼──────────────────────────────────┼────────────────────┘
              │                                  │
              ▼                                  │
┌─────────────────────────────────────────────────────────────────────┐
│              GreenNode AgentBase Runtime                            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  AI Alert RCA Agent                                          │  │
│  │                                                              │  │
│  │  POST /invocations ◄── Alertmanager webhook                  │  │
│  │  GET  /           ──► Web UI (Chat / Alert / Knowledge)      │  │
│  │                                                              │  │
│  │  BatchManager → 5 phút → LangGraph Workflow                  │  │
│  │    → SSH EC2 #2 → LLM analyze → Telegram report             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
              │
              ▼
     📱 Telegram Bot → Nhóm/Channel của team
```

### Vai trò từng thành phần

| Thành phần | Vai trò |
|------------|---------|
| **EC2 #1 (Monitor)** | Chạy Prometheus + Alertmanager. Thu thập metrics, đánh giá rule, gửi webhook khi có alert |
| **EC2 #2 (Target)** | Máy chủ thực tế cần giám sát. Chạy node_exporter, cho phép SSH từ agent |
| **AI Agent (AgentBase)** | Nhận alert, gom batch, SSH điều tra, LLM phân tích, gửi báo cáo Telegram |
| **Telegram Bot** | Kênh nhận báo cáo RCA của team |

---

## 2. Cách thức hoạt động chi tiết

### 2.1 Luồng từ alert đến báo cáo

```
[1] node_exporter trên EC2 #2 expose metrics tại :9100/metrics
    └─ CPU usage, memory, disk, network interfaces, ...

[2] Prometheus (EC2 #1) scrape metrics mỗi 15 giây
    └─ Lưu time-series vào /var/lib/prometheus

[3] Prometheus evaluate alert_rules.yml mỗi 15 giây
    └─ Ví dụ: CPU > 70% trong 1 phút → alert HighCPU = FIRING

[4] Alertmanager nhận alert từ Prometheus
    └─ Áp dụng group_wait (30s), group_interval (2m)
    └─ Gửi webhook POST đến AI Agent endpoint /invocations

[5] AI Agent nhận webhook → BatchManager.receive_alert()
    └─ Alert được đưa vào batch theo instance
    └─ Batch timer 5 phút bắt đầu đếm

[6] Sau 5 phút (hoặc trigger thủ công) → LangGraph workflow khởi động

[7] analyze_alerts: LLM tóm tắt danh sách alert trong batch

[8] evaluate_relevance: LLM đánh giá mức độ quan trọng
    ├─ LOW  → generate_report (chỉ ghi chú, không điều tra)
    └─ MEDIUM/HIGH → investigate

[9] investigate: SSH vào EC2 #2, chạy lệnh chẩn đoán
    └─ Lệnh được lọc qua allowlist (config.yaml)
    └─ Ví dụ: top -bn1, free -h, df -h, ps aux --sort=-%cpu

[10] analyze_root_cause: LLM đọc output SSH + knowledge base
     └─ Kết luận nguyên nhân bằng tiếng Việt
     └─ Trả về: root_cause, evidence[], confidence

[11] recommend_fix: LLM đề xuất giải pháp
     └─ immediate: xử lý ngay
     └─ long_term: cải thiện dài hạn
     └─ need_human_approval: hành động cần con người duyệt

[12] generate_report: Format HTML Telegram
     └─ Header (server, thời gian, severity)
     └─ Kết quả SSH (command + 2 dòng output đầu)
     └─ Nguyên nhân + độ tin cậy + bằng chứng
     └─ Khuyến nghị phân loại

[13] send_to_teams: Gửi qua Telegram Bot API
     └─ parse_mode=HTML, tự split nếu > 4096 ký tự
     └─ Retry 3 lần nếu fail
```

### 2.2 Knowledge Base hoạt động thế nào

Trước mỗi lần LLM phân tích, agent load **toàn bộ** file `.md` trong thư mục `knowledge/` và inject vào system prompt:

```
[LLM System Prompt]
  + Bạn là SRE assistant...
  + ### Knowledge: cpu.md
    (nội dung cpu.md)
  + ### Knowledge: ram.md
    (nội dung ram.md)
  + ### Knowledge: disk.md
    ...
  + ### Knowledge: network.md
    ...
  + ### Knowledge: quan_profile.md
    (bất kỳ file nào bạn upload thêm)
```

→ Upload file mới qua Web UI → **agent học ngay**, không cần redeploy.

### 2.3 Phân quyền Chat UI

```
Admin ──► Toàn quyền:
          Chat / Investigate
          Send Alert (test)
          Upload + Xóa Knowledge files
          Tạo / Xóa user accounts

User  ──► Hạn chế:
          Chat / Investigate (chỉ đọc + hỏi)
          Send Alert (test)
          Xem danh sách Knowledge files (không upload/xóa)
```

---

## 3. Yêu cầu chuẩn bị

- **2 EC2 instance** (Ubuntu 22.04 hoặc 24.04) — t2.micro là đủ để test
- **GreenNode account** có quyền deploy AgentBase
- **GreenNode AIP API key** (từ lệnh `/agentbase-llm` trong terminal AgentBase)
- **Telegram account** để tạo bot
- **SSH key pair** (tạo mới hoặc dùng key có sẵn)

---

## Bước 1 — Tạo Telegram Bot

1. Mở Telegram, tìm **@BotFather**
2. Gửi `/newbot` → đặt tên bot → nhận `BOT_TOKEN` (dạng `123456:ABC-xxx`)
3. Tạo group/channel Telegram cho team
4. Thêm bot vào group với quyền **Send Messages**
5. Lấy `CHAT_ID`:
   ```bash
   curl https://api.telegram.org/bot<BOT_TOKEN>/getUpdates
   # Gửi 1 tin nhắn bất kỳ vào group trước, rồi chạy lệnh trên
   # Tìm "chat":{"id": -123456789} → đó là CHAT_ID
   ```
6. Test gửi tin nhắn:
   ```bash
   curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/sendMessage" \
     -d "chat_id=<CHAT_ID>&text=Hello from AI Agent&parse_mode=HTML"
   ```

---

## Bước 2 — Chuẩn bị SSH Key

Agent SSH vào EC2 #2 dùng password (user `monitor`). Cấu hình trong `.env`:

```env
SSH_USERNAME=monitor
SSH_PASSWORD=your_monitor_password   # hoặc dùng private key
SSH_PRIVATE_KEY_PATH=/app/keys/id_rsa  # nếu dùng key
```

> **Lưu ý bảo mật**: Nếu dùng password, chỉ cho phép SSH từ IP của AgentBase runtime. Nếu dùng private key, mount key vào container khi deploy.

---

## Bước 3 — Cấu hình EC2 Target (máy chủ cần giám sát)

EC2 này chạy ứng dụng thực tế và cần:
- **node_exporter** để Prometheus thu thập metrics
- **SSH user `monitor`** để agent SSH vào điều tra

### Cách 1: Dùng User Data (tự động khi launch EC2)

Paste nội dung file `infra/userdata_agent.sh` vào ô **User Data** khi tạo EC2.

> ⚠️ **Trước khi dùng**: Đổi `SSH_PASSWORD` trong file thành password an toàn của bạn.

### Cách 2: Chạy thủ công trên EC2 đã có

```bash
# Cài node_exporter
NE_VERSION="1.7.0"
cd /tmp
wget "https://github.com/prometheus/node_exporter/releases/download/v${NE_VERSION}/node_exporter-${NE_VERSION}.linux-amd64.tar.gz"
tar xf node_exporter-*.tar.gz
sudo cp node_exporter-*/node_exporter /usr/local/bin/

# Tạo user node_exporter
sudo useradd --no-create-home --shell /bin/false node_exporter

# Tạo systemd service
sudo tee /etc/systemd/system/node_exporter.service > /dev/null << 'EOF'
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=node_exporter
ExecStart=/usr/local/bin/node_exporter --web.listen-address=0.0.0.0:9100
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now node_exporter

# Tạo user monitor cho SSH
sudo useradd -m -s /bin/bash monitor
echo "monitor:YOUR_SECURE_PASSWORD" | sudo chpasswd

# Bật SSH password auth
sudo sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
grep -q "^PasswordAuthentication" /etc/ssh/sshd_config || echo "PasswordAuthentication yes" | sudo tee -a /etc/ssh/sshd_config
sudo systemctl restart ssh || sudo systemctl restart sshd
```

### Kiểm tra

```bash
# Từ máy local, kiểm tra node_exporter
curl http://<EC2_TARGET_PUBLIC_IP>:9100/metrics | head -20

# Kiểm tra SSH
ssh monitor@<EC2_TARGET_PUBLIC_IP>
```

### Security Group EC2 Target cần mở

| Port | Protocol | Source | Mục đích |
|------|----------|--------|----------|
| 9100 | TCP | EC2 Monitor IP | Prometheus scrape |
| 22 | TCP | AgentBase Runtime CIDR | Agent SSH điều tra |

---

## Bước 4 — Cấu hình EC2 Monitor (Prometheus + Alertmanager)

EC2 này chạy Prometheus và Alertmanager.

### Cách 1: Dùng User Data

Paste nội dung `infra/userdata_monitor.sh` vào User Data khi tạo EC2.

> ⚠️ **Trước khi dùng**: Cập nhật `AGENT_ENDPOINT` trong file thành endpoint thực của bạn.

### Cách 2: Chạy thủ công

Chạy script `infra/userdata_monitor.sh` trực tiếp trên EC2:

```bash
chmod +x userdata_monitor.sh
sudo ./userdata_monitor.sh
```

### Sau khi EC2 Monitor khởi động — CẬP NHẬT TARGET IP

```bash
# SSH vào EC2 Monitor
ssh ubuntu@<EC2_MONITOR_PUBLIC_IP>

# Sửa prometheus.yml: thay TARGET_EC2_IP thành Private IP của EC2 Target
sudo nano /etc/prometheus/prometheus.yml

# Tìm dòng:
#   targets:
#     - 'TARGET_EC2_IP:9100'
#   labels:
#     instance: 'TARGET_EC2_IP'
#
# Sửa thành (giữ private IP ở targets, public IP ở instance label):
#   targets:
#     - '172.31.x.x:9100'      ← Private IP (để scrape được trong VPC)
#   labels:
#     instance: '54.x.x.x'     ← Public IP (để agent SSH được)

sudo systemctl restart prometheus
```

> **Tại sao phải dùng 2 IP khác nhau?**
> - `targets`: Prometheus scrape qua Private IP (nội bộ VPC, nhanh hơn, không mất phí bandwidth)
> - `instance` label: Agent dùng label này để SSH → phải là Public IP để SSH từ ngoài vào được

### Kiểm tra

```bash
# Prometheus targets
curl http://<EC2_MONITOR_PUBLIC_IP>:9090/api/v1/targets | python3 -m json.tool

# Prometheus UI
open http://<EC2_MONITOR_PUBLIC_IP>:9090

# Alertmanager UI
open http://<EC2_MONITOR_PUBLIC_IP>:9093
```

### Security Group EC2 Monitor cần mở

| Port | Protocol | Source | Mục đích |
|------|----------|--------|----------|
| 9090 | TCP | Your IP | Xem Prometheus UI |
| 9093 | TCP | Your IP | Xem Alertmanager UI |

---

## Bước 5 — Deploy AI Agent lên GreenNode AgentBase

### 5.1 Chuẩn bị file `.env`

```bash
cp .env.example .env
# Điền đầy đủ các giá trị:
```

```env
# LLM (GreenNode AIP)
LLM_MODEL=minimax/minimax-m2.5
LLM_BASE_URL=https://aiplatform.vngcloud.vn/...
LLM_API_KEY=gn-xxxxxxxxxxxxxxxx

# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIxxx
TELEGRAM_CHAT_ID=-1001234567890

# SSH (để connect vào EC2 Target)
SSH_USERNAME=monitor
SSH_PASSWORD=your_monitor_password

# Auth — mật khẩu admin mặc định (đổi ngay sau lần đầu đăng nhập)
ADMIN_DEFAULT_PASSWORD=Admin@SecurePass123
```

> ⚠️ **Không commit `.env` lên git.** File `.gitignore` đã có rule loại trừ `.env`.

### 5.2 Deploy lên AgentBase

```bash
# Trong terminal AgentBase (hoặc Claude Code)
/agentbase-wizard

# Wizard sẽ hỏi:
# - Agent name: ai-alert-rca-agent
# - Dockerfile: Dockerfile (mặc định)
# - Environment variables: paste từ .env
```

Hoặc deploy thủ công:

```bash
# Build Docker image
docker build -t ai-alert-agent .

# Push lên Container Registry của GreenNode
docker tag ai-alert-agent <registry>/ai-alert-agent:latest
docker push <registry>/ai-alert-agent:latest

# Deploy lên AgentBase Runtime
# (theo hướng dẫn của GreenNode AgentBase)
```

### 5.3 Lấy endpoint URL

Sau khi deploy xong, AgentBase trả về URL dạng:
```
https://endpoint-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.agentbase-runtime.aiplatform.vngcloud.vn
```

Lưu URL này — cần dùng cho Alertmanager config và Web UI.

---

## Bước 6 — Kết nối Alertmanager với Agent

SSH vào EC2 Monitor, cập nhật `alertmanager.yml`:

```bash
sudo nano /etc/alertmanager/alertmanager.yml
```

```yaml
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'instance']
  group_wait: 30s          # Đợi 30s để gom alert cùng group
  group_interval: 2m       # Đợi 2m trước khi gửi lại nếu có alert mới
  repeat_interval: 1h      # Không gửi lại cùng alert trong 1h
  receiver: 'ai-agent'

receivers:
  - name: 'ai-agent'
    webhook_configs:
      - url: 'https://<YOUR_AGENT_ENDPOINT>/invocations'
        send_resolved: false   # Chỉ gửi khi alert FIRING, không gửi RESOLVED
        http_config:
          tls_config:
            insecure_skip_verify: true
```

```bash
sudo systemctl restart alertmanager

# Kiểm tra config hợp lệ
amtool check-config /etc/alertmanager/alertmanager.yml
```

---

## Bước 7 — Đăng nhập Web UI & thiết lập ban đầu

### 7.1 Đăng nhập lần đầu

1. Mở trình duyệt: `https://<YOUR_AGENT_ENDPOINT>/`
2. Kiểm tra log container lấy mật khẩu admin mặc định:
   ```
   [AUTH] Default admin created — username: admin | password: Admin@SecurePass123
   ```
3. Đăng nhập: **admin** / password từ log

### 7.2 Thiết lập sau đăng nhập (Admin)

**Tạo tài khoản cho team** → Tab 👥 **Users**:
- Click **➕ Tạo** → Điền username, password, chọn role
- `admin`: Toàn quyền quản lý
- `user`: Chỉ chat và xem

**Upload Knowledge Base** → Tab 📚 **Knowledge Base**:
- Kéo thả file `.md` vào khung upload
- Các file mặc định đã có: `cpu.md`, `ram.md`, `disk.md`, `network.md`
- Thêm kiến thức về hệ thống của bạn: runbook, thông tin service, cấu hình đặc thù

### 7.3 Ví dụ nội dung Knowledge file tùy chỉnh

```markdown
# Thông tin hạ tầng production

## Servers
- payment-api: 54.x.x.x (t3.medium, 4GB RAM)
- auth-service: 54.x.x.y (t3.small, 2GB RAM)
- database: 172.31.x.x (private, chỉ trong VPC)

## Ngưỡng cảnh báo đặc thù
- payment-api CPU > 60% là bất thường (thường < 30%)
- auth-service memory leak xảy ra mỗi ~7 ngày, cần restart

## Liên hệ on-call
- Backend: Quân (SRE lead)
- Database: Bảo
```

---

## Kiểm tra toàn bộ hệ thống

### Test 1: Health check

```bash
curl -X POST https://<AGENT_ENDPOINT>/invocations \
  -H "Content-Type: application/json" \
  -d '{"action": "health"}'

# Expected: {"status": "healthy", "active_batches": 0, ...}
```

### Test 2: Gửi alert giả qua Web UI

1. Tab 🚨 **Send Alert**
2. Alert Name: `HighCPU`
3. Instance: IP của EC2 Target
4. Severity: `warning`
5. Click **Send Alert to Agent**
6. Response: `{"status": "queued", "batch_id": "...", ...}`
7. Sau 5 phút → Telegram nhận báo cáo

### Test 3: Trigger ngay không cần chờ 5 phút

```bash
# Lấy batch_id từ response ở bước trên
curl -X POST https://<AGENT_ENDPOINT>/invocations \
  -H "Content-Type: application/json" \
  -d '{"action": "trigger_batch", "batch_id": "<batch_id>", "token": "<your_token>"}'
```

### Test 4: Stress test EC2 Target (trigger alert thực)

```bash
# SSH vào EC2 Target
ssh monitor@<EC2_TARGET_PUBLIC_IP>

# Stress CPU (5 phút)
stress-ng --cpu 2 --timeout 300s &

# Sau ~1 phút → Prometheus detect HighCPU → Alertmanager gửi webhook → Agent nhận
```

### Test 5: Chat investigate qua Web UI

1. Tab 💬 **Chat / Investigate**
2. Nhắn: `kiểm tra CPU trên <EC2_TARGET_IP>`
3. Agent SSH và trả về kết quả ngay (không qua batch/Telegram)

---

## Xử lý sự cố thường gặp

### Agent không nhận được alert từ Alertmanager

```bash
# Kiểm tra Alertmanager đang gửi đúng chưa
curl http://<EC2_MONITOR_IP>:9093/api/v2/alerts

# Test webhook trực tiếp
curl -X POST https://<AGENT_ENDPOINT>/invocations \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [{
      "status": "firing",
      "labels": {"alertname": "TestAlert", "instance": "1.2.3.4", "severity": "warning"},
      "annotations": {"description": "Test alert"}
    }]
  }'
```

### SSH không thực hiện được (output rỗng hoặc lỗi)

```bash
# Kiểm tra agent có SSH được vào target không
# Từ máy local test trước:
ssh monitor@<TARGET_IP>

# Nếu OK nhưng agent vẫn lỗi → kiểm tra:
# 1. SSH_USERNAME và SSH_PASSWORD trong .env có đúng không?
# 2. Instance label trong prometheus.yml có phải Public IP không?
# 3. Security Group EC2 Target có mở port 22 từ AgentBase IP không?
```

### Báo cáo Telegram không gửi được

```bash
# Test trực tiếp Telegram API
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>&text=Test&parse_mode=HTML"

# Kiểm tra TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID trong .env
# CHAT_ID của group phải có dấu trừ: -1001234567890
```

### LLM trả về lỗi 401

```bash
# Kiểm tra LLM_API_KEY trong .env không có dấu ngoặc kép
# SAI:  LLM_API_KEY="gn-xxx"
# ĐÚNG: LLM_API_KEY=gn-xxx

# Kiểm tra key còn hạn
curl https://<LLM_BASE_URL>/models \
  -H "Authorization: Bearer <LLM_API_KEY>"
```

### Alert luôn bị đánh giá LOW relevance

Kiểm tra `config.yaml`:
```yaml
system_context:
  critical_environments:
    - prod
    - production
    - unknown    # ← Đảm bảo có "unknown" để xử lý alert không có env label
  critical_services:
    - ""         # ← Đảm bảo có "" để xử lý alert không có service label
```

### Web UI hiện login loop (đăng nhập xong lại bị đá ra)

Session lưu trong memory — **restart container làm mất toàn bộ session**. Đây là behavior bình thường. Đăng nhập lại là được.

Nếu vẫn không login được → kiểm tra file `data/users.json` trong container:
```bash
docker exec -it <container_id> cat /app/data/users.json
```

---

## Tóm tắt checklist triển khai

- [ ] Tạo Telegram Bot, lấy `BOT_TOKEN` và `CHAT_ID`
- [ ] Launch EC2 #2 (Target) với `userdata_agent.sh`
- [ ] Xác nhận `node_exporter` chạy ở `:9100` và SSH `monitor@` hoạt động
- [ ] Launch EC2 #1 (Monitor) với `userdata_monitor.sh`
- [ ] Cập nhật `prometheus.yml`: `targets` = Private IP, `instance` label = Public IP
- [ ] Restart Prometheus, xác nhận target UP
- [ ] Tạo `.env` với đầy đủ `LLM_*`, `TELEGRAM_*`, `SSH_*`, `ADMIN_DEFAULT_PASSWORD`
- [ ] Deploy agent lên AgentBase, lấy endpoint URL
- [ ] Cập nhật `alertmanager.yml` với endpoint mới, restart Alertmanager
- [ ] Mở Web UI, đăng nhập admin, đổi mật khẩu
- [ ] Tạo tài khoản cho team members
- [ ] Upload knowledge files đặc thù của hệ thống
- [ ] Chạy stress test → xác nhận Telegram nhận báo cáo RCA
