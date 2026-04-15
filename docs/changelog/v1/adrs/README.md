# ADR Index

| ADR | Title | Status |
|---|---|---|
| ADR-001 | Agri OS Core là deterministic operating core | Accepted |
| ADR-002 | Mỗi domain chỉ có một source of truth | Accepted |
| ADR-003 | Ghi event nghiệp vụ sớm để nuôi audit, projections và agent context | Accepted |
| ADR-004 | Monolith modular trước, không microservice hóa sớm | Accepted |
| ADR-005 | AI/Agent ở vai trò advisory trước khi được execute | Accepted |
| ADR-006 | External mapping table là bắt buộc | Accepted |
| ADR-007 | Role-based views ưu tiên hơn raw table access | Accepted |
| ADR-008 | OpenAPI contracts và ADRs là một phần của baseline kỹ thuật | Accepted |
| ADR-009 | Core owns plot/crop summary; LiteFarm may own deep field data later | Accepted |
| [ADR-010](ADR-010-id-strategy.md) | ID Strategy — UUID cho machine ID, sequential code cho human-readable | Accepted |
| [ADR-011](ADR-011-api-contract-committed-spec.md) | OpenAPI spec phải là committed artifact trong git | Accepted |
| ADR-012 | Organization là legal-operating owner aggregate; tenant giữ nghĩa deployment boundary | Proposed |

Tài liệu này là chỉ mục nhanh cho các quyết định kiến trúc đã được khóa trong baseline hiện tại.

Khi có quyết định mới:
- thêm ADR mới thay vì sửa âm thầm quyết định cũ
- nếu một ADR bị thay thế, cập nhật trạng thái của ADR cũ theo quy ước `Superseded by ADR-XXX`