# Agri System Docs

Bộ tài liệu này là **xương sống kiến trúc** cho project quản lý nông nghiệp + CRM + ERP + Agent.

Mục tiêu của bộ docs:
- chốt phần **deterministic core** trước
- để AI/Agent đứng ở lớp hỗ trợ và điều phối mềm
- giúp team có chung cách hiểu về workflow, dữ liệu, event, trạng thái, phân quyền và tích hợp

## Cấu trúc chính

- `docs/architecture/README.md`: mục lục và cách đọc
- `docs/architecture/01-system-vision.md`: tầm nhìn hệ thống
- `docs/architecture/02-core-workflows.md`: workflow lõi
- `docs/architecture/03-domain-glossary.md`: từ điển nghiệp vụ
- `docs/architecture/04-canonical-data-model.md`: mô hình dữ liệu chuẩn
- `docs/architecture/05-event-catalog.md`: danh mục event
- `docs/architecture/06-state-transitions.md`: trạng thái và chuyển trạng thái
- `docs/architecture/07-permission-matrix.md`: phân quyền
- `docs/architecture/08-integration-contracts.md`: hợp đồng tích hợp
- `docs/architecture/09-ai-agent-boundaries.md`: ranh giới AI/Agent
- `docs/architecture/10-assumptions-and-migration-path.md`: giả định và đường tiến hóa
- `docs/architecture/11-core-baseline-signoff.md`: baseline deliverables, owner, sign-off criteria
- `openapi/openapi.yaml`: OpenAPI v1 cho deterministic core
- `adrs/`: các ADR khóa các quyết định kiến trúc quan trọng


## Cách dùng nhanh cho team

1. Đọc `docs/architecture/README.md`
2. Chốt lại 1 workflow đầu tiên cần build
3. Build theo **vertical slice**
4. Khi code có tranh cãi, quay lại các file:
   - dữ liệu: `04`
   - event: `05`
   - state: `06`
   - phân quyền: `07`
   - AI có được chạm vào hay không: `09`
5. Dùng `openapi.yaml` làm baseline cho backend routes, DTOs, validation.
6. Dùng ADRs để khóa boundary, tránh vibe coding làm trôi source of truth.
7. Khi thay đổi decision lớn, không sửa âm thầm — thêm ADR mới hoặc supersede ADR cũ.

## Nguyên tắc cốt lõi

- **Source of truth phải rõ**
- **State chính không được mơ hồ**
- **Mọi thay đổi quan trọng nên có event**
- **AI không được định nghĩa sự thật của hệ thống**
- **Monolith modular trước, tách dần sau**


## DDL scope
DDL này cố ý thiên về deterministic core vận hành:
- customer canonical identity
- preorder
- orders
- lots
- allocations
- inventory movements
- farm summary
- external mappings
- eventing / audit / idempotency

Nó chưa bao phủ:
- accounting journal chuẩn của ERP
- farm agronomy sâu
- agent memory/runtime

## FastAPI scope
Skeleton route groups bám theo OpenAPI v1:
- route có sẵn
- DTO có sẵn
- TODO được đặt đúng chỗ để team bắt đầu cấy business logic

AI không có router riêng ở bộ này.
Khi thêm AI sau, AI phải đi qua cùng command/query contracts hoặc một brain adapter nằm ngoài deterministic core.
