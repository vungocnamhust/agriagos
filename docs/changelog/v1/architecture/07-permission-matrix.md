# 07. Permission Matrix

## 1. Mục tiêu

Tài liệu này trả lời 4 câu hỏi:
- ai được xem gì
- ai được sửa gì
- ai được phê duyệt gì
- AI/Agent được chạm vào đâu

Nguyên tắc:
- **least privilege**
- role-based trước, attribute-based sau nếu cần
- AI không được rộng quyền hơn role người mà nó phục vụ

Role / permission diagram xem ở:
- [Role-based View / Permission Diagram](../agri_diagrams/08-role-based-view-permission-diagram.md)

## 2. Các vai trò chính

- Founder / Super Admin
- Admin vận hành
- Sales
- CSKH
- Ops / Kho / Đóng gói
- Farm Manager
- Accountant
- Viewer / Analyst
- Agent / Automation

---

## 3. Quy tắc nền

### 3.1 Quyền xem khác quyền sửa
Người thấy được dữ liệu không đồng nghĩa người đó được phép đổi dữ liệu đó.

### 3.2 Quyền duyệt là một lớp riêng
Một số action không nên ai tạo ra action đó cũng tự duyệt luôn.

### 3.3 Agent chỉ được “mượn quyền”
Agent không tự có vai trò độc lập mạnh hơn con người.
Nó chỉ được làm trong vùng mà role gốc cho phép.

### 3.4 Dữ liệu nhạy cảm nên ưu tiên read model thay vì raw table
Ví dụ:
- sales nên xem customer 360
- ops nên xem fulfillment board
- farm manager nên xem farm summary
thay vì ai cũng đụng raw model toàn hệ

---

## 4. Phạm vi quyền theo domain

## 4.1 Founder / Super Admin
### Được làm
- xem toàn bộ
- cấu hình hệ thống
- chỉnh permission
- approve action nhạy cảm
- override trong trường hợp đặc biệt

### Điều kiện
- mọi override phải có audit log
- không khuyến khích dùng override như lối đi thường xuyên

---

## 4.2 Admin vận hành
### Được làm
- xem gần như toàn bộ operational data
- tạo / sửa customer, preorder, order
- theo dõi lot, allocation, packing, delivery
- điều phối liên phòng ban
- xem lỗi sync / retry / queue

### Không nên làm trực tiếp
- chốt accounting final
- bypass policy mà không để lại log
- tự mở rộng permission của chính mình

---

## 4.3 Sales
### Được xem
- customer profile cần cho bán hàng
- preorder
- order
- delivery summary
- preference / segment cần thiết

### Được sửa
- tạo customer
- tạo preorder
- tạo order
- cập nhật note bán hàng

### Không được
- release lot
- chỉnh inventory movement
- chốt payment final
- override allocation

---

## 4.4 CSKH
### Được xem
- customer profile
- order / preorder status
- delivery status
- purchase history
- preference timeline

### Được sửa
- note CSKH
- feedback
- preference candidate
- lịch follow-up

### Không được
- chỉnh allocation
- release lot
- sửa payment amount final

---

## 4.5 Ops / Kho / Đóng gói
### Được xem
- order cần xử lý
- available lots
- allocation records
- packing queue
- shipping status

### Được sửa
- allocate lot theo policy
- pack hàng
- cập nhật shipping status vận hành
- xử lý reserve / release reserve theo flow cho phép

### Không được
- sửa customer core info
- sửa preorder terms
- sửa payment final
- tự un-block lot nếu policy không cho

---

## 4.6 Farm Manager
### Được xem
- plot
- crop cycle
- expected harvest
- lots của vùng phụ trách

### Được sửa
- plot summary
- crop cycle summary
- tạo harvested lot
- cập nhật growth stage summary

### Có thể được làm
- đề xuất release lot
- release lot nếu được phân vai và policy cho phép

### Không được
- sửa customer / preorder / payment
- thao tác CRM

---

## 4.7 Accountant
### Được xem
- order
- payment summary
- delivery summary
- sync trạng thái với ERP

### Được sửa
- payment status vận hành theo policy
- reconciliation note
- ERP sync reference

### Không được
- can thiệp allocation
- can thiệp lot release nếu không có vai trò ops/qc phù hợp

---

## 4.8 Viewer / Analyst
### Được xem
- dashboard
- report
- read models được cấp quyền

### Không được
- chạm vào write model
- chạy action nghiệp vụ

---

## 4.9 Agent / Automation
### Được làm
- đọc dữ liệu trong scope cần thiết
- tạo suggestion
- tạo draft
- gửi nhắc việc
- tạo summary
- gọi workflow mềm trong vùng an toàn

### Không được làm trực tiếp
- mark delivered cuối cùng
- release lot cuối cùng nếu là action nhạy cảm
- chỉnh available quantity
- chỉnh payment amount cuối cùng
- sửa permission
- override source of truth

---

## 5. Ma trận tóm tắt theo domain

| Domain | Founder | Admin | Sales | CSKH | Ops | Farm Manager | Accountant | Viewer | Agent |
|---|---|---|---|---|---|---|---|---|---|
| Customer xem | full | full | yes | yes | limited | no | limited | yes | scoped |
| Customer sửa | full | full | partial | partial | no | no | no | no | no direct |
| Preorder xem | full | full | yes | yes | limited | no | limited | yes | scoped |
| Preorder tạo/sửa | full | full | yes | limited | no | no | no | no | propose only |
| Order xem | full | full | yes | yes | yes | limited | yes | yes | scoped |
| Order tạo/sửa | full | full | yes | limited | limited | no | no | no | propose only |
| Lot xem | full | full | limited | limited | yes | yes | limited | yes | scoped |
| Lot tạo | full | full | no | no | yes | yes | no | no | no direct |
| Lot release/block | full | full | no | no | limited | limited/yes theo policy | no | no | no direct |
| Allocation | full | full | no | no | yes | no | no | no | suggest only |
| Plot/Crop xem | full | full | limited | no | yes | yes | no | yes | scoped |
| Plot/Crop sửa | full | full | no | no | limited | yes | no | no | no direct |
| Payment status xem | full | full | limited | limited | limited | no | yes | yes | scoped |
| Payment chỉnh | full | limited | no | no | no | no | yes | no | no direct |
| Config / Permission | full | limited | no | no | no | no | no | no | no |

---

## 6. Các action nhạy cảm cần approval

Bắt buộc approval trong phase đầu:
- lot release trong case đặc biệt
- refund / payment adjustment
- order cancellation sau packing
- allocation override
- permission change
- agent muốn execute thay vì chỉ suggest

## 7. Pattern an toàn nên dùng với AI

### Pattern A - Suggest → Human Approve → Execute
Dùng cho:
- lot release nhạy cảm
- refund
- allocation override
- cancellation sau packed

### Pattern B - Suggest → Deterministic Validate → Execute
Dùng cho:
- tạo draft order
- update segment
- tạo follow-up task

### Pattern C - Auto Execute trong vùng an toàn
Dùng cho:
- gửi nhắc việc nội bộ
- tóm tắt dashboard
- tạo note / draft message
- gắn tag low-risk

---

## 8. Audit requirements

Mọi action nhạy cảm phải log:
- ai làm
- lúc nào
- object nào bị tác động
- trước / sau thay đổi gì
- lý do nếu override hoặc reject
- correlation id nếu thuộc một flow lớn

---

## 9. Permission roadmap

### Phase 1
- role-based đơn giản
- scope dữ liệu chủ yếu theo role

### Phase 2
- thêm data scope theo team / vùng / owner

### Phase 3
- thêm policy engine chi tiết nếu workflow đủ phức tạp

Không nên nhảy vào policy engine quá sớm nếu team còn chưa ổn workflow thật.

## 10. Kết luận

Permission tốt không phải permission “rất thông minh”.  
Permission tốt là:
- dễ hiểu
- đủ chặt
- audit được
- không cho AI quyền rộng hơn con người
