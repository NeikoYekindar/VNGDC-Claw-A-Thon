# Teams Security Report Template

Template này là chuẩn cấu trúc cho mọi báo cáo agent gửi sang Microsoft Teams. Mục tiêu là để người nhận nắm được kết luận chính trong 30 giây, sau đó có đủ bằng chứng và hành động tiếp theo để xử lý.

## Quy tắc chung

- Không mở đầu bằng lời chào.
- Không đưa secret, password, token, webhook signature hoặc private key vào báo cáo.
- Không paste raw output dài vào Teams card; raw output chi tiết nằm trong file Excel đính kèm.
- Mỗi báo cáo phải có kết luận tổng thể, phạm vi, số liệu chính, hành động ưu tiên và bằng chứng ngắn.
- Dùng tiếng Việt chuyên nghiệp, ngắn gọn, hướng hành động.
- Với Teams card, ưu tiên bullet và numbered list; hạn chế bảng dài vì Teams render Markdown table không ổn định.

## Cấu trúc bắt buộc

```markdown
# <Tên báo cáo>

**Trạng thái tổng thể**: <Đạt / Cần rà soát / Cần xử lý / Lỗi kiểm tra>
**Thời điểm**: <YYYY-MM-DD HH:mm:ss ICT>
**Nguồn**: VNGDC Security Agent

## 1. Tóm tắt điều hành

<2-4 câu nêu kết luận chính, mức rủi ro, phạm vi ảnh hưởng và việc cần làm trước tiên.>

## 2. Phạm vi kiểm tra

- **Server/Scope**: <host, service, hoặc scope>
- **Hệ điều hành/Nền tảng**: <Ubuntu 24.04 / Windows Server 2022 / Wazuh / Mixed>
- **Loại kiểm tra**: <Hardening / Vulnerability / Daily Security Check>
- **File bằng chứng**: <Tên file Excel nếu có>

## 3. Kết quả trọng yếu

- **Fail/Critical**: <số lượng và ý nghĩa>
- **Warn/High**: <số lượng và ý nghĩa>
- **Tác động vận hành**: <ảnh hưởng nếu không xử lý>

## 4. Phát hiện ưu tiên

### [P0/P1/P2][Critical/High/Medium] <Tên finding>

- **Vấn đề**: <cấu hình, CVE hoặc điều kiện chưa đạt>
- **Bằng chứng**: <dòng check/log/CVE rút gọn>
- **Rủi ro**: <tác động bảo mật thực tế>
- **Khắc phục**: <hành động cụ thể>
- **Kiểm tra lại**: <lệnh hoặc cách xác minh>

## 5. Hành động yêu cầu

1. **P0/P1 - Xử lý ngay**: <việc cần làm trước>
2. **P2 - Chuẩn hóa cấu hình**: <việc cần đưa vào backlog/sprint>
3. **Theo dõi**: <cách kiểm tra lại và lưu bằng chứng>

## 6. Bằng chứng và dữ liệu đính kèm

- **Bằng chứng ngắn**: <tối đa 5-8 dòng FAIL/WARN/CVE quan trọng>
- **File đính kèm**: <Excel report chứa raw output và dữ liệu đầy đủ>
```

## Mapping trạng thái

| Điều kiện | Trạng thái tổng thể | Ưu tiên |
|---|---|---|
| Có FAIL hardening hoặc Critical CVE | Cần xử lý | P1 |
| Có WARN hardening hoặc High CVE | Cần rà soát | P2 |
| Không có lỗi quan trọng | Đạt | P3 |
| Tool/SSH/API lỗi | Lỗi kiểm tra | P1 |

## Tiêu đề chuẩn

- Hardening đơn lẻ: `Hardening Report: <host> - <FAIL> FAIL, <WARN> WARN`
- Daily report: `[Automated] Daily Security Report`
- Vulnerability report: `Vulnerability Report: <scope> - <Critical> Critical, <High> High`

