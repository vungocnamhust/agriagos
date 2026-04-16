# 09. AI Agent Boundaries

## 1. Mục tiêu

Tài liệu này chốt ranh giới giữa:
- deterministic core
- automation thường
- AI / Agent

Nếu không chốt sớm, hệ rất dễ:
- mơ hồ source of truth
- trao quyền quá tay cho AI
- khó debug
- khó audit
- khó mở rộng về sau

## 2. Một câu phải nhớ

**AI không định nghĩa sự thật hệ thống.**  
AI chỉ:
- đọc
- hiểu
- hỏi thiếu
- gợi ý
- tạo draft
- tóm tắt
- hỗ trợ operator

## 3. AI nên đứng ở đâu trong hệ

Trong kiến trúc chung của mình:
- deterministic core là lõi
- AI đứng phía trên lõi
- AI chỉ đi qua query / tool / command contract

Điều đó nghĩa là:
- AI không chạm thẳng DB canonical
- AI không bypass policy
- AI không tự mở rộng quyền
- AI không được suy quyền từ membership, contribution role, hoặc chat/channel binding

Phase 1 clarification:
- kiến trúc có thể chừa sẵn cơ chế biểu diễn bypass lane cho agent / automation
- nhưng hiện tại không có bypass lane nào đang enable
- mọi bypass request ở Phase 1 phải bị deny và audit thay vì được execute

Rule cứng cho epic authority model:
- `Actor Identity`, `Membership/Affiliation`, `Contribution Role`, và `Permission Grant` là các lớp khác nhau
- agent chỉ được dùng lớp authority đang được runtime enforce; các lớp context chỉ để read, suggest, summarize, hoặc propose
- nếu future `PermissionGrant` runtime lane được ship, decision đó phải được ghi bằng ADR riêng thay vì ngầm đổi semantics của membership hoặc contribution

---

## 4. Những việc AI nên làm ngay

## 4.1 Canonical Intake
Nhận input từ chat / form / operator và chuẩn hóa về JSON chung.

Ví dụ AI có thể giúp:
- khách nói rất mơ hồ
- thiếu field
- dùng từ không chuẩn
- cùng một ý nhưng nói theo nhiều cách

Output của AI nên là:
- action_type
- object hints
- missing fields
- confidence
- next suggested step

## 4.2 Hỏi thiếu thông tin
Ví dụ:
- chưa có địa chỉ giao
- chưa rõ quantity
- chưa rõ khách muốn dùng preorder quota hay mua thêm
- chưa rõ lot preference nếu workflow cần

## 4.3 Gợi ý allocation
AI có thể gợi ý:
- lot nào phù hợp
- order nào nên ưu tiên
- cách gom xử lý để đỡ thiếu hàng

Nhưng core hoặc người phải chốt.

## 4.4 CRM support
AI có thể:
- tóm tắt customer 360
- gợi ý sản phẩm phù hợp
- soạn tin nhắn follow-up
- gợi ý segment / tag / preference candidate

## 4.5 Ops summary
AI có thể:
- tóm tắt tình hình ngày
- gom lỗi sync
- báo đơn nào đang tắc
- báo lot nào sắp cạn
- tạo bản tóm tắt cho founder / admin

---

## 5. Những việc AI không nên tự làm trong phase đầu

- tự release lot
- tự mark delivered cuối cùng
- tự thay đổi available quantity
- tự hợp nhất customer record
- tự override allocation
- tự sửa permission
- tự chỉnh payment amount cuối cùng
- tự kết luận accounting final

---

## 6. Cách chia agent theo vai trò

## 6.1 Sales Agent
### Được làm
- đọc customer 360
- gợi ý order draft
- gợi ý lịch follow-up
- soạn nội dung bán hàng

### Không được làm
- chốt payment
- chốt delivery final
- sửa lot / allocation final

## 6.2 CSKH Agent
### Được làm
- tóm tắt lịch sử khách
- gợi ý phản hồi
- tạo preference candidate
- nhắc lịch giao / nhắc mua lại

### Không được làm
- sửa quota preorder final
- thay đổi order financials

## 6.3 Ops Agent
### Được làm
- hiển thị đơn cần xử lý
- gợi ý allocation
- gợi ý ưu tiên xử lý
- cảnh báo thiếu hàng

### Không được làm
- execute allocation cuối cùng nếu policy yêu cầu approval
- tự mở blocked lot
- tự mark delivered cuối cùng

## 6.4 Farm Agent
### Được làm
- tóm tắt plot / crop cycle
- nhắc việc
- gợi ý dự báo sản lượng
- tạo draft harvested lot

### Không được làm
- tự release lot cuối cùng nếu chưa qua policy

## 6.5 Executive / Supervisor Agent
### Được làm
- tổng hợp đa role
- phát hiện xung đột
- nhắc việc xuyên bộ phận
- gom lỗi / cảnh báo cho founder hoặc admin

### Không được làm
- có quyền rộng hơn từng domain owner
- viết thẳng truth vào core

`qc_reviewer` là top-level business role riêng cho QC lane; agent phục vụ QC vẫn không được tự lấy vai trò này nếu không có delegated execution contract được implement riêng.

---

## 7. Pattern an toàn nên dùng

### Pattern A - Suggest → Human Approve → Execute
Dùng cho:
- lot release nhạy cảm
- refund
- allocation override
- cancel sau packed

### Pattern B - Suggest → Deterministic Validate → Execute
Dùng cho:
- tạo draft order
- update segment
- update follow-up task
- create note
- tạo candidate preference

### Pattern C - Auto Execute trong vùng an toàn
Dùng cho:
- gửi nhắc việc nội bộ
- tóm tắt dashboard
- tạo draft message
- gắn low-risk tag

---

## 8. Tool design cho agent

Nên dùng tool purpose-specific, ví dụ:
- `get_customer_profile`
- `get_preorder_balance`
- `get_available_lots`
- `create_order_draft`
- `suggest_allocation`
- `prepare_message_draft`
- `create_preference_candidate`

Không nên dùng:
- shell toàn năng
- query tự do vào DB canonical
- tool sửa raw tables trực tiếp

---

## 9. Context boundary

Mỗi agent chỉ nên được cấp:
- đúng dữ liệu cần thiết
- đúng tool cần thiết
- đúng memory cần thiết

Ví dụ:
- CRM agent không cần thấy accounting raw
- farm agent không cần thấy toàn bộ chat history
- ops agent không cần mọi preference riêng tư

---

## 10. Dữ liệu AI được phép ghi

### Được ghi trực tiếp
- draft
- note
- suggestion
- summary
- candidate tags
- candidate preference
- draft message

### Chỉ được ghi sau validation / approval
- confirmed order draft
- confirmed preference
- allocation
- lot release
- payment update
- state change quan trọng

### Chưa được ghi qua bypass lane ở Phase 1
- canonical order / preorder / lot state changes
- QC review final decision
- audit / permission override
- packed-or-later cancellation

---

## 11. Guardrails kỹ thuật

Phase đầu nên có:
- max tool calls mỗi run
- max tokens
- timeout
- deny list action nhạy cảm
- approval hooks
- audit trail cho mọi action của agent

Phase sau mới nâng dần:
- model routing
- richer memory
- supervisor orchestration

---

## 12. Chỉ số để đánh giá agent

- suggestion acceptance rate
- false suggestion rate
- human override rate
- time saved
- escalation rate
- failed tool call rate
- số run đụng action nhạy cảm

Nếu chưa đo được các chỉ số này, chưa nên mở rộng quyền cho agent.

## 13. Lộ trình agent hóa

### Phase 1
AI đọc và gợi ý

### Phase 2
AI tạo draft + operator duyệt

### Phase 3
AI auto-execute trong vùng rất an toàn

### Phase 4
Supervisor agent điều phối nhiều sub-agent

Không nên nhảy từ phase 1 lên phase 4 quá sớm.

## 14. Kết luận

AI càng mạnh, deterministic core càng phải rõ.
Nếu core mơ hồ:
- AI sẽ đoán
- team sẽ khó debug
- source of truth sẽ bị mờ

Nói ngắn:
**AI chỉ nên tăng tốc hệ thống đã rõ luật, không nên thay thế luật.**
