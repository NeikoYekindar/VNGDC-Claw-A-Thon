# Network Alert Knowledge Base

## Các ngưỡng cảnh báo Network

| Chỉ số | Ngưỡng | Mức độ | Hành động |
|--------|--------|--------|-----------|
| Packet loss | > 1% | Warning | Kiểm tra đường truyền, switch/router |
| Packet loss | > 5% | Critical | Điều tra ngay, có thể mất kết nối |
| Network latency | > 100ms | Warning | Kiểm tra congestion, routing |
| Network latency | > 500ms | Critical | Service degraded, user impact |
| Bandwidth usage | > 80% | Warning | Nguy cơ nghẽn mạng |
| TCP retransmit rate | > 1% | Warning | Packet loss hoặc network congestion |
| Connection refused | Liên tục | Critical | Service down hoặc firewall block |
| TIME_WAIT connections | > 10000 | Warning | Cần tune TCP keepalive/timeout |

## Nguyên nhân phổ biến

### Packet loss / Latency cao
- Network congestion do bandwidth đầy (đặc biệt giờ cao điểm)
- NIC (Network Interface Card) bị lỗi hoặc driver issue
- Switch/router quá tải
- MTU mismatch gây fragmentation
- AWS/cloud provider network issue (kiểm tra AWS Health Dashboard)

### Connection timeout / refused
- Service bị crash hoặc restart
- Firewall rule chặn kết nối (Security Group, iptables)
- Port bị bind sai hoặc không listen
- Quá nhiều connections làm exhausted file descriptors (ulimit)
- TCP backlog đầy (net.core.somaxconn thấp)

### Bandwidth cao bất thường
- DDoS hoặc traffic spike do marketing campaign
- Backup/restore đang chạy
- Log shipping hoặc database replication lag
- Malware hoặc crypto mining (rare)
- Ứng dụng có memory leak gây retry storm

### DNS issues
- DNS resolution chậm gây timeout cascade
- DNS server quá tải hoặc down
- TTL cache miss do deploy thay đổi IP

## Các lệnh điều tra

```bash
# Tổng quan network interface
ip -s link show
ifconfig -a

# Kiểm tra kết nối hiện tại
ss -tuln          # listening ports
ss -tupn          # kết nối đang mở với PID
netstat -s        # thống kê TCP/UDP errors

# Đếm connections theo state
ss -tan | awk '{print $1}' | sort | uniq -c | sort -rn

# Kiểm tra packet loss
ping -c 20 8.8.8.8
ping -c 20 <gateway_ip>

# Theo dõi network traffic real-time
iftop -i eth0 -n 2>/dev/null
nload eth0 2>/dev/null
nethogs 2>/dev/null

# Kiểm tra bandwidth usage
cat /proc/net/dev
vnstat -h 2>/dev/null

# Kiểm tra TCP retransmits
ss -s
cat /proc/net/snmp | grep -i retrans

# Kiểm tra firewall rules
iptables -L -n -v 2>/dev/null
nft list ruleset 2>/dev/null

# Kiểm tra routing
ip route show
traceroute -n <target_ip>

# Kiểm tra DNS
dig @8.8.8.8 <hostname>
resolvectl status 2>/dev/null
cat /etc/resolv.conf

# Kiểm tra file descriptors (liên quan đến max connections)
ulimit -n
cat /proc/sys/net/core/somaxconn
ss -s | grep -i estab
```

## Hướng xử lý

### Immediate mitigation
- **Nếu packet loss / latency cao**: ping test đến gateway + các instance khác để xác định phạm vi
- **Nếu connection refused**: kiểm tra service có đang chạy không (`systemctl status <service>`, `ss -tlnp`)
- **Nếu bandwidth đầy**: dùng `iftop` hoặc `nethogs` tìm process/IP đang dùng bandwidth nhiều nhất
- **Nếu DNS lỗi**: thử `dig @8.8.8.8` để bypass local DNS, xem kết quả trả về
- **Nếu quá nhiều TIME_WAIT**: tạm thời bật `tcp_tw_reuse`:
  ```bash
  sysctl -w net.ipv4.tcp_tw_reuse=1  # CẦN XÁC NHẬN
  ```

### Long-term fix
- Cấu hình TCP keepalive và timeout phù hợp với workload
- Tăng ulimit file descriptors (`/etc/security/limits.conf`)
- Cấu hình `net.core.somaxconn` và `net.ipv4.tcp_backlog` cao hơn cho high-traffic service
- Dùng connection pooling (PgBouncer, HAProxy) thay vì direct connection
- Thiết lập monitoring bandwidth trend để phát hiện tăng bất thường sớm
- Cân nhắc CDN cho static assets nếu bandwidth quá cao
- Dùng AWS VPC Flow Logs hoặc cloud-native network monitoring

## Phân biệt lỗi network nội bộ vs. external

| Triệu chứng | Khả năng nội bộ | Khả năng external |
|-------------|-----------------|-------------------|
| Chỉ lỗi 1 instance | Cao | Thấp |
| Nhiều instance cùng lúc | Thấp | Cao |
| Ping gateway OK, ping 8.8.8.8 fail | — | ISP/uplink issue |
| Cả gateway fail | Switch/router nội bộ | — |
| Chỉ lỗi theo region | — | Cloud provider issue |

## Infrastructure context
<!-- Điền thông tin hệ thống cụ thể của bạn -->
<!-- Ví dụ: -->
<!-- - Primary interface: eth0, MTU 9001 (jumbo frames trên AWS) -->
<!-- - Gateway: 172.31.0.1 -->
<!-- - DNS: 172.31.0.2 (AWS VPC DNS) -->
<!-- - Bandwidth limit: 1 Gbps (instance type t3.medium) -->
<!-- - Security Group: allow 22, 80, 443, 9100 từ VPC CIDR -->
