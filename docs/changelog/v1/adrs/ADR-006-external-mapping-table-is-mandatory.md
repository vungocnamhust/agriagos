# ADR-006: External mapping table là bắt buộc

## Status
Accepted

## Context
Hệ sẽ tích hợp ERP, LiteFarm/farm app, CRM và có thể thêm logistics/payments.
Nếu mapping nằm rải rác trong code hoặc chỉ tồn tại trong đầu team, sync sẽ rất dễ vỡ.

## Decision
Tạo bảng mapping chuẩn:
- external_system
- external_object_type
- external_object_id
- internal_object_type
- internal_object_id
- sync_status
- last_synced_at
- last_error

Ngoài ra cần identity binding riêng cho phone/zalo/fb/email nếu dùng omnichannel.

## Consequences
### Tốt
- Sync minh bạch
- Dễ reconcile
- Không hardcode mapping khắp nơi

### Xấu
- Tăng thêm một lớp dữ liệu phải quản lý
- Cần quy ước cập nhật mapping rất rõ
