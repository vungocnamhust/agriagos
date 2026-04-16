# Contribution Ledger

## Nói ngắn gọn

`Contribution Ledger` ghi nhận ai đã đóng góp gì vào một `ProjectScope`.

Nó là fact nghiệp vụ để đo tác động và phân bổ giá trị, không phải engine cấp quyền.

## 1. Contribution Role khác Authority thế nào

### Contribution Role

- mô tả vai trò trong một lần đóng góp cụ thể
- là fact nghiệp vụ
- ví dụ: người cung cấp xe, người dẫn khách, người góp vốn, người tạo nội dung

### Authority

- mô tả quyền runtime đang được enforce
- ví dụ: ai được confirm contribution, ai được ghi cost record, ai được làm QC review

Một người có contribution lớn không có nghĩa là họ được approve hoặc sửa mọi thứ.

## 2. Runtime hiện có gì

Theo project contribution lane hiện tại:
- record contribution
- confirm contribution
- reject contribution
- project contribution summary views
- project contribution ledger views

## 3. Dùng để làm gì

- ghi nhận tác động thật
- giải thích lời lỗ theo project scope
- biết ai đã đóng góp tài nguyên, công, khách hoặc vận hành
- làm input cho cost record lane đầu tiên

## 4. Không nên nhầm với

### Event log toàn hệ thống

Event log ghi state-changing facts của hệ. Contribution ledger là lane nghiệp vụ chuyên cho đóng góp.

### Permission table

Contribution không phải danh sách quyền.

## 5. Ví dụ thực tế

- Anh Minh góp xe tải cho chuyến giao hàng của project X.
- Chị Lan giới thiệu khách hàng đầu tiên cho dòng quà tặng nông sản.
- Một cộng tác viên ghi nhận 3 ngày công chuẩn bị trải nghiệm farm tour.

## 6. Source of truth không

Có, cho contribution facts của project scope lane hiện tại.