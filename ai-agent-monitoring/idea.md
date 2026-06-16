# Yêu cầu xây dựng AI Agent phân tích Alert và Root Cause Analysis

## 1. Mục tiêu

Xây dựng một AI Agent có nhiệm vụ tự động tiếp nhận alert từ hệ thống giám sát, phân tích ý nghĩa của alert, đăng nhập vào instance/server liên quan để kiểm tra bằng command line, xác định root cause, đánh giá mức độ quan trọng, đề xuất hướng xử lý, sau đó gửi report ngắn gọn về Microsoft Teams thông qua webhook.

Agent cần tránh spam thông báo bằng cách gom các alert phát sinh gần nhau thành batch trong một khoảng thời gian quan sát 10 phút trước khi xử lý.

---

## 2. Bối cảnh hoạt động

Hệ thống hiện tại có thể là on-premise, cloud hoặc hybrid. Không phải mọi alert đều có cùng mức độ quan trọng. Agent cần có khả năng phân tích ngữ cảnh hệ thống để quyết định alert có cần report chi tiết hay chỉ cần note đơn giản.

Ví dụ:

- Nếu hệ thống đang vận hành on-premise, các alert liên quan trực tiếp đến dịch vụ cloud không ảnh hưởng đến hệ thống hiện tại có thể được đánh dấu là `low relevance` và chỉ cần ghi chú ngắn.
- Nếu alert liên quan đến CPU, RAM, disk, network, process chết, service unavailable, database connection, latency hoặc error rate tăng cao trên instance production thì cần phân tích kỹ và report đầy đủ.

---

## 3. Luồng xử lý tổng quan

### 3.1. Trigger khi có alert

Agent được kích hoạt khi nhận được alert từ hệ thống giám sát.

Nguồn alert có thể là một trong các dạng sau:

- Webhook từ monitoring system.
- Message từ alert manager.
- Event queue.
- API polling từ monitoring platform.

Mỗi alert đầu vào tối thiểu cần có các thông tin sau:

```json
{
  "alert_id": "string",
  "alert_name": "string",
  "severity": "critical | warning | info",
  "instance": "hostname or ip",
  "service": "string",
  "environment": "prod | staging | dev",
  "timestamp": "ISO-8601 datetime",
  "description": "string",
  "labels": {},
  "annotations": {},
  "metrics_url": "optional string"
}
```

---

### 3.2. Batch window 10 phút để tránh spam

Khi nhận alert đầu tiên, Agent không xử lý ngay lập tức mà bắt đầu một cửa sổ quan sát 10 phút.

Trong 10 phút này:

- Nếu có thêm alert mới liên quan đến cùng instance, service hoặc cùng nhóm hạ tầng, Agent gom các alert đó vào cùng một batch.
- Nếu không có alert mới, Agent xử lý alert ban đầu như một batch chỉ có một alert.
- Sau khi hết 10 phút, Agent bắt đầu phân tích toàn bộ batch.

Mục tiêu:

- Tránh gửi nhiều report rời rạc cho cùng một sự cố.
- Cho phép Agent nhìn được bức tranh tổng thể thay vì phân tích từng alert riêng lẻ.
- Giảm noise trên Microsoft Teams.

Gợi ý grouping rule:

```text
Group alert vào cùng batch nếu một trong các điều kiện sau đúng:
- Cùng instance.
- Cùng service.
- Cùng cluster/application.
- Cùng alert fingerprint từ monitoring system.
- Alert xảy ra trong vòng 10 phút kể từ alert đầu tiên của batch.
```

---

## 4. Nhiệm vụ chi tiết của Agent

### 4.1. Đọc và hiểu alert

Agent cần phân tích nội dung alert để trả lời các câu hỏi:

- Alert này nói về vấn đề gì?
- Alert liên quan đến instance/service nào?
- Severity là gì?
- Đây là alert về tài nguyên, network, application, database, service, filesystem, hay dependency bên ngoài?
- Alert có khả năng ảnh hưởng đến user hoặc hệ thống production không?

Kết quả mong muốn:

```text
Alert Summary:
- Alert name: HighCPUUsage
- Instance: app-01
- Service: payment-api
- Severity: warning
- Meaning: CPU usage trên instance app-01 vượt ngưỡng trong một khoảng thời gian nhất định.
```

---

### 4.2. Đánh giá mức độ liên quan và độ quan trọng

Agent cần đánh giá alert có quan trọng với hệ thống hiện tại hay không.

Các yếu tố cần xét:

- Environment: production, staging, dev.
- Service có nằm trong danh sách critical service không.
- Instance có đang phục vụ traffic thật không.
- Alert có lặp lại nhiều lần không.
- Có nhiều alert liên quan cùng lúc không.
- Loại hạ tầng hiện tại: on-premise, cloud, hybrid.
- Alert có liên quan trực tiếp đến hệ thống hiện tại không.

Output gợi ý:

```text
Impact Assessment:
- Relevance: High | Medium | Low
- Impact: Critical | Major | Minor | Informational
- Reason: Alert xảy ra trên production instance thuộc payment-api, là service critical.
```

Nếu alert ít liên quan:

```text
Relevance: Low
Reason: Alert liên quan đến cloud load balancer nhưng hệ thống hiện tại đang chạy on-premise và không route traffic qua cloud load balancer này.
Action: Chỉ note đơn giản, không cần RCA sâu.
```

---

### 4.3. Đăng nhập server để kiểm tra

Sau khi xác định alert cần phân tích, Agent dùng account/credential được cung cấp để đăng nhập vào server liên quan.

Yêu cầu bảo mật:

- Không hardcode username/password/token trong source code.
- Dùng secret manager, environment variables hoặc encrypted config.
- Không in credential ra log hoặc report.
- Command execution phải có timeout.
- Chỉ chạy command trong allowlist để tránh rủi ro.
- Ghi lại command đã chạy nhưng không ghi sensitive output.

Các phương thức hỗ trợ:

- SSH bằng key.
- SSH bằng username/password nếu bắt buộc.
- Bastion host nếu cần.
- Kubernetes exec nếu instance là pod/container.

---

### 4.4. Kiểm tra bằng command line

Agent cần chọn command phù hợp theo loại alert.

#### CPU alert

```bash
top -b -n 1 | head -n 30
ps aux --sort=-%cpu | head -n 15
uptime
mpstat 1 5
```

#### Memory alert

```bash
free -m
vmstat 1 5
ps aux --sort=-%mem | head -n 15
dmesg | tail -n 50
```

#### Disk alert

```bash
df -h
du -sh /var/log/* 2>/dev/null | sort -h | tail -n 20
lsblk
inode_status=$(df -ih)
echo "$inode_status"
```

#### Network alert

```bash
ss -tulpen
ss -s
ip addr
ip route
ping -c 4 8.8.8.8
```

#### Service down alert

```bash
systemctl status <service_name> --no-pager
journalctl -u <service_name> -n 100 --no-pager
ps aux | grep <service_name>
```

#### Application error alert

```bash
journalctl -n 100 --no-pager
tail -n 200 /var/log/<app>/<app>.log
grep -i "error\|exception\|timeout\|failed" /var/log/<app>/<app>.log | tail -n 50
```

#### Container/Kubernetes alert

```bash
kubectl get pods -n <namespace> -o wide
kubectl describe pod <pod_name> -n <namespace>
kubectl logs <pod_name> -n <namespace> --tail=200
kubectl top pod <pod_name> -n <namespace>
```

Agent cần tự map loại alert sang bộ command tương ứng.

---

### 4.5. Curl metrics để xem trend

Nếu alert có metrics endpoint hoặc monitoring API, Agent có thể dùng curl để lấy thông số trend.

Ví dụ:

```bash
curl -s "<metrics_url>"
curl -s "http://<instance>:9100/metrics"
curl -s "http://<prometheus>/api/v1/query?query=<promql_query>"
```

Agent cần phân tích trend như:

- Metric tăng đột biến hay tăng từ từ.
- Có recovery chưa.
- Có tương quan với alert khác không.
- Vấn đề xảy ra một lần hay lặp lại.
- Ngưỡng alert có hợp lý không.

Ví dụ output:

```text
Metric Trend:
- CPU tăng từ 45% lên 96% trong 8 phút.
- Sau đó giảm về 62% sau khi process batch-job kết thúc.
- Pattern giống spike tạm thời, chưa thấy dấu hiệu kéo dài.
```

---

### 4.6. Xác định root cause

Agent cần tổng hợp dữ liệu từ:

- Alert payload.
- Các alert khác trong batch.
- Command output từ server.
- Metrics trend.
- Log hệ thống hoặc application.
- Ngữ cảnh service/environment.

Sau đó đưa ra root cause ở mức tự tin phù hợp.

Output gợi ý:

```text
Root Cause:
- Probable root cause: Process java của payment-api dùng CPU cao bất thường.
- Evidence:
  - ps aux cho thấy java process PID 1234 dùng 280% CPU.
  - CPU metric tăng mạnh trong cùng thời điểm alert trigger.
  - Log ghi nhận lượng request tăng đột biến từ 10:12 đến 10:19.
- Confidence: Medium
```

Nếu chưa đủ dữ liệu:

```text
Root Cause:
- Unable to confirm exact root cause.
- Most likely cause: Disk usage tăng do log file application phát sinh lớn.
- Evidence:
  - /var/log/app chiếm 85GB.
  - df -h cho thấy / partition đạt 94%.
- Missing data:
  - Chưa có log rotation config.
  - Chưa có application deployment history.
- Confidence: Medium
```

---

### 4.7. Đề xuất phương pháp fix

Agent cần đề xuất hướng xử lý an toàn, ưu tiên không tự động thay đổi hệ thống production trừ khi được cho phép rõ ràng.

Phân loại đề xuất:

#### Immediate mitigation

Các bước giảm ảnh hưởng ngay:

- Restart service nếu service bị treo và runbook cho phép.
- Clear log tạm thời nếu disk full, nhưng phải ưu tiên compress/archive thay vì delete trực tiếp.
- Scale thêm instance/pod nếu traffic tăng.
- Kill process bất thường nếu process đó không critical và có xác nhận rule.

#### Long-term fix

Các cải tiến lâu dài:

- Tối ưu application query hoặc code path gây CPU cao.
- Cấu hình log rotation.
- Tăng disk capacity.
- Điều chỉnh alert threshold.
- Thêm autoscaling.
- Tách workload batch job khỏi production instance.

#### Need human review

Các trường hợp cần người vận hành xác nhận:

- Root cause chưa rõ.
- Có nguy cơ mất dữ liệu.
- Cần restart service critical.
- Cần thay đổi cấu hình production.
- Alert liên quan database, storage hoặc network core.

---

## 5. Report gửi về Microsoft Teams

Agent gửi report qua Microsoft Teams webhook sau khi xử lý xong batch.

Report cần ngắn gọn, dễ đọc, có đủ thông tin hành động.

### 5.1. Format report đề xuất

```markdown
## Alert RCA Report

**Status:** Investigated
**Batch Window:** 2026-01-01 10:00:00 - 2026-01-01 10:10:00
**Environment:** production
**Affected Instance:** app-01
**Affected Service:** payment-api
**Severity:** warning
**Relevance:** high

### 1. Alert Summary
- HighCPUUsage triggered on app-01.
- CPU usage exceeded threshold for more than 5 minutes.
- Related alerts in batch: 3

### 2. Impact Assessment
- Impact: Major
- Reason: payment-api is a production critical service.
- User impact: Possible latency increase.

### 3. Investigation
- Checked CPU, memory, process list and service logs.
- Top CPU process: java PID 1234 using 280% CPU.
- Metrics show CPU spike from 45% to 96% within 8 minutes.

### 4. Probable Root Cause
Batch job triggered high CPU on the same instance while payment-api was serving production traffic.

Confidence: Medium

### 5. Recommended Fix
Immediate:
- Move batch job away from production API instance.
- Consider scaling payment-api if latency increases.

Long-term:
- Separate batch workload from API workload.
- Add resource limits.
- Review alert threshold and autoscaling policy.

### 6. Notes
No automatic remediation was executed.
```

---

### 5.2. Teams webhook payload

Agent cần gửi message tới Teams bằng incoming webhook.

Ví dụ payload đơn giản:

```json
{
  "text": "## Alert RCA Report\n\n**Status:** Investigated\n**Affected Instance:** app-01\n**Root Cause:** CPU spike caused by batch job.\n**Recommended Fix:** Move batch job away from production API instance."
}
```

Nếu dùng Adaptive Card, cần tạo module riêng để render report đẹp hơn.

---

## 6. Kiến trúc đề xuất

### 6.1. Thành phần chính

```text
Monitoring System
    |
    v
Alert Receiver API
    |
    v
Batch Manager / Deduplication Layer
    |
    v
Alert Analyzer
    |
    v
Context & Relevance Evaluator
    |
    v
Investigation Orchestrator
    |-- SSH Executor
    |-- Metrics Collector
    |-- Log Collector
    |-- Kubernetes Executor
    |
    v
Root Cause Analyzer
    |
    v
Fix Recommendation Engine
    |
    v
Report Generator
    |
    v
Microsoft Teams Webhook Sender
```

---

### 6.2. Module cần implement

#### `AlertReceiver`

Nhiệm vụ:

- Nhận alert payload.
- Validate payload.
- Normalize dữ liệu alert về format chung.
- Đẩy alert vào batch queue.

#### `BatchManager`

Nhiệm vụ:

- Tạo batch khi có alert mới.
- Chờ 10 phút trước khi xử lý.
- Gom alert liên quan vào cùng batch.
- Tránh xử lý trùng alert.

#### `AlertAnalyzer`

Nhiệm vụ:

- Phân tích alert name, description, labels, annotations.
- Xác định loại alert.
- Xác định instance/service/environment.
- Tạo summary ban đầu.

#### `RelevanceEvaluator`

Nhiệm vụ:

- Đánh giá alert có quan trọng không.
- So sánh alert với context hệ thống.
- Phân loại relevance: `high`, `medium`, `low`.
- Nếu relevance thấp, tạo note ngắn thay vì RCA sâu.

#### `InvestigationOrchestrator`

Nhiệm vụ:

- Chọn loại investigation phù hợp.
- Gọi SSH executor, metrics collector hoặc Kubernetes executor.
- Thu thập output.
- Áp timeout và error handling.

#### `SSHExecutor`

Nhiệm vụ:

- Đăng nhập server bằng credential được cung cấp.
- Chạy command theo allowlist.
- Trả output đã sanitize.
- Không log secret.

#### `MetricsCollector`

Nhiệm vụ:

- Curl endpoint metrics nếu có.
- Query Prometheus hoặc monitoring API nếu được cấu hình.
- Tóm tắt trend.

#### `RootCauseAnalyzer`

Nhiệm vụ:

- Tổng hợp dữ liệu.
- Xác định root cause hoặc probable root cause.
- Đưa ra evidence.
- Đưa ra confidence level.

#### `FixRecommendationEngine`

Nhiệm vụ:

- Đề xuất immediate mitigation.
- Đề xuất long-term fix.
- Xác định action nào cần human approval.

#### `TeamsReporter`

Nhiệm vụ:

- Format report.
- Gửi report qua Microsoft Teams webhook.
- Retry nếu gửi thất bại.
- Không gửi quá nhiều report cho cùng một batch.

---

## 7. Cấu hình đề xuất

Agent cần có file config, ví dụ `config.yaml`:

```yaml
agent:
  batch_window_minutes: 10
  command_timeout_seconds: 20
  max_alerts_per_batch: 50
  default_confidence_threshold: medium

system_context:
  infrastructure_type: on_premise
  critical_environments:
    - prod
  critical_services:
    - payment-api
    - auth-service
    - database
    - gateway
  low_relevance_keywords:
    - cloud load balancer
    - aws autoscaling
    - gcp cloud run
    - azure app service

teams:
  webhook_url_env: TEAMS_WEBHOOK_URL

ssh:
  username_env: SSH_USERNAME
  private_key_path_env: SSH_PRIVATE_KEY_PATH
  bastion_host_env: BASTION_HOST
  allowed_commands:
    - uptime
    - free -m
    - df -h
    - df -ih
    - top -b -n 1
    - ps aux
    - vmstat
    - mpstat
    - ss
    - ip addr
    - ip route
    - systemctl status
    - journalctl
    - tail
    - grep

metrics:
  prometheus_url_env: PROMETHEUS_URL
  allow_direct_instance_metrics: true
```

---

## 8. Yêu cầu bảo mật

- Không lưu plain-text password trong repository.
- Không gửi credential vào Teams report.
- Không expose command output chứa token, password, private key hoặc connection string.
- Cần sanitize output trước khi log/report.
- Chỉ cho phép command trong allowlist.
- Command nguy hiểm cần bị chặn, ví dụ:
  - `rm -rf`
  - `mkfs`
  - `dd`
  - `reboot`
  - `shutdown`
  - `kill -9` nếu chưa có approval rule
  - thay đổi firewall/routing nếu chưa có approval
- Mọi action remediation tự động phải tắt mặc định.
- Agent chỉ được recommend fix, không tự fix production nếu chưa bật chế độ auto-remediation.

---

## 9. Error handling

Agent cần xử lý các trường hợp lỗi:

- Không SSH được vào server.
- Credential sai hoặc hết hạn.
- Command timeout.
- Metrics endpoint không phản hồi.
- Payload alert thiếu thông tin.
- Teams webhook lỗi.
- Có quá nhiều alert trong một batch.
- Alert không map được instance/service.

Report vẫn cần được gửi nếu investigation không hoàn chỉnh, ví dụ:

```text
Investigation Status: Partial
Reason: Cannot SSH to app-01 due to authentication failure.
Available evidence: Alert payload and metrics trend only.
Recommended action: Check SSH credential or server access path.
```

---

## 10. Logging và audit

Agent cần log các thông tin sau:

- Alert received time.
- Batch ID.
- Alert IDs trong batch.
- Instance/service liên quan.
- Command đã chạy.
- Command status: success, failed, timeout.
- Report sent status.
- Root cause confidence.

Không log:

- Password.
- Token.
- Private key.
- Full environment variables.
- Secret trong command output.

---

## 11. Output mong muốn của Agent

Với mỗi batch, Agent cần tạo object kết quả có cấu trúc:

```json
{
  "batch_id": "string",
  "status": "investigated | partial | skipped | failed",
  "alerts": [],
  "summary": "string",
  "relevance": "high | medium | low",
  "impact": "critical | major | minor | informational",
  "investigation_steps": [],
  "evidence": [],
  "root_cause": "string",
  "confidence": "high | medium | low",
  "recommended_fix": {
    "immediate": [],
    "long_term": [],
    "need_human_approval": []
  },
  "teams_report_sent": true
}
```

---

## 12. Acceptance Criteria

Claude Code cần build hệ thống thỏa các tiêu chí sau:

1. Agent nhận được alert qua API/webhook.
2. Agent normalize alert payload về schema chung.
3. Khi alert đầu tiên trigger, Agent chờ 10 phút để gom các alert liên quan.
4. Sau 10 phút, Agent xử lý batch thay vì xử lý từng alert riêng lẻ.
5. Agent phân tích alert để xác định alert nói về vấn đề gì.
6. Agent đánh giá relevance và impact dựa trên environment, service và system context.
7. Nếu alert relevance thấp, Agent chỉ tạo note ngắn và không RCA sâu.
8. Nếu alert cần phân tích, Agent đăng nhập server bằng credential được cấu hình an toàn.
9. Agent chạy command phù hợp với loại alert.
10. Agent có thể curl metrics endpoint hoặc query Prometheus để xem trend nếu có cấu hình.
11. Agent tổng hợp evidence và đưa ra probable root cause.
12. Agent đề xuất immediate mitigation và long-term fix.
13. Agent gửi report ngắn gọn về Microsoft Teams webhook.
14. Agent không in credential hoặc secret ra log/report.
15. Agent có command allowlist và timeout.
16. Agent xử lý được lỗi SSH, lỗi metrics, lỗi Teams webhook và payload thiếu thông tin.
17. Agent có log/audit cho từng batch.
18. Auto-remediation phải tắt mặc định, chỉ recommend fix trừ khi có cấu hình explicit.

---

## 13. Gợi ý công nghệ

Có thể triển khai bằng một trong các stack sau:

### Option A: Python

- FastAPI cho Alert Receiver API.
- Celery/RQ/Redis hoặc APScheduler cho batch window.
- Paramiko hoặc AsyncSSH cho SSH.
- Requests/httpx cho Teams webhook và metrics API.
- Pydantic cho schema validation.
- LangChain/LlamaIndex hoặc SDK LLM trực tiếp cho reasoning nếu cần.

### Option B: Node.js/TypeScript

- Express/NestJS cho API.
- BullMQ/Redis cho batch queue.
- ssh2 cho SSH.
- axios/fetch cho webhook và metrics.
- zod cho schema validation.
- OpenAI/Anthropic SDK cho reasoning nếu cần.

Ưu tiên build theo hướng modular, dễ test, dễ thay LLM provider.

---

## 14. Đề xuất cấu trúc thư mục

```text
alert-rca-agent/
├── src/
│   ├── main.py
│   ├── config.py
│   ├── models/
│   │   ├── alert.py
│   │   ├── batch.py
│   │   └── report.py
│   ├── receivers/
│   │   └── webhook_receiver.py
│   ├── batching/
│   │   └── batch_manager.py
│   ├── analyzers/
│   │   ├── alert_analyzer.py
│   │   ├── relevance_evaluator.py
│   │   ├── root_cause_analyzer.py
│   │   └── fix_recommender.py
│   ├── executors/
│   │   ├── ssh_executor.py
│   │   ├── k8s_executor.py
│   │   └── command_policy.py
│   ├── metrics/
│   │   └── metrics_collector.py
│   ├── reporters/
│   │   └── teams_reporter.py
│   ├── security/
│   │   └── sanitizer.py
│   └── utils/
│       └── logger.py
├── tests/
├── config.example.yaml
├── README.md
└── requirements.txt
```

---

## 15. Prompt nội bộ cho LLM reasoning

Nếu dùng LLM để phân tích, có thể dùng system prompt như sau:

```text
You are an SRE assistant agent. Your job is to analyze monitoring alerts, server command outputs, metrics trends, and logs to identify probable root cause and recommend safe remediation steps.

Rules:
- Never expose credentials, tokens, passwords, private keys, or secrets.
- Do not recommend destructive commands unless explicitly marked as requiring human approval.
- If evidence is incomplete, say so clearly.
- Always provide confidence level: high, medium, or low.
- Distinguish between immediate mitigation and long-term fix.
- If the alert is not relevant to the current infrastructure context, mark it as low relevance and provide only a short note.
- Prefer safe, reversible actions.
- Do not claim certainty without evidence.
```

---

## 16. Ví dụ end-to-end

### Input alert

```json
{
  "alert_id": "a-001",
  "alert_name": "HighDiskUsage",
  "severity": "warning",
  "instance": "app-01",
  "service": "payment-api",
  "environment": "prod",
  "timestamp": "2026-01-01T10:00:00Z",
  "description": "Disk usage on / is above 90%",
  "labels": {
    "mountpoint": "/"
  },
  "annotations": {
    "summary": "Disk usage is high on app-01"
  }
}
```

### Investigation result

```text
Commands executed:
- df -h
- df -ih
- du -sh /var/log/* | sort -h | tail -n 20

Evidence:
- / partition usage is 94%.
- /var/log/payment-api occupies 78GB.
- inode usage is normal.
```

### Teams report

```markdown
## Alert RCA Report

**Status:** Investigated
**Affected Instance:** app-01
**Affected Service:** payment-api
**Severity:** warning
**Relevance:** high
**Impact:** major

### Summary
Disk usage on `/` exceeded 90%.

### Root Cause
Application logs under `/var/log/payment-api` are consuming most of the disk space.

Confidence: High

### Evidence
- `/` usage: 94%.
- `/var/log/payment-api`: 78GB.
- Inode usage is normal.

### Recommended Fix
Immediate:
- Compress/archive old application logs.
- Verify log rotation config.

Long-term:
- Configure logrotate for payment-api.
- Add disk usage forecast alert.
- Consider increasing disk size if log volume is expected.

### Notes
No automatic remediation was executed.
```

---

## 17. Yêu cầu cuối cùng cho Claude Code

Hãy implement AI Agent theo spec trên.

Ưu tiên:

1. Thiết kế modular, dễ mở rộng.
2. Có config rõ ràng.
3. Có unit test cho các module quan trọng.
4. Có mock mode để test mà không cần SSH thật.
5. Có sample alert payload.
6. Có sample Teams report.
7. Có README hướng dẫn chạy local.
8. Không hardcode secret.
9. Auto-remediation tắt mặc định.
10. Report phải ngắn gọn, dễ đọc và hữu ích cho SRE/on-call.