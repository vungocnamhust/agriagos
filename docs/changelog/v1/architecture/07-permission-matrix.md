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
- [Role-based View / Permission Diagram](../diagram/08-role-based-view-permission-diagram.md)

## 2. Các vai trò chính

- Founder / Super Admin
- Admin vận hành
- Sales
- CSKH
- Ops / Kho / Đóng gói
- Farm Manager
- QC Reviewer
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

### 3.5 Baseline policy trước, gateway enforcement theo sau
Permission matrix này là baseline policy mà write path phải đi tới.

Phase đầu cần hiểu rõ:
- không phải mọi rule ở đây đã được gateway enforce đầy đủ
- nhưng implementation mới không được đi ngược baseline này
- nếu current code chưa enforce đủ, phần thiếu phải được coi là debt có chủ đích chứ không phải permission ngầm

### 3.6 Organization baseline policy
`Organization` là business owner aggregate mới trong baseline kiến trúc. Phase 1 hiện đã có standalone runtime auth surface cho Organization CRUD + activate/pause/close.

Policy baseline cho runtime hiện tại và các slice tiếp theo:
- Founder / Super Admin và Admin vận hành là nhóm chính được tạo, sửa, kích hoạt, tạm dừng, hoặc đóng organization
- Sales, CSKH, Ops, Farm Manager, Accountant, Viewer không mặc định có quyền mutate organization aggregate
- raw read lane cho organization aggregate hiện cũng chỉ mở cho Founder / Super Admin / Admin
- việc một role nào đó được thao tác records thuộc một organization không tự động đồng nghĩa role đó được sửa organization aggregate
- org-scoped RBAC/ABAC và membership theo organization là phase sau, không được ngầm giả định đã tồn tại

### 3.7 ProjectScope baseline policy
`ProjectScope` là lớp soft scope dưới `Organization`. Runtime Phase 1 hiện đã cover aggregate `ProjectScope`, assignment / contribution lanes, cost-record lane đầu tiên, revenue-record lane đầu tiên, và read-model `project-contribution-summary` cùng `project-pnl-summary`; các policy lanes sâu hơn vẫn rollout dần theo slices sau.

Policy baseline:
- Founder / Super Admin và Admin là nhóm chính được tạo, sửa, activate, pause, close, archive `ProjectScope`
- Farm Manager, Ops, Sales có thể là owner nghiệp vụ của records nằm trong một scope, nhưng không mặc định có quyền mutate `ProjectScope` aggregate
- việc một role được gắn record vào scope không tự động đồng nghĩa role đó được sửa scope profile hoặc parent-child grouping
- assignment sang `ProjectScope` nên mở theo domain-owner lane: Farm Manager cho plot/crop/lot, Sales hoặc Admin cho preorder/order/customer source, Ops cho inventory movement, Accountant hoặc Admin cho financial allocations
- confirmation của contribution hoặc financially eligible assignment là lane nhạy cảm; Founder / Super Admin / Admin là baseline approvers, có thể mở thêm approver role riêng ở phase sau
- P&L theo `ProjectScope` là read surface nhạy cảm; Founder / Super Admin / Admin / Accountant là baseline readers, Viewer / Analyst chỉ nên vào qua read models được duyệt
- project-scoped membership, per-scope ABAC, và delegated agent permissions là phase sau; docs này không ngầm khẳng định runtime đã enforce các lane đó

---

## 4. Phạm vi quyền theo domain

## 4.1 Founder / Super Admin
### Được làm
- xem toàn bộ
- cấu hình hệ thống
- chỉnh permission
- approve action nhạy cảm
- override trong trường hợp đặc biệt
- tạo / sửa / activate / pause / close organization khi policy cho phép

### Điều kiện
- mọi override phải có audit log
- không khuyến khích dùng override như lối đi thường xuyên

---

## 4.2 Admin vận hành
### Được làm
- xem gần như toàn bộ operational data
- query event log và audit log phục vụ debug / điều phối vận hành
- tạo / sửa customer, preorder, order
- theo dõi lot, allocation, packing, delivery
- điều phối liên phòng ban
- xem lỗi sync / retry / queue
- tạo / sửa / activate / pause organization theo policy baseline

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
- xác nhận preference candidate thành preference dùng cho workflow
- review duplicate candidate của customer khi cần giữ canonical identity sạch

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
- xác nhận preference candidate theo guard chuẩn của core workflow
- review duplicate candidate khi cần phân biệt đúng hồ sơ khách

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
- xác nhận preference canonical
- review duplicate candidate canonical

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
- tự xác nhận accounting reconcile

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
- xác nhận hoặc escalate conflict giữa Core operational payment state và ERP accounting final state

### Không được
- can thiệp allocation
- can thiệp lot release nếu không có vai trò ops/qc phù hợp
- tự sửa customer preference canonical

---

## 4.8 QC Reviewer
### Được xem
- lot evidence
- QC review history
- các read surface liên quan QC đã được cấp quyền

### Được sửa
- tạo QC review
- cập nhật QC note / approval evidence theo policy

### Không được
- thao tác order, preorder, customer như role vận hành chung
- release lot
- sửa payment final

---

## 4.9 Viewer / Analyst
### Được xem
- dashboard
- report
- read models được cấp quyền
- short-term ưu tiên qua `/api/v1/views/*` và scoped `/api/v1/events`

Ghi chú:
- không phải mọi read model đều mở cho viewer / analyst theo mặc định
- `customer_360` vẫn chỉ mở cho các role trực tiếp phục vụ customer workflow nếu permission matrix không nói khác

### Không được
- chạm vào write model
- chạy action nghiệp vụ
- mặc định không đọc raw operational routes nếu đã có read model phù hợp

---

## 4.10 Agent / Automation
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
- xác nhận preference canonical
- review duplicate candidate canonical
- tự approve reconcile giữa Core và ERP

### Bypass mechanism
- kiến trúc phải chừa sẵn cơ chế biểu diễn bypass lane để sau này mở các lane hẹp có audit
- Phase 1 hiện chưa enable bất kỳ bypass lane nào cho agent / automation
- mọi bypass request ở phase hiện tại phải bị deny và audit rõ ràng

### Guard cho trusted integration trên customer preference
- integration chỉ được xác nhận trực tiếp preference canonical khi request mang `actorRole=integration`, có `actorId`, và có `externalRef`
- nếu thiếu một trong ba guard trên, integration payload chỉ được coi là candidate/input chứ không được canonicalize trực tiếp
- duplicate candidate review không mở cho integration hoặc agent path trong phase hiện tại

---

## 5. Ma trận tóm tắt theo domain

| Domain | Founder | Admin | Sales | CSKH | Ops | Farm Manager | QC Reviewer | Accountant | Viewer | Agent |
|---|---|---|---|---|---|---|---|---|---|---|
| Customer xem | full | full | yes | yes | limited | no | no | limited | no | scoped |
| Customer sửa | full | full | partial | partial | no | no | no | no | no | no direct |
| Preorder xem | full | full | yes | yes | limited | no | no | limited | no raw, use views only | scoped |
| Preorder tạo/sửa | full | full | yes | limited | no | no | no | no | no | propose only |
| Order xem | full | full | yes | yes | yes | limited | no | yes | no raw, use views only | scoped |
| Order tạo/sửa | full | full | yes | limited | limited | no | no | no | no | propose only |
| Lot xem | full | full | limited | limited | yes | yes | yes scoped | limited | read model only | scoped |
| Lot tạo | full | full | no | no | yes | yes | no | no | no | no direct |
| Lot release/block/unblock | full | full | no | no | limited | limited/yes theo policy | no | no | no | no direct |
| Lot evidence / QC review | full | full | no | no | limited | limited | yes | no | no | no direct |
| Allocation | full | full | no | no | yes | no | no | no | no | suggest only |
| Plot/Crop xem | full | full | limited | no | yes | yes | limited | no | `/views/farm*` only | scoped |
| Plot/Crop sửa | full | full | no | no | limited | yes | no | no | no | no direct |
| Payment status xem | full | full | limited | limited | limited | no | no | yes | no | scoped |
| Payment chỉnh | full | limited | no | no | no | no | no | yes | no | no direct |
| Event log query | full | yes scoped | no | no | no | no | no | limited scoped | scoped only | no direct |
| Audit log query | full | yes | no | no | no | no | no | limited | no | no direct |
| Preference confirm | full | yes | yes | yes theo policy | no | no | no | no | no | no direct |
| Duplicate candidate review | full | yes | yes | yes theo policy | no | no | no | no | no | no direct |
| ERP reconcile approve | full | limited | no | no | no | no | no | yes | no | no direct |
| Config / Permission | full | limited | no | no | no | no | no | no | no | no |

---

## 6. Các action nhạy cảm cần approval

Bắt buộc approval trong phase đầu:
- lot release trong case đặc biệt
- refund / payment adjustment
- order cancellation sau packing
- allocation override
- reconcile conflict giữa Core operational state và ERP accounting final state
- permission change
- agent muốn execute thay vì chỉ suggest

### Action nào cần ai approve
| Action nhạy cảm | Người khởi tạo hợp lệ | Người approve hợp lệ |
|---|---|---|
| Cancel order sau `packed` | Admin, Ops | Founder hoặc Admin vận hành theo policy |
| Lot release case đặc biệt | Farm Manager, Ops | Admin vận hành hoặc Founder |
| Payment adjustment / refund | Accountant | Founder hoặc Admin vận hành |
| ERP reconcile conflict | Accountant | Founder hoặc Admin vận hành |
| Allocation override | Ops | Admin vận hành |
| Preference confirm từ candidate có tác động workflow | Sales, CSKH, Admin | Không cần lớp approve riêng, nhưng bắt buộc audit log |

Phase 1 implementation note:
- raw `/api/v1/customers`, `/api/v1/customers/{customer_id}`, `/api/v1/customers/duplicate-candidates`, và `/api/v1/customers/{customer_id}/duplicate-candidates` hiện enforce Founder / Super Admin / Admin / Sales / CSKH ở service layer; Ops, Accountant, Viewer, và raw agent reads bị deny trên lane này
- `Customer xem = limited/scoped` cho Ops, Accountant, Agent nên hiểu là qua customer-facing views hoặc tool/read surface riêng theo role, không phải raw customer routes trong Phase 1
- raw `/api/v1/orders*` reads and write commands now enforce the matrix directly in the service layer; Viewer remains denied on raw order access and agent lanes stay proposal-only
- raw `/api/v1/lots/{lot_id}` reads plus `/evidence` and `/qc-reviews` readbacks now enforce operational-only access in the service layer; current readers are Founder / Super Admin, Admin, Ops, Farm Manager, và QC Reviewer
- lot create commands (`POST /api/v1/lots`, `POST /api/v1/lots/processed`) now require Founder / Super Admin / Admin / Ops / Farm Manager; lot adjust/release/block/unblock uses the same write lane, while evidence add and QC review also admit `qc_reviewer`
- packed-or-later order cancel vẫn còn một divergence implementation: service hiện chỉ gate theo role và chưa enforce `approvalRef`; theo dõi tại `DL-20260412-02` trong divergence ledger
- route `ReleaseLot` hiện chỉ mang `approvalRef` như approval evidence cho case đặc biệt; identity của người approve vẫn thuộc audit/workflow ngoài request schema và chưa được enforce như field riêng ở public API
- khi thiếu `approvalRef` cho lot release nhạy cảm, service hiện ghi audit decision `escalated` với `reason_code=approval_required` và metadata tối thiểu như `requiredApprovalRef`, `requiredApproverRoles`, `escalationOwner` trước khi trả `403`

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

Phase 1 readback note:
- `GET /api/v1/audit` là operator/debug surface để query audit decisions
- intended roles hiện tại: Founder / Super Admin, Admin vận hành, và Accountant khi cần lần lại operational payment / reconcile trail
- quyền đọc endpoint này đã đi qua shared read authz ở Phase 1; các role khác bị deny và ghi audit `audit.query`

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
