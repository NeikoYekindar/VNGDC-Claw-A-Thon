# Disk / Storage Alert Knowledge Base

## Các ngưỡng cảnh báo Disk

| Ngưỡng | Mức độ | Hành động |
|--------|--------|-----------|
| Used > 70% | Info | Bắt đầu theo dõi tăng trưởng |
| Used > 80% | Warning | Kiểm tra nguyên nhân, lên kế hoạch |
| Used > 90% | Critical | Giải phóng ngay hoặc mở rộng |
| Used > 95% | Emergency | Service có thể bị fail, xử lý ngay |
| Inode used > 80% | Warning | Quá nhiều file nhỏ, dù dung lượng còn nhiều |

## Nguyên nhân phổ biến

### Log file quá lớn
- Application log không có log rotation
- Log level DEBUG được bật trên production
- Error log tăng đột biến do lỗi application
- Access log của web server (Nginx, Apache) không rotate

### Data tăng tự nhiên
- Database data files tăng theo business
- Backup files tích lũy theo thời gian
- Upload files từ user không được cleanup
- Core dump files do application crash

### Disk đầy đột ngột
- Database transaction log (WAL) không được cleanup
- Temporary files không xóa sau khi xử lý
- Docker images và containers tích lũy
- `/tmp` hoặc `/var/tmp` đầy

### Inode đầy (dù dung lượng còn)
- Quá nhiều file nhỏ (session files, cache files, email queue)
- Thư mục chứa hàng triệu file nhỏ

## Các lệnh điều tra

```bash
# Tổng quan disk usage
df -h
df -ih   # inode usage

# Tìm thư mục lớn nhất
du -sh /* 2>/dev/null | sort -h | tail -n 20
du -sh /var/log/* 2>/dev/null | sort -h | tail -n 20
du -sh /var/lib/* 2>/dev/null | sort -h | tail -n 20

# Tìm file lớn nhất
find / -type f -size +100M 2>/dev/null | head -n 20
find /var/log -name "*.log" -size +1G 2>/dev/null

# Kiểm tra disk I/O
iostat -x 1 5
iotop -b -n 5 2>/dev/null

# Kiểm tra log rotation config
ls -la /etc/logrotate.d/
cat /etc/logrotate.conf

# Kiểm tra cron jobs liên quan đến cleanup
crontab -l
ls /etc/cron.daily/
```

## Hướng xử lý

### Immediate mitigation (không xóa dữ liệu quan trọng)
- **Compress log cũ** (an toàn hơn xóa):
  ```bash
  gzip /var/log/app/app.log.1
  ```
- **Archive log ra storage khác** trước khi xóa
- **Xóa log đã rotate an toàn** (file .gz cũ hơn 30 ngày):
  ```bash
  find /var/log -name "*.gz" -mtime +30 -delete  # CẦN XÁC NHẬN
  ```
- **Xóa Docker resources không dùng**:
  ```bash
  docker system prune -f  # CẦN XÁC NHẬN
  ```

### Long-term fix
- Cấu hình logrotate cho tất cả application log
- Thêm disk usage forecast alert (alert sớm ở 70%)
- Tăng disk size hoặc mount thêm volume
- Chuyển log sang centralized logging (ELK, Loki)
- Cấu hình backup policy với retention period rõ ràng
- Dùng S3/object storage cho user upload files

## Các đường dẫn log phổ biến cần kiểm tra
```
/var/log/           # System logs
/var/log/nginx/     # Nginx access/error logs
/var/log/apache2/   # Apache logs
/var/log/mysql/     # MySQL logs
/var/log/postgresql/ # PostgreSQL logs
/opt/app/logs/      # Application logs (thường gặp)
/home/*/logs/       # User application logs
```

## Infrastructure context
<!-- Điền thông tin hệ thống cụ thể của bạn -->
<!-- Ví dụ: -->
<!-- - Disk layout: / = 50GB SSD, /data = 500GB HDD -->
<!-- - Log rotation: logrotate chạy mỗi ngày, giữ 7 ngày -->
<!-- - Application log path: /opt/payment-api/logs/ -->
<!-- - Database data: /var/lib/mysql/ -->
<!-- - Backup path: /backup/ (giữ 30 ngày) -->
