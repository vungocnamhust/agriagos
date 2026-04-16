# Danh Sách Quyết Định Kiến Trúc Nên Ghi ADR

## Nói ngắn gọn

Nếu team muốn bộ docs này bền và không trôi lại, các quyết định dưới đây nên được ghi ADR hoặc superseding ADR rõ ràng.

## Các quyết định nên khóa bằng ADR

1. Lớp docs reader-facing dưới `docs/` là lớp giải thích và onboarding, không thay authority của changelog docs.
2. Quy tắc viết docs mới: tiếng Việt dễ hiểu trước, English canonical term đặt trong ngoặc.
3. `Organization` là chủ thể vận hành mở cho nhiều mô hình, không chỉ nội bộ hợp tác xã.
4. `ProjectScope` là soft scope cho value stream, không phải hard global boundary.
5. `Actor Identity`, `Affiliation`, `Contribution`, `Permission` là bốn lớp khác nhau, không được gộp ngầm.
6. Zalo group hoặc communication binding không phải source of truth cho quyền.
7. AI Agent không được suy quyền từ membership, affiliation hoặc contribution role.
8. Future authority expansion phải đi qua ADR riêng trước khi semantics của runtime hiện tại bị đổi.