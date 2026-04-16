# Current Authz And Audit

## Nói ngắn gọn

Runtime hiện tại có authz thật, nhưng chưa phải permission platform hoàn chỉnh.

Hiện hệ thống đang enforce chủ yếu bằng:
- baseline roles
- service-layer checks
- protected reads
- audit deny hoặc escalate

## 1. Các role hiện có trong enum

Theo `app/models/enums.py`, runtime hiện có:
- `super_admin`
- `founder`
- `admin`
- `sales`
- `cskh`
- `integration`
- `ops`
- `farm_manager`
- `accountant`
- `viewer`
- `agent`
- `qc_reviewer`

## 2. Điều authz hiện tại thực sự làm

- Chuẩn hóa alias role.
- Bảo vệ read surfaces như `/views`, `/events`, `/audit` và nhiều raw reads.
- Kiểm tra write permission ở service layer cho order, preorder, lot, project-related writes.
- Ghi audit khi bị từ chối, leo thang hoặc thất bại.
- Từ chối mọi bypass request ở Phase 1.

## 3. Điều authz hiện tại chưa phải

- Chưa là engine `Permission Grant` đầy đủ.
- Chưa là ABAC hoàn chỉnh theo org hoặc project.
- Chưa là delegated permission runtime đầy đủ cho agent.
- Chưa là field-level masking engine.

## 4. Audit hiện đang ghi gì

Audit lane dùng để ghi:
- ai đã thử làm gì
- trên đối tượng nào
- kết quả là `allowed`, `denied`, `escalated`, hay `failed`
- reason code là gì
- correlation id, metadata, snapshot liên quan

## 5. Các nguyên tắc phải nhớ

### Membership không phải permission

Một actor có affiliation với organization hoặc project không tự động có quyền sửa dữ liệu nhạy cảm.

### Contribution không phải authority

Người đóng góp cho một project không tự động có quyền approve hay execute action nhạy cảm.

### Agent không được tự nâng quyền

Agent có thể xuất hiện như actor type hoặc delegated context, nhưng vẫn phải bị chặn bởi authority runtime hiện hành.

### Zalo group không phải nguồn sự thật cho quyền

Một người ở trong group chat vận hành không có nghĩa là họ có quyền trong deterministic core.