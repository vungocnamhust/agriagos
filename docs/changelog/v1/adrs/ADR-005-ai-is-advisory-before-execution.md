# ADR-005: AI/Agent ở vai trò advisory trước khi được execute

## Status
Accepted

## Context
AI rất hữu ích để:
- hiểu input mơ hồ
- hỏi thiếu dữ liệu
- tạo draft
- gợi ý allocation / follow-up / segmentation

Nhưng nếu cho AI chạm thẳng vào truth layer quá sớm thì:
- khó audit
- dễ excessive agency
- dễ phá state đúng của hệ thống

## Decision
AI/Agent chỉ được:
- đọc dữ liệu trong scope
- tạo draft / note / summary / suggestion
- propose action qua command contracts
- auto execute chỉ trong vùng an toàn và ít rủi ro

AI/Agent không được:
- tự release lot cuối cùng
- tự mark delivered cuối cùng
- tự chốt payment final
- tự override permission
- tự merge canonical customer records

## Consequences
### Tốt
- An toàn hơn
- Dễ đo acceptance rate
- Không làm mờ source of truth

### Xấu
- Giai đoạn đầu automation chưa “wow”
- Cần thêm bước approve/validate
