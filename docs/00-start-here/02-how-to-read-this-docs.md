# Cách Đọc Bộ Docs Này

## Nói ngắn gọn

Đọc theo nghiệp vụ trước, kỹ thuật sau.

Đừng bắt đầu bằng event catalog hay state machine nếu bạn còn chưa hiểu `Organization`, `ProjectScope`, `Actor`, `Order`, `Lot` khác nhau thế nào.

## Luật đọc quan trọng

### 1. Luôn tách hai lớp

Lớp A, đang có trong runtime:
- API đã mount
- DTO đã có
- event đã emit
- schema hoặc table đang được code dùng
- authz đang chạy

Lớp B, roadmap hoặc future:
- đã được nhắc trong kiến trúc
- có thể có draft DTO, draft doc, draft diagram
- nhưng chưa được coi là truth runtime

### 2. Ưu tiên tiếng Việt dễ hiểu trước

Nếu có thuật ngữ tiếng Anh, trong docs này sẽ đi kèm giải thích tiếng Việt ngay tại chỗ.

### 3. Nếu thấy mâu thuẫn, kiểm tra theo thứ tự sau

1. `docs/changelog/v1/architecture/00-source-of-truth-registry.md`
2. authority docs trong `docs/changelog/v1/architecture/`
3. OpenAPI và diagram trong changelog
4. code runtime ở `agos_app/app/`
5. derived docs ở repo root hoặc lớp docs mới này

### 4. Không suy rộng từ tên gọi

Ví dụ:
- `membership` không đồng nghĩa với quyền
- `contribution role` không đồng nghĩa với authority
- `organization` không phải chỉ là nhãn gắn record
- `actor` không phải cùng nghĩa với user account

## Thứ tự đọc khuyến nghị

### Tuyến 1: Người mới hoàn toàn

1. `01-system-overview.md`
2. `03-documentation-review.md`
3. `docs/01-glossary/glossary.md`
4. `docs/07-roadmap/current-vs-future.md`

### Tuyến 2: Dev backend

1. `docs/02-current-runtime/current-runtime-overview.md`
2. `docs/02-current-runtime/current-api-and-events.md`
3. `docs/02-current-runtime/current-authz-and-audit.md`
4. `docs/03-domain-model/`
5. `docs/04-core-workflows/order-lot-inventory-flow.md`

### Tuyến 3: Product và ops

1. `docs/01-glossary/glossary.md`
2. `docs/03-domain-model/project-scope.md`
3. `docs/04-core-workflows/contribution-recording.md`
4. `docs/04-core-workflows/cost-revenue-attribution.md`

## Cách dùng khi cập nhật code

Khi code thay đổi, hãy hỏi 4 câu:
- Runtime mới có API hay event mới không?
- Khái niệm nào đổi nghĩa?
- Diagram nào đang nói như thể feature đã ship trong khi thực tế chưa?
- Có cần ADR vì boundary hoặc authority đã đổi không?

## Dấu hiệu docs đang sai

- nói `future` như thể đã chạy thật
- dùng từ tiếng Anh mà không giải thích
- một khái niệm có hai tên khác nhau ở hai file
- diagram nói một chuyện, route/service chạy một chuyện
- mô tả system như app nội bộ HTX trong khi code đã mở cho nhiều organization