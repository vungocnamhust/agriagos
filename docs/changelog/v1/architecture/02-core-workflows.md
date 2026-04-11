# 02. Core Workflows

## 1. Mục tiêu của tài liệu này

Tài liệu này mô tả các workflow lõi mà hệ thống **phải chạy được trước khi agent hóa mạnh**.

Nguyên tắc:
- mỗi workflow phải có actor, input, rule, output, event
- mô tả bằng ngôn ngữ dễ hiểu
- tập trung vào use case thật, không mô hình hóa cho đẹp
- ưu tiên vertical slice: UI → API → business rule → DB → event log

## 2. Danh sách workflow lõi

Phase đầu chỉ cần khóa 7 workflow này:

1. Tạo và quản lý khách hàng
2. Preorder / đặt trước
3. Plot / crop cycle cơ bản
4. Tạo lot thu hoạch
5. Release lot
6. Tạo order và allocate lot
7. Packing / delivery / cập nhật lịch sử mua

Các workflow này liên kết với 3 sequence diagrams:
- [PreorderPlaced](../agri_diagrams/09-sequence-preorder-placed.md)
- [HarvestedLotCreated → LotReleased](../agri_diagrams/10-sequence-harvestedlot-to-lotreleased.md)
- [OrderAllocated → OrderDelivered](../agri_diagrams/11-sequence-orderallocated-to-orderdelivered.md)

---

## 3. Workflow A - Tạo và quản lý khách hàng

### Mục tiêu
Tạo hồ sơ khách đủ dùng để:
- nhận diện khách
- gắn lịch sử mua
- gắn preorder
- phục vụ sales / CSKH
- làm canonical identity cho các hệ khác

### Actor
- Sales
- CSKH
- Admin
- System sync từ CRM / form / chat

### Input tối thiểu
- tên
- số điện thoại
- kênh đến
- khu vực hoặc địa chỉ tối thiểu
- ghi chú ban đầu nếu có

### Rule chính
- một số điện thoại không được tạo ra 2 hồ sơ chính thức khác nhau một cách vô tình
- nếu nghi trùng, tạo **candidate merge** thay vì merge tự động
- customer phải có `customer_code` ổn định
- nếu đến từ CRM hoặc chat channel, phải ghi lại `external mapping`

### Output
- customer profile
- customer code
- mapping với external systems nếu có
- event log

### Event tối thiểu
- `CustomerCreated`
- `CustomerUpdated`
- `CustomerMerged`
- `CustomerPreferenceUpdated`

---

## 4. Workflow B - Preorder / đặt trước

### Bài toán
Khách cam kết mua trước một lượng hàng, nhưng **chưa giao ngay**.

Ví dụ:
- khách đặt trước 100kg gạo vụ tới
- giao dần theo đợt
- quota phải được giữ rõ ràng

### Actor
- Sales
- CSKH
- Admin
- Customer qua form / chat / điện thoại

### Input
- customer
- sản phẩm
- quantity cam kết
- nhịp giao dự kiến
- ngày bắt đầu
- deposit hoặc ghi chú nếu có

### Rule chính
- preorder là **cam kết**, chưa phải đơn giao ngay
- phải tách rõ:
  - `committed_qty`
  - `allocated_qty`
  - `delivered_qty`
  - `remaining_qty`
- không allocate vượt quota còn lại
- mọi thay đổi sau khi confirmed phải có log
- được phép giảm hoặc hủy preorder, nhưng không được “sửa âm thầm”

### Output
- preorder record
- quota balance
- lịch giao dự kiến
- event log

### Event tối thiểu
- `PreorderPlaced`
- `PreorderAdjusted`
- `PreorderActivated`
- `PreorderCancelled`
- `PreorderQuotaConsumed`
- `PreorderCompleted`

### Cách nghĩ đúng
Preorder là **cầu nối giữa thị trường và sản xuất**.  
Nó không phải chỉ là một “note bán hàng”.

---

## 5. Workflow C - Quản lý plot / crop cycle cơ bản

### Mục tiêu
Chưa làm nông học sâu, nhưng đủ để:
- biết đang trồng ở đâu
- đang ở kỳ sinh trưởng nào
- lúc nào dự kiến có hàng
- lô thu hoạch có thể trace ngược về đâu

### Actor
- Farm Manager
- Admin
- Ops farm
- Sync từ LiteFarm nếu có

### Input
- plot
- diện tích
- vị trí
- crop name
- plant count hoặc density nếu có
- growth stage
- expected harvest window

### Rule chính
- plot là thực thể nền, không nên tạo trùng
- crop cycle là vòng đời một vụ cụ thể trên plot
- lot thu hoạch phải truy được ngược về crop cycle
- nếu LiteFarm là source sâu, core chỉ giữ snapshot tối thiểu
- phase đầu mặc định build `plot/crop summary` trực tiếp trong Core
- chỉ khi integration phase chốt snapshot contract rõ ràng thì LiteFarm mới trở thành nguồn sâu cho tenant đó

### Output
- plot record
- crop cycle record
- growth stage summary
- expected harvest summary

### Event tối thiểu
- `PlotCreated`
- `CropCycleStarted`
- `GrowthStageUpdated`
- `ExpectedHarvestUpdated`
- `CropCycleClosed`

---

## 6. Workflow D - Tạo lot thu hoạch

### Bài toán
Khi có một đợt thu hoạch hoặc sơ chế tạo ra hàng vật lý, hệ phải tạo được `lot`.

### Actor
- Farm Manager
- Ops farm
- Admin
- Integration sync nếu có

### Input
- plot hoặc crop cycle nguồn
- ngày thu hoạch / sản xuất
- sản phẩm
- estimated quantity
- actual quantity
- note chất lượng cơ bản
- ảnh hoặc file đính kèm nếu có

### Rule chính
- lot phải có nguồn gốc rõ ràng
- lot code phải unique
- quantity phải có đơn vị đo chuẩn
- lot mới tạo chưa được allocate ngay nếu chưa release
- nếu quantity đổi sau này thì phải log adjustment

### Output
- lot record
- quantity thực tế
- trạng thái ban đầu của lot
- event log

### Event tối thiểu
- `HarvestedLotCreated`
- `HarvestedLotAdjusted`
- `LotQualityChecked`

---

## 7. Workflow E - Release lot

### Bài toán
Lot đã tồn tại, nhưng chỉ khi đủ điều kiện mới được coi là **hàng khả dụng để bán / allocate**.

### Actor
- QC
- Ops manager
- Admin

### Input
- lot id
- kết quả kiểm tối thiểu
- released quantity
- available quantity
- ghi chú nếu block hoặc release có điều kiện

### Rule chính
- chỉ lot ở trạng thái hợp lệ mới được release
- `released_qty` không được lớn hơn `actual_qty`
- blocked lot không được allocate
- release là quyết định nghiệp vụ, không phải chỉ là cập nhật một con số
- phase hiện tại đi theo direct action `release -> block -> unblock`; case nhạy cảm vẫn có thể đòi approval theo policy nhưng chưa có command/event tách riêng
- direct release từ lane `harvested` cho actor như Farm Manager hoặc Ops được coi là case nhạy cảm và phải mang `approval_ref`
- approval policy tối thiểu xem ở `07-permission-matrix.md`; state guard xem ở `06-state-transitions.md`

### Output
- lot state = `released`
- available quantity được mở
- event log
- lot xuất hiện ở board có thể allocate

### Event tối thiểu
- `LotReleaseRequested`
- `LotReleased`
- `LotReleaseAdjusted`
- `LotBlocked`
- `LotUnblocked`

---

## 8. Workflow F - Tạo order và allocate lot

### Bài toán
Từ nhu cầu giao cụ thể, hệ phải:
- tạo order
- xác định order này có lấy từ preorder hay không
- gắn lot vào order line đúng rule

### Actor
- Sales
- CSKH
- Admin
- Ops / kho
- Agent chỉ được suggest

### Input
- customer
- order lines
- source channel
- địa chỉ giao
- ngày giao
- payment intent
- reference preorder nếu có

### Rule chính
- order có thể:
  - bán lẻ thông thường
  - hoặc rút dần từ preorder
- nếu lấy từ preorder, phải giữ liên kết rõ
- chỉ allocate từ lot `released`
- không allocate vượt available quantity
- không consume delivered quantity của preorder cho đến khi order thật sự delivered
- policy chọn lot phải rõ: FIFO / FEFO / theo chất lượng / theo vùng
- allocation override hoặc cancel sau `packed` không được coi là action thường; phải đi qua approval policy
- AI chỉ được suggest allocation hoặc cancel path, không được tự approve

### Output
- order
- order lines
- allocation records
- reserved quantity trên lot
- event log

### Event tối thiểu
- `OrderCreated`
- `OrderConfirmed`
- `OrderAllocated`
- `OrderPartiallyAllocated`
- `AllocationAdjusted`
- `AllocationReleased`

### Ghi chú
Đây là chỗ dễ để AI “thấy hợp lý rồi tự làm bừa”.  
Trong phase đầu, AI chỉ được **gợi ý allocation**, không được chốt thay core.

Nếu workflow cần hủy sau `packed`, phải phát sinh `OrderCancelRequested` trước khi đi tới `OrderCancelled`.

---

## 9. Workflow G - Packing

### Actor
- Ops
- Kho
- Đóng gói

### Input
- order
- allocation records
- packed quantity thực tế
- note chênh lệch nếu có

### Rule chính
- chỉ order có allocation hợp lệ mới được pack
- packed quantity có thể lệch với allocated quantity, nhưng phải log
- nếu thiếu hàng, trạng thái order và line phải phản ánh rõ
- nếu thiếu hàng dẫn tới override allocation hoặc hủy một phần, action đó phải quay lại policy của order/allocation thay vì sửa tay quantity âm thầm

### Output
- packing record
- packed status
- event log

### Event tối thiểu
- `OrderPacked`
- `OrderPartiallyPacked`
- `OrderPackingAdjusted`

---

## 10. Workflow H - Delivery và cập nhật lịch sử mua

### Actor
- Ops
- Delivery
- Sales / CSKH
- Logistics sync nếu có

### Input
- packed order
- carrier / method
- delivery status
- delivered quantity
- COD / payment note nếu cần

### Rule chính
- phải phân biệt:
  - shipped
  - delivered
  - failed
  - partially delivered
- chỉ khi `delivered` mới:
  - tăng lịch sử mua thật
  - consume preorder quota
  - cập nhật last purchase
- `shipped` chưa đủ để coi là hoàn tất
- nếu logistics báo delivered nhưng policy core chưa xác nhận đủ mạnh, chưa được coi là delivered truth cuối cùng
- payment note ở bước delivery chỉ là operational note; accounting final vẫn reconcile với ERP theo policy riêng

### Output
- delivery record
- customer purchase history updated
- preorder consumption updated nếu có
- event log

### Event tối thiểu
- `OrderShipped`
- `OrderDelivered`
- `OrderPartiallyDelivered`
- `OrderDeliveryFailed`
- `PreorderQuotaConsumed`
- `CustomerLastPurchaseUpdated`

---

## 11. Workflow I - Cập nhật preference và hành vi khách hàng

### Bài toán
Sau mỗi lần mua hoặc tương tác, hệ phải học dần:
- khách thích gì
- khách có nhịp mua ra sao
- khách hợp sản phẩm nào

### Actor
- CSKH
- Sales
- System analytics
- AI assistant ở mức suggest

### Input
- purchase history
- feedback
- tag
- ghi chú CSKH
- channel behavior

### Rule chính
- preference là dữ liệu hỗ trợ CRM, không phải dữ liệu kế toán
- AI có thể đề xuất preference
- nhưng nếu preference ảnh hưởng workflow quan trọng thì phải có người hoặc rule xác nhận
- lịch sử thay đổi preference nên giữ dạng timeline
- candidate từ CRM hoặc AI không tự thành canonical preference
- chỉ role được phép theo `07-permission-matrix.md` mới được xác nhận candidate thành preference dùng cho workflow

### Output
- customer profile cập nhật
- segment tags
- preference timeline

### Event tối thiểu
- `CustomerPreferenceUpdated`
- `CustomerSegmentChanged`
- `CustomerLastPurchaseUpdated`

### Policy hook
- guard xác nhận preference xem ở `06-state-transitions.md`
- quyền xác nhận preference xem ở `07-permission-matrix.md`

---

## 12. Thứ tự triển khai hợp lý

### Sprint chứng minh giá trị đầu tiên
1. Customer
2. Preorder
3. Order
4. Lot
5. Release
6. Allocation
7. Packing / Delivery
8. Customer history update

### Sprint tiếp theo
1. Plot
2. Crop cycle
3. Tích hợp LiteFarm / ERP / CRM
4. Read models theo role
5. Alert / reminder cơ bản

## 13. Quy tắc build

- không build full engine trước
- không generic hóa trước khi có lặp đủ nhiều
- mỗi workflow phải đi xuyên hết một lát cắt thật
- cái gì AI chưa nên làm thì đừng “mở sẵn để sau”
- nếu cần đơn giản hóa, đơn giản ở UI và automation trước, không đơn giản hóa source of truth
