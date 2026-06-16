# RAM / Memory Alert Knowledge Base

## Các ngưỡng cảnh báo Memory

| Ngưỡng | Mức độ | Hành động |
|--------|--------|-----------|
| Used > 80% | Warning | Monitor, kiểm tra memory leak |
| Used > 90% | Critical | Điều tra ngay, có nguy cơ OOM |
| Swap used > 20% | Warning | RAM đang thiếu, hệ thống đang swap |
| Swap used > 50% | Critical | Performance giảm nghiêm trọng |
| OOMKiller xuất hiện trong log | Critical | Process đã bị kill do hết RAM |

## Nguyên nhân phổ biến

### Memory leak
- Application không giải phóng memory sau khi xử lý xong request
- Connection pool không được đóng đúng cách
- Cache không có TTL hoặc size limit
- JVM heap quá lớn hoặc không được tuning

### Memory tăng đột biến
- Traffic spike dẫn đến nhiều request đồng thời
- Load test hoặc DDoS
- File upload lớn được đọc vào memory

### Swap cao
- RAM thực sự thiếu, OS phải dùng disk làm RAM tạm
- Dẫn đến I/O cao và performance giảm mạnh

## Các lệnh điều tra

```bash
# Tổng quan memory
free -m
free -h

# Chi tiết memory usage theo process
ps aux --sort=-%mem | head -n 15

# Memory theo thời gian (5 samples, 1 giây/lần)
vmstat 1 5

# Kiểm tra OOMKiller
dmesg | grep -i "oom\|killed process" | tail -n 20
journalctl -k | grep -i oom | tail -n 20

# Kiểm tra memory của từng process
cat /proc/<PID>/status | grep VmRSS

# Kiểm tra shared memory và buffers
cat /proc/meminfo

# Kiểm tra memory leak theo thời gian (chạy nhiều lần)
ps -o pid,rss,comm -p <PID>
```

## Hướng xử lý

### Immediate mitigation
- Nếu có OOMKiller: xác định process nào bị kill, restart nếu cần
- Nếu memory leak: restart service (short-term fix, cần long-term fix)
- Nếu swap cao: xem xét giảm tải hoặc thêm RAM
- Clear cache nếu phần lớn memory là cache không cần thiết: `sync && echo 3 > /proc/sys/vm/drop_caches` (cần xác nhận)

### Long-term fix
- Tăng RAM instance nếu workload thật sự cần
- Tối ưu memory usage trong application code
- Cấu hình JVM heap size phù hợp (-Xmx, -Xms)
- Thêm memory limit cho container/service
- Cấu hình memory alert ở ngưỡng sớm hơn (70%) để có thời gian phản ứng
- Review connection pool size

## Infrastructure context
<!-- Điền thông tin hệ thống cụ thể của bạn -->
<!-- Ví dụ: -->
<!-- - payment-api JVM heap: -Xmx2g -Xms1g -->
<!-- - Tổng RAM các production instance: 8GB -->
<!-- - Swap: 2GB trên tất cả instance -->
<!-- - Redis cache giới hạn 1GB (maxmemory 1gb) -->
