# Review Hiện Trạng Tài Liệu

## Nói ngắn gọn

Bộ docs cũ có nền kiến trúc khá tốt ở lớp authority docs, nhưng người mới rất dễ bị lạc vì ba vấn đề:
- thuật ngữ tiếng Anh dày và nhiều lớp nghĩa gần nhau
- mô tả hiện tại và roadmap còn lẫn nhau
- thứ tự giải thích chưa đi từ nghiệp vụ đời thực đến runtime đang ship

## 1. Các vấn đề chính đang có

### 1.1 Thuật ngữ dày và dễ trộn

Các từ như `Actor`, `Affiliation`, `Membership`, `ProjectScope`, `Contribution Role`, `Permission Grant`, `Authority`, `Value Stream`, `Assignment` thường xuất hiện gần nhau nhưng chưa được giải thích theo thứ tự từ dễ đến khó.

Hậu quả:
- founder đọc dễ mất mạch
- dev mới dễ code sai boundary
- product dễ nhầm context fact với quyền runtime

### 1.2 Một số tài liệu viết như thể future đã có

Các lane như `Permission Grant engine`, `field-level masking`, `delegated permission runtime`, `tool gateway`, `agent session scope` vẫn là hướng đi sau, nhưng ở một số chỗ người đọc có thể hiểu nhầm là đã có lane runtime.

### 1.3 Tài liệu repo root và changelog đang tạo cảm giác có hai canon

Authority thật nằm ở `docs/changelog/v1/architecture/`, nhưng người mới lại rất dễ mở `system_v1.md`, `CLAUDE.md`, `event_desc.md`, `deterministic_core_diagram.md` trước.

### 1.4 Một số mô tả vẫn mang màu “nội bộ HTX”

Định hướng mới của hệ là nền tảng mở cho nhiều organization tự vận hành.

Vì vậy, cách mô tả cần chuyển sang:
- household producer
- family business
- solo founder
- startup operator
- cooperative như một loại organization, không phải mô hình mặc định của cả hệ

### 1.5 Diagram chưa phục vụ tốt cho người mới

Diagram cũ chủ yếu tốt cho người đã quen kiến trúc. Nó chưa thật sự chia rõ:
- cái đang chạy trong runtime
- cái mới là target architecture

## 2. Điểm mạnh của bộ docs hiện có

- Có source-of-truth registry rõ ràng.
- Có divergence ledger để ghi chênh lệch giữa code và docs.
- Có event, state, permission, AI boundary docs tách riêng.
- Có diagram set khá đầy đủ cho deterministic core.

Vấn đề chính là cách trình bày, thứ tự giải thích và phân lớp current versus future.

## 3. Kết luận review

Điều cần làm không phải là đập bỏ toàn bộ authority docs hiện có.

Điều cần làm là:
- thêm một lớp docs dễ đọc ở `docs/`
- chuẩn hóa glossary tiếng Việt dễ hiểu
- tách rõ runtime hiện tại và roadmap tương lai
- tạo checklist để mỗi lần code đổi thì docs không trôi

## 4. File nên viết lại, bỏ, hoặc merge

### Nên viết lại hoặc viết lớp giải thích mới

- `docs/changelog/v1/README.md`: nên cập nhật theo hướng trỏ sang lớp docs mới để onboarding dễ hơn.
- `system_v1.md`: nên xem là narrative companion, không nên bị hiểu là authority chính.
- `event_desc.md`: nên dần được thay bằng bản giải thích bám authority event docs.
- `deterministic_core_diagram.md`: nên xem là companion, không phải bộ diagram authority chính.

### Nên giữ nhưng đổi cách đọc

- `docs/changelog/v1/architecture/03-domain-glossary.md`
- `docs/changelog/v1/architecture/04-canonical-data-model.md`
- `docs/changelog/v1/architecture/05-event-catalog.md`
- `docs/changelog/v1/architecture/07-permission-matrix.md`
- `docs/changelog/v1/architecture/09-ai-agent-boundaries.md`

### Nên merge về mặt nhận thức, không nhất thiết merge file vật lý ngay

- `event_desc.md` và `docs/changelog/v1/architecture/05-event-catalog.md`
- `deterministic_core_diagram.md` và `docs/changelog/v1/diagram/`
- phần onboarding trong repo root docs và `docs/00-start-here/`

## 5. Thuật ngữ cấm dùng nếu chưa giải thích

- Actor
- Membership
- Affiliation
- Permission Grant
- Authority Scope
- Contribution Role
- ProjectScope
- Value Stream
- Assignment
- Soft Scope
- Runtime Baseline
- Tenant
- Delegation
- Binding
- Aggregation
- Canonical
- Source of truth
- Deterministic
- Read model
- Write path
- Tool gateway

## 6. Checklist kiểm tra docs có còn khớp code không

- Có route nào đã mount nhưng docs chưa nói tới không?
- Có event nào runtime emit nhưng glossary hoặc event docs chưa nói không?
- Có enum status nào authority docs nói tới nhưng gateway chưa enforce không?
- Có policy nào docs mô tả là đang chạy nhưng service layer chưa enforce không?
- Có roadmap lane nào đang được viết như thể đã có API và schema runtime không?
- Có diagram nào không còn phản ánh route, service và aggregate đang tồn tại không?
- Có file nào vẫn mô tả hệ như mô hình nội bộ một HTX duy nhất không?

## 7. Các quyết định kiến trúc nên ghi hoặc cập nhật ADR

- Lớp docs reader-facing mới dưới `docs/` là lớp giải thích, không thay authority changelog.
- Quy ước viết docs: tiếng Việt dễ hiểu trước, tên English chuẩn đặt trong ngoặc.
- `ProjectScope` được giải thích chính thức là soft scope cho value stream, không phải hard global boundary.
- `Actor Identity`, `Affiliation`, `Contribution`, `Permission` là bốn lớp khác nhau.
- AI không được suy quyền từ membership hoặc contribution.
- Zalo group hoặc channel binding không phải source of truth cho quyền.

## 8. Kế hoạch ưu tiên

1. Chuẩn hóa glossary.
2. Viết current runtime docs bám code đang ship.
3. Viết current versus future roadmap rõ ràng.
4. Viết domain model theo thứ tự dễ hiểu.
5. Viết workflow nghiệp vụ trước, kỹ thuật sau.
6. Bổ sung diagram reader-friendly.
7. Sau đó mới sync lại derived docs cũ ở repo root nếu cần.