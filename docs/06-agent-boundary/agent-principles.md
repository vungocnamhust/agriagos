# Nguyên Tắc Agent Boundary

## Nói ngắn gọn

AI Agent đứng trên deterministic core, không đứng thay deterministic core.

## 1. Agent được làm gì

- đọc dữ liệu được phép đọc
- tóm tắt tình hình
- hỏi thiếu dữ liệu
- gợi ý allocation hoặc next step
- tạo draft message, draft order, draft note

## 2. Agent không được làm gì

- sửa raw truth trực tiếp trong DB
- bypass policy
- tự suy quyền từ affiliation, membership hoặc contribution
- tự release lot nếu policy chưa cho
- tự mark delivered cuối cùng nếu runtime không cho

## 3. Agent phải đi qua cái gì

- query contract
- command contract
- authority runtime hiện có
- audit trail khi action nhạy cảm liên quan

## 4. Câu phải nhớ

AI hỗ trợ điều phối.

AI không định nghĩa sự thật của hệ thống.