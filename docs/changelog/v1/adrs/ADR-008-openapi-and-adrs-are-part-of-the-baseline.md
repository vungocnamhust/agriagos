# ADR-008: OpenAPI contracts và ADRs là một phần của baseline kỹ thuật

## Status
Accepted

## Context
Team đang vibe coding nhanh. Nếu chỉ có vision/doc prose mà không có contract và decision records thì rất dễ:
- mỗi người code một kiểu
- boundary bị trôi
- sửa decision lớn mà không ai biết

## Decision
Xem OpenAPI contracts và ADRs là tài liệu baseline chính thức cùng với docs deterministic core.

Khi thay đổi:
- workflow write API -> cập nhật OpenAPI
- quyết định kiến trúc lớn -> thêm ADR mới hoặc supersede ADR cũ

## Consequences
### Tốt
- Giảm lệch mục tiêu khi code nhanh
- Onboard người mới dễ hơn
- Decision lớn có dấu vết

### Xấu
- Tốn thêm chút kỷ luật tài liệu
