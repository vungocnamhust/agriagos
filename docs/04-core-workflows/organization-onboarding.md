# Workflow Tạo Organization

## Nói ngắn gọn

Bước đầu tiên của hệ là ghi nhận chủ thể vận hành.

Không có organization, mọi lane phía sau sẽ thiếu parent context.

## Trình tự dễ hiểu

1. Người vận hành tạo một organization.
2. Hệ thống cấp `organizationId` và `organizationCode`.
3. Organization bắt đầu ở trạng thái `draft`.
4. Sau khi đủ thông tin hoặc đủ điều kiện, organization được `activate`.
5. Từ đó có thể tạo project scope, gắn actor affiliation và gắn các hoạt động khác dưới organization này.

## Ví dụ thực tế

Một hộ sản xuất đang bán gạo riêng muốn đưa toàn bộ hoạt động lên hệ thống. Họ tạo organization trước, sau đó mới khai báo dòng giá trị và tài sản.

## Runtime hiện có

- create
- update
- activate
- pause
- close

## Điều cần nhớ

Organization là chủ thể vận hành, không phải label trang trí.