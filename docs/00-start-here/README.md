# Bắt Đầu Ở Đây

## Nói ngắn gọn

AgriOS là lõi vận hành xác định sự thật của một hệ sinh thái nông nghiệp mở.

Một cá nhân, hộ gia đình, nhóm vận hành, hay đối tác có thể:
- tạo một tổ chức vận hành
- khai báo tài sản và nguồn lực
- tạo dòng giá trị hoặc phạm vi dự án mềm
- ghi nhận đóng góp của người tham gia
- vận hành khách hàng, cam kết mua trước, đơn hàng, lô hàng, phân bổ và tồn kho
- xem báo cáo tác động, lời lỗ và phân quyền đọc hoặc thao tác

AI Agent chỉ đứng ở lớp hỗ trợ. AI không được tự quyết định sự thật của hệ thống.

## Đọc theo thứ tự nào

1. `docs/00-start-here/01-system-overview.md`
2. `docs/00-start-here/02-how-to-read-this-docs.md`
3. `docs/00-start-here/03-documentation-review.md`
4. `docs/01-glossary/glossary.md`
5. `docs/02-current-runtime/current-runtime-overview.md`
6. `docs/03-domain-model/`
7. `docs/04-core-workflows/`
8. `docs/06-agent-boundary/`
9. `docs/07-roadmap/current-vs-future.md`

## Nếu bạn là...

- Founder: đọc `01-system-overview`, `03-documentation-review`, `07-roadmap/current-vs-future`.
- Dev mới vào: đọc `01-glossary`, `02-current-runtime`, `03-domain-model`, rồi mới sang `04-core-workflows`.
- Product hoặc ops: đọc `01-system-overview`, `03-domain-model`, `04-core-workflows`.

## Source of truth nằm ở đâu

Authority docs vẫn là:
- `docs/changelog/v1/architecture/00-source-of-truth-registry.md`
- `docs/changelog/v1/architecture/`
- `docs/changelog/v1/openapi/agros-api-v1.0.yaml`
- `docs/changelog/v1/diagram/`

Lớp docs mới này là lớp giải thích và điều hướng. Nếu có mâu thuẫn, ưu tiên authority docs rồi đối chiếu lại code runtime.