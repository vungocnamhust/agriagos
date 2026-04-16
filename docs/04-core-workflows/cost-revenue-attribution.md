# Workflow Ghi Nhận Chi Phí Và Doanh Thu Theo Project

## Nói ngắn gọn

ProjectScope chỉ thực sự có giá trị quản trị khi hệ thống quy được chi phí, doanh thu và tác động về đúng scope.

## Trình tự dễ hiểu

1. Record nghiệp vụ được gán vào project scope.
2. Contribution được confirm.
3. Runtime lane hiện tại có thể tạo cost record từ contribution đã confirm.
4. Khi order delivered và có active project assignment, runtime hiện tại có thể ghi revenue record.
5. Runtime hiện tại cũng đã có baseline financial allocation lane cho cost record theo `manual_full` và `manual_weighted`.
6. Các view tổng hợp dùng các fact này để cho thấy lời lỗ và phân bổ.

## Ví dụ thực tế

- Một contribution đã confirm cho biết project dùng 2 ngày công và 1 xe tải. Runtime có thể ghi cost record đầu tiên từ đó.
- Một order thuộc project X được giao thành công. Runtime có thể ghi revenue record đầu tiên cho project đó.
- Một cost record có thể được phân bổ về một hoặc nhiều ProjectScope bằng financial allocation baseline hiện tại.

## Điều chưa nên nói quá tay

Chưa có engine phân bổ tài chính đầy đủ cho mọi case phức tạp hoặc revenue allocation hoàn chỉnh cho mọi tình huống.

Runtime hiện đã có cost/revenue record lane và baseline financial allocation lane, đủ để bắt đầu nhìn project economics mà không nên mô tả như một finance engine hoàn chỉnh.