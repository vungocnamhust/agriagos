# 06. State Transitions

## 1. Mục tiêu

Tài liệu này mô tả các trạng thái chính và chuyển trạng thái hợp lệ.

Nguyên tắc:
- state chính không được mơ hồ
- một state phải có ý nghĩa nghiệp vụ rõ
- state phải đủ ít để team vận hành hiểu nhanh
- AI không được tự tạo state lạ ngoài spec

State machine chi tiết xem ở:
- [State Machines: CropTask, Lot, Order](../agri_diagrams/05-state-machines-croptask-lot-order.md)

## 2. Quy tắc dùng state

### 2.1 State là “ảnh hiện tại”, không phải lịch sử
Lịch sử đi ở event log.  
State chỉ trả lời: object này đang ở đâu trong workflow.

### 2.2 Không tạo state chỉ vì “nghe kỹ thuật hơn”
State nào được giữ lại phải có ít nhất một trong ba lý do:
- ảnh hưởng quyền thao tác
- ảnh hưởng workflow kế tiếp
- ảnh hưởng logic báo cáo / vận hành

### 2.3 Nếu có state quan trọng, phải có guard rõ
Ví dụ:
- chỉ lot `released` mới được allocate
- chỉ order `packed` mới được ship
- chỉ order `delivered` mới được consume preorder quota

### 2.4 Phân biệt `canonical state vocabulary` và `gateway-enforced subset`
Tài liệu này chốt hai lớp khác nhau:
- **canonical state vocabulary**: tập state mà domain được phép dùng để mô tả thực tế vận hành
- **gateway-enforced subset hiện tại**: tập transition đang được `Command Gateway` enforce trong implementation phase đầu

Rule đọc tài liệu:
- nếu state đã có trong enum và trong tài liệu này, nó là state hợp lệ của domain
- nếu transition chưa có trong gateway, coi đó là **policy chưa được enforce đầy đủ**, không phải lý do để tự ý bỏ qua guard
- phase đầu phải ưu tiên khớp `gateway.py` trước khi mở rộng state machine phức tạp hơn

---

## 3. Customer state

### State gợi ý
- `active`
- `inactive`
- `blocked`

### Khi nào dùng
- `active`: dùng bình thường
- `inactive`: không còn tương tác thường xuyên hoặc tạm dừng
- `blocked`: cần hạn chế xử lý đặc biệt

### Transition
- active → inactive
- inactive → active
- active → blocked
- blocked → active

### Ghi chú
Phase đầu không cần làm customer state quá phức tạp.

---

## 4. Preorder state

### State
- `draft`
- `confirmed`
- `active`
- `completed`
- `cancelled`

### Ý nghĩa
- `draft`: mới nhập, chưa chốt
- `confirmed`: điều khoản chính đã chốt
- `active`: đang còn quota để giao dần
- `completed`: đã giao đủ hoặc kết thúc hợp lệ
- `cancelled`: bị hủy

### Transition hợp lệ
- draft → confirmed
- confirmed → active
- active → completed
- draft → cancelled
- confirmed → cancelled
- active → cancelled

### Guard quan trọng
- không đi từ `completed` về `active`
- nếu quantity thay đổi sau `confirmed`, phải có event log
- chỉ `delivered` mới được consume quota thật
- `remaining_qty` là quota còn có thể allocate, không phải điều kiện duy nhất để `completed`
- `completed` chỉ đúng khi nghĩa vụ giao còn lại theo `committed_qty - delivered_qty - cancelled_qty` về 0

### Gateway-enforced subset hiện tại
Trong implementation hiện tại của `app/core/gateway.py`, preorder đang enforce các transition sau:
- `draft -> confirmed`
- `draft -> cancelled`
- `confirmed -> confirmed` qua action `adjust`
- `confirmed -> active`
- `confirmed -> cancelled`
- `active -> active` qua action `adjust`
- `active -> cancelled`

---

## 5. Order state

### State
- `draft`
- `confirmed`
- `allocated`
- `partially_allocated`
- `packed`
- `partially_packed`
- `shipped`
- `delivered`
- `partially_delivered`
- `cancel_requested`
- `cancelled`
- `failed`

### Ý nghĩa ngắn
- `draft`: order mới tạo, chưa chốt
- `confirmed`: đã sẵn sàng đi tiếp
- `allocated`: mọi line đã có hàng
- `partially_allocated`: mới có một phần
- `packed`: đã đóng gói đầy đủ
- `partially_packed`: mới đóng được một phần
- `shipped`: đã xuất đi
- `delivered`: khách nhận thành công
- `partially_delivered`: giao được một phần
- `cancel_requested`: đã có yêu cầu hủy
- `cancelled`: hủy hoàn tất
- `failed`: một lỗi vận hành cần xử lý thủ công

### Transition hợp lệ
- draft → confirmed
- confirmed → allocated
- confirmed → partially_allocated
- allocated → packed
- partially_allocated → partially_packed
- packed → shipped
- shipped → delivered
- shipped → partially_delivered
- confirmed → cancel_requested
- allocated → cancel_requested
- packed → cancel_requested
- cancel_requested → cancelled
- shipped → failed

### Guard quan trọng
- chỉ allocate nếu lot `released`
- chỉ pack nếu order có allocation hợp lệ
- chỉ ship nếu order đã packed ở mức chấp nhận được
- chỉ `delivered` mới tăng lịch sử mua thật
- cancel sau packed thường phải approval

### Gateway-enforced subset hiện tại
`app/core/gateway.py` hiện enforce chắc các transition sau:
- `draft -> confirmed`
- `draft -> cancelled`
- `confirmed -> allocated | partially_allocated` qua action `allocate`
- `partially_allocated -> allocated` qua action `allocate`
- `partially_allocated -> partially_packed` qua action `pack`
- `partially_allocated -> cancel_requested`
- `confirmed -> cancelled`
- `allocated -> packed | partially_packed`
- `partially_packed -> packed`
- `allocated -> cancel_requested`
- `packed -> shipped`
- `packed -> cancel_requested`
- `cancel_requested -> cancelled`
- `shipped -> delivered | partially_delivered`
- `partially_delivered -> delivered`

State `failed` vẫn thuộc canonical vocabulary của domain, nhưng chưa phải gateway-enforced subset của phase đầu.

---

## 6. Order Line state

### State
- `open`
- `allocated`
- `packed`
- `delivered`
- `cancelled`

### Vì sao cần line-level state
Để xử lý đúng các case:
- đơn nhiều mặt hàng
- giao thiếu
- chia nhiều đợt
- lấy hàng từ nhiều lot

Nếu chỉ có order-level state thì nhiều case sẽ bị mơ hồ.

---

## 7. Lot state

### State
- `draft`
- `harvested`
- `qc_pending`
- `released`
- `blocked`
- `depleted`
- `closed`

### Ý nghĩa
- `draft`: mới tạo, chưa chốt đủ dữ liệu
- `harvested`: đã ghi nhận thu hoạch / sản xuất
- `qc_pending`: đang chờ kiểm hoặc chờ release condition
- `released`: được phép allocate
- `blocked`: tạm ngừng dùng
- `depleted`: đã dùng hết quantity có ý nghĩa
- `closed`: kết thúc vòng đời

### Transition hợp lệ
- draft → harvested
- harvested → qc_pending
- harvested → released
- harvested → blocked
- qc_pending → released
- qc_pending → blocked
- released → blocked
- blocked → qc_pending
- released → depleted
- depleted → closed

### Guard quan trọng
- chỉ `released` mới được allocate
- lot `qc_pending` chỉ được release khi qua QC guard tối thiểu
- `blocked` không được allocate
- `block` phải đóng phần `available_qty` chưa allocate; `unblock` không tự mở lại inventory
- `depleted` nghĩa là quantity còn lại không đủ ý nghĩa vận hành

### Gateway-enforced subset hiện tại
`app/core/gateway.py` hiện enforce chắc các transition sau:
- `harvested -> released`
- `harvested -> blocked`
- `qc_pending -> released`
- `qc_pending -> blocked`
- `released -> blocked`
- `blocked -> qc_pending`

Các state `draft`, `qc_pending`, `depleted`, `closed` vẫn là canonical vocabulary của lot lifecycle, nhưng chưa được gateway phase đầu đi hết.

Lưu ý quan trọng:
- phase hiện tại mở lại lane kiểm tra bằng `blocked -> qc_pending`, không release trực tiếp từ `blocked`
- unblock không tự mở available quantity; lot chỉ mở inventory lại sau một lệnh release hợp lệ

---

## 8. Allocation state

### State
- `active`
- `released`
- `consumed`
- `cancelled`

### Ý nghĩa
- `active`: đang giữ chỗ cho order
- `released`: bỏ giữ chỗ, trả lại lot
- `consumed`: đã tiêu thụ thật qua pack / deliver logic
- `cancelled`: allocation bị hủy

### Guard quan trọng
- allocation không được tồn tại mà không có order line và lot hợp lệ
- khi allocation chuyển `released` hoặc `cancelled`, inventory movement phải phản ánh lại

---

## 9. Delivery state

### State
- `pending`
- `shipped`
- `delivered`
- `partially_delivered`
- `failed`
- `returned`

### Guard quan trọng
- `delivered` là mốc để:
  - cập nhật lịch sử mua
  - consume preorder quota
  - đẩy CRM follow-up sau mua
- `shipped` chưa đủ để coi là hoàn tất

---

## 10. Payment state

### State
- `unpaid`
- `partially_paid`
- `paid`
- `refunded`
- `writeoff`

### Ghi chú
Payment state trong core là trạng thái vận hành.  
Accounting final vẫn chốt ở ERP nếu phase đó đã có sync chuẩn.

### Rule baseline
- fulfillment và workflow vận hành nhìn vào payment state của core
- reconcile accounting nhìn vào ERP final state
- nếu hai hệ lệch nhau, không overwrite âm thầm; phải gắn cờ `needs_reconciliation`

---

## 11. Crop Cycle state

### State
- `planned`
- `active`
- `near_harvest`
- `harvested`
- `closed`
- `cancelled`

### Transition
- planned → active
- active → near_harvest
- near_harvest → harvested
- harvested → closed
- planned → cancelled
- active → cancelled

---

## 12. Growth Stage values

Phase đầu nên giữ đơn giản:
- `seeded`
- `growing`
- `maturing`
- `harvest_window`
- `harvested`

Không cần vi mô quá nếu hiện trường chưa dùng nổi.

---

## 13. Guard examples

### Order allocation guard
- chỉ allocate nếu order ở `confirmed` hoặc tương đương hợp lệ
- chỉ allocate từ lot `released`

### Packing guard
- chỉ pack nếu có allocation hợp lệ
- nếu quantity thiếu, phải ghi state phù hợp

### Delivery guard
- chỉ mark delivered nếu có xác nhận đủ mạnh theo policy

### Preorder consumption guard
- chỉ consume quota khi order hoặc line thật sự `delivered`

### Lot release guard
- chỉ release nếu lot có đủ dữ liệu tối thiểu và không bị blocked bởi policy

### Preference confirmation guard
- candidate từ CRM, AI, hoặc operator note không tự thành canonical preference
- chỉ role được phép mới được xác nhận preference thành truth vận hành
- action xác nhận phải phát sinh `CustomerPreferenceUpdated` và audit log

---

## 14. Cách implement practical

### Phase đầu
- lưu state hiện tại ngay trên bản ghi chính
- lưu history bằng event log

### Phase sau
- nếu workflow đủ phức tạp, thêm state machine guard / policy engine riêng
- nhưng không cần nhảy vào engine tổng quát quá sớm

## 15. Kết luận

State model tốt là state model mà:
- ops đọc hiểu được
- dev code đúng được
- audit lần ngược được
- AI không thể “đoán đại rồi tự ghi”

Nếu có tranh luận về state, quay lại hỏi:
- state này có đổi quyền hay workflow không?
- nếu bỏ nó đi, team vận hành có bị mơ hồ không?
