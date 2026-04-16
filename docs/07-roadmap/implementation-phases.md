# Kế Hoạch Thực Hiện Theo Thứ Tự Ưu Tiên

## Nói ngắn gọn

Ưu tiên đầu tiên không phải là thêm thật nhiều docs mới, mà là làm cho người mới hiểu đúng runtime hiện tại.

## Ưu tiên 1

- Chuẩn hóa glossary và term map.
- Giữ rõ lớp authority docs và lớp giải thích.
- Chốt file `current-vs-future.md` như cổng chống nhầm lẫn.

## Ưu tiên 2

- Đồng bộ lại `docs/changelog/v1/README.md` để trỏ người đọc sang lớp docs mới.
- Rà lại các file root như `system_v1.md`, `event_desc.md`, `deterministic_core_diagram.md` để tránh tạo cảm giác có hai canon.

## Ưu tiên 3

- Cập nhật authority docs nào đang dùng từ gây hiểu nhầm như `HTX` theo nghĩa mặc định toàn hệ.
- Gắn rõ nhãn current versus future ở permission và AI boundary docs cũ nếu còn nhập nhằng.

## Ưu tiên 4

- Khi runtime authority engine mở rộng, tạo ADR và sync lại lớp docs mới ngay trong cùng thay đổi.

## Thứ tự thực hiện khuyến nghị cho team

1. Chốt vocabulary.
2. Chốt current runtime surfaces.
3. Chốt diagram onboarding.
4. Chốt current versus future policy.
5. Sau đó mới mở rộng roadmap docs theo epic.