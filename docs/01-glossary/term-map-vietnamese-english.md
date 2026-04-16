# Bản Đối Chiếu Thuật Ngữ Việt - Anh

| Tiếng Việt dễ hiểu | English canonical term | Ghi chú dùng từ |
|---|---|---|
| Tổ chức vận hành | Organization | Dùng cho aggregate vận hành chính |
| Loại tổ chức | Organization Type | Enum phân loại organization |
| Phạm vi dự án mềm | ProjectScope | Canonical term trong code |
| Dòng giá trị | Value Stream | Tên nghiệp vụ gần nghĩa với ProjectScope |
| Chủ thể được ghi nhận | Actor Identity | Không đồng nghĩa với user account |
| Quan hệ mềm | Affiliation | Không tự sinh permission |
| Thành viên | Membership | Một dạng affiliation |
| Quyền được cấp riêng | Permission Grant | Hiện mới là roadmap lane |
| Vai trò đóng góp | Contribution Role | Thuộc contribution fact, không phải authority |
| Sổ cái đóng góp | Contribution Ledger | Lane ghi nhận đóng góp append-only |
| Gán phạm vi dự án | Project Assignment | Gắn record vào project scope |
| Nguồn lực dùng chung | Shared Resource | Không phải lot inventory |
| Khách hàng chuẩn | Customer Profile | Runtime thường gọi ngắn là customer |
| Cam kết mua trước | Preorder | Contract quantity, không phải shipment |
| Đơn hàng bán | Sales Order | Runtime route dùng `orders` |
| Lô hàng | LotBatch | Runtime thường gọi ngắn là lot |
| Phân bổ | Allocation | Link order line với lot |
| Kiểm định chất lượng | QC Review | Quyết định QC cho lot |
| Sự kiện miền nghiệp vụ | Domain Event | Event fact dạng quá khứ |
| Nhật ký audit | Audit Log | Log quyết định cho phép hoặc từ chối |
| Quyền hạn đang enforce | Authority | Runtime service checks |
| Tài khoản đăng nhập | User Account | Chưa là canonical runtime aggregate đầy đủ |
| Ràng buộc kênh giao tiếp | Communication Binding | Không phải source of truth cho quyền |
| Lõi xác định sự thật | Deterministic Core | Giữ state, event, audit, idempotency |