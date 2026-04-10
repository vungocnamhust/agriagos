# ADR-007: Role-based views ưu tiên hơn raw table access

## Status
Accepted

## Context
Hệ có nhiều role:
- founder/admin
- sales
- CSKH
- ops/kho
- farm manager
- accountant
- viewer
- future agents

Cùng một dữ liệu gốc nhưng mỗi role cần nhìn khác nhau.
Nếu frontend hoặc agent query raw tables trực tiếp, hệ sẽ khó kiểm soát dữ liệu hiển thị và permission.

## Decision
Ưu tiên read models / role-based views như:
- customer_360_view
- available_lots_board
- pending_fulfillment_board
- farm_summary_view
- qc_board_view (khi có)

Frontend và agent nên dùng views hoặc query APIs tương ứng thay vì đọc bảng thô.

## Consequences
### Tốt
- Dễ áp permission
- Dễ làm one truth, many views
- AI sau này dễ đọc đúng context hơn

### Xấu
- Tăng công build projections
- Cần giữ projections cập nhật
