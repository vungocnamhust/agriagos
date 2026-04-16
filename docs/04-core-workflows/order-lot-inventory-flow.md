# Workflow Order - Lot - Inventory

## Nói ngắn gọn

Đây là phần lõi của deterministic core đang chạy mạnh nhất.

Mục tiêu là biết:
- khách đã cam kết gì
- order nào đang được thực hiện
- lot nào đang còn khả dụng
- allocation nào đã giữ hoặc tiêu thụ số lượng

## Trình tự dễ hiểu

1. Có thể bắt đầu từ customer và preorder.
2. Tạo order để phục vụ giao dịch cụ thể.
3. Confirm order.
4. Allocate order line vào một hoặc nhiều lot.
5. Pack, ship, deliver theo lifecycle.
6. Khi delivered, các fact liên quan như preorder delivered quantity mới được tiến lên.

## Ví dụ thực tế

Khách đã preorder 200 kg gạo. Đợt này tạo order giao 50 kg. Order được allocate vào lot đã release. Sau khi giao thành công, delivered quantity của preorder mới tăng tương ứng.

## Điều rất quan trọng

- Preorder là contract quantity, không phải shipment.
- Order là lane thực hiện giao dịch cụ thể.
- Allocation là bản ghi nối lot với order line.
- Lot chỉ được allocate khi trạng thái phù hợp.

## Current runtime

Các lane này đã ship và là source of truth chính của hệ.