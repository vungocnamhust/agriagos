# Future Agent Session Scope

## Nói ngắn gọn

`Agent Session Scope` là khái niệm hữu ích cho tương lai, nhưng hiện chưa là lane runtime đã ship.

## Mục tiêu tương lai

- giới hạn agent chỉ thấy đúng phần ngữ cảnh cần thiết
- giới hạn tool call theo session
- ghi rõ agent đang thay mặt ai hoặc phục vụ workflow nào

## Điều cần nhớ hiện tại

Hiện runtime mới chỉ có:
- actor role
- delegated context ở mức hạn chế
- deny mọi bypass request

Chưa có agent session scope hoàn chỉnh.