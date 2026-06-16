# CPU Alert Knowledge Base

## Các ngưỡng cảnh báo CPU

| Ngưỡng | Mức độ | Hành động |
|--------|--------|-----------|
| > 70% trong 5 phút | Warning | Kiểm tra process, monitor tiếp |
| > 90% trong 5 phút | Critical | Điều tra ngay, cân nhắc scale |
| Load average > số CPU | Warning | Có thể bị bottleneck I/O hoặc CPU |
| Load average > 2x số CPU | Critical | Hệ thống đang quá tải nghiêm trọng |

## Nguyên nhân phổ biến

### CPU spike đột ngột (tăng nhanh, giảm nhanh)
- Batch job chạy định kỳ (cron job, scheduled task)
- GC (Garbage Collection) của JVM / Python
- Traffic spike đột biến
- Log rotation hoặc backup job

### CPU cao kéo dài
- Memory leak dẫn đến swap → CPU tăng
- Infinite loop trong application code
- Database query không có index (full table scan)
- Quá nhiều thread/process tranh nhau CPU

### CPU cao do hệ thống
- Kernel update hoặc package upgrade đang chạy nền
- Antivirus / security scan
- System log rotation (logrotate)

## Các lệnh điều tra

```bash
# Xem process tiêu tốn CPU nhiều nhất
top -b -n 1 | head -n 20
ps aux --sort=-%cpu | head -n 15

# Xem load average theo thời gian
uptime
cat /proc/loadavg

# Chi tiết CPU theo core
mpstat -P ALL 1 5

# Xem CPU usage theo user/system/iowait
vmstat 1 5

# Tìm process đang dùng nhiều CPU
pidstat -u 1 5
```

## Hướng xử lý

### Immediate mitigation
- Nếu batch job: xem xét reschedule sang giờ thấp điểm
- Nếu process treo (zombie hoặc 100% CPU): restart service (cần confirm)
- Nếu traffic spike: cân nhắc scale horizontal

### Long-term fix
- Tách batch job ra khỏi production instance
- Tối ưu database query (thêm index)
- Cấu hình autoscaling policy
- Review và tối ưu code path gây CPU cao
- Giới hạn CPU usage của từng service bằng cgroups/Docker limits

## Infrastructure context
<!-- Điền thông tin hệ thống cụ thể của bạn -->
<!-- Ví dụ: -->
<!-- - payment-api chạy trên Java 17, thường có GC spike mỗi 30 phút -->
<!-- - batch-job chạy lúc 2h sáng mỗi ngày, bình thường dùng 60-70% CPU trong 10 phút -->
<!-- - Số CPU của các production instance: 4 vCPU -->
