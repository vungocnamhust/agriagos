Vì lớp deterministic của cậu không nên ghi log theo kiểu “có gì ghi nấy”, mà phải ghi **những sự kiện mốc** làm thay đổi trạng thái của chuỗi giá trị. Những event này được chọn vì chúng là các điểm chuyển pha quan trọng giữa **khách hàng → nhu cầu → sản xuất → lô hàng → đơn hàng → giao hàng → học lại từ khách**. Nó bám đúng nguyên tắc của hệ cậu: có **canonical data model**, mọi phần chỉ đọc/ghi qua **event bus + schema chuẩn**, và dùng event để nối sản xuất, truy xuất, đơn hàng, CRM thành một luồng chung.  

Nói dễ hiểu:
các event này không phải để “lưu lịch sử cho vui”.
Chúng được chọn vì mỗi event trả lời một câu hỏi vận hành rất cụ thể.

---

## 1) Vì sao phải chọn đúng “event mốc” thay vì log tất cả mọi thứ?

Một event tốt thường có 5 đặc điểm:

**Một là:** nó đánh dấu một thay đổi trạng thái thật sự.
**Hai là:** nó có ý nghĩa nghiệp vụ rõ.
**Ba là:** nhiều module khác cần biết nó xảy ra.
**Bốn là:** nó đáng được audit và phân tích về sau.
**Năm là:** sau này agent, workflow, dashboard đều có thể dựa vào nó.

Ví dụ:

* “user mở màn hình order 3 lần” là log kỹ thuật, chưa chắc là domain event
* “OrderPacked” là domain event thật, vì từ đó kho, CSKH, giao hàng, traceability đều bị ảnh hưởng

---

# 2) Giải thích từng event

## `CustomerCreated`

### Vì sao cần?

Vì đây là thời điểm **một người trở thành một thực thể chính thức trong hệ**.

Nếu không có event này, cậu sẽ không biết:

* khách đó vào hệ từ lúc nào
* họ đến từ kênh nào
* những event sau gắn vào customer nào
* khách cũ và khách mới được phân biệt ra sao

### Nó mở ra những gì?

* tạo hồ sơ khách trong CRM
* nối identity giữa CRM, ERP, chat channel
* bắt đầu tính lifecycle
* cho phép sau này attach order, preorder, preference vào đúng khách

### Tại sao không chỉ cần row trong bảng khách hàng?

Vì row chỉ cho biết **trạng thái hiện tại**.
Còn event cho biết **thời điểm bắt đầu quan hệ**.

---

## `PreorderPlaced`

### Vì sao cần?

Vì với hệ của cậu, **đơn đặt trước không chỉ là một order bình thường**.
Nó là tín hiệu kéo ngược về sản xuất.

Trong mô hình của cậu, đặt trước gạo, sản phẩm theo mùa, hoặc pre-order từ khách là thứ nối trực tiếp thị trường với mùa vụ. CRM khách hàng và đặt trước được xác định là mảng phải số hóa rất sớm vì ai nắm khách và đặt trước thì người đó nắm quyền lực chuỗi. 

### Nó mở ra những gì?

* dự báo nhu cầu
* gắn đơn tương lai với crop cycle/lot tương lai
* biết khách nào cam kết mua sớm
* tính % sản lượng đã được “khóa đầu ra”
* trigger nhắc lịch giao / chăm khách / chuẩn bị hàng

### Tại sao không gộp luôn vào `OrderPlaced`?

Vì preorder và order thường có logic khác:

* preorder có thể chưa có hàng ngay
* preorder có thể kéo dài nhiều tuần/tháng
* preorder ảnh hưởng kế hoạch sản xuất
* preorder cần theo dõi commitment riêng

Nói ngắn:
`PreorderPlaced` là **event của nhu cầu tương lai**,
còn `OrderPlaced` thường là **event của giao dịch hiện tại**.

---

## `HarvestedLotCreated`

### Vì sao cần?

Vì đây là lúc nông sản đi từ “đang ở ngoài ruộng” thành “một lô hàng cụ thể có thể quản lý được”.

Nếu không có event này:

* không biết lô nào thực sự đã thu hoạch
* không có điểm bắt đầu cho traceability
* không có gì để QC review
* không có gì để order allocation bám vào

### Nó mở ra những gì?

* tạo mã lot
* gắn lot với crop cycle / plot / farmer
* bắt đầu hồ sơ truy xuất
* tạo nơi để attach evidence
* đưa lô vào hàng chờ QC

### Vì sao đây là event mốc?

Vì đây là lúc thực thể quản trị đổi loại:

* trước đó cậu quản vụ/cây/ruộng
* sau đó cậu quản **lô**

Nó là cây cầu từ sản xuất sang vận hành thương mại.

---

## `LotReleased`

### Vì sao cần?

Vì đây là thời điểm lô **được phép bước vào phần thương mại**.

Trước đó lot có thể:

* mới tạo
* đang thiếu chứng cứ
* đang chờ QC
* bị block

Chỉ khi có `LotReleased`, hệ mới được hiểu là:

> “lô này đủ điều kiện đi tiếp”

Trong logic deterministic của cậu, đơn hàng, kho, allocation đều phải đi qua guard như “lot chưa release thì không được allocate”. Tức là QC/truy xuất là phần phải làm “cứng”. 

### Nó mở ra những gì?

* hàng khả dụng để bán
* cho phép allocate vào order
* hiển thị ở traceability/public-safe view
* làm mốc SLA từ harvest đến release
* phân biệt hàng có thể bán và hàng chỉ đang tồn trên danh nghĩa

### Tại sao không chỉ dùng `LotPassedQC`?

Vì nhiều khi:

* QC pass xong vẫn cần bước release riêng
* release có thể bị chặn bởi policy khác
* có nơi QC review và approval vận hành là 2 bước khác nhau

Nên `LotReleased` là event **thương mại hóa lô**, không chỉ là event **kỹ thuật QC**.

---

## `OrderAllocated`

### Vì sao cần?

Vì đây là lúc hệ xác định:

> “đơn này sẽ được phục vụ bằng lô nào, số lượng nào”

Nó quan trọng vì lúc này mới bắt đầu có ràng buộc thật giữa:

* khách hàng
* order
* inventory
* lot traceability

### Nó mở ra những gì?

* reserve tồn khả dụng
* ngăn double-sell
* biết khách A đang chờ lô nào
* tạo đường traceability từ order ngược về lot
* sales/ops biết order này đã có hàng thật chưa

### Tại sao không chỉ cần `OrderConfirmed`?

Vì `OrderConfirmed` mới chỉ nói:

* “đơn hợp lệ”
  còn `OrderAllocated` mới nói:
* “đã chỉ định hàng cụ thể để phục vụ đơn này”

Đây là mốc rất quan trọng trong chuỗi có lot/batch.

---

## `OrderPartiallyAllocated`

### Vì sao cần?

Vì không phải lúc nào order cũng được reserve đủ hàng trong một lần allocate.

Nếu không có event này, hệ chỉ nhìn thấy hai trạng thái cực đoan:

* chưa allocate gì
* hoặc đã allocate đủ

trong khi thực tế ops thường phải đi qua một pha trung gian: đã giữ được một phần hàng, nhưng chưa đủ để coi là fully allocated.

### Nó mở ra những gì?

* cho phép order quay về một trạng thái trung gian có ý nghĩa vận hành
* giúp UI/ops biết đơn nào còn thiếu hàng thật
* làm mốc để tiếp tục allocate bổ sung thay vì pack nhầm

---

## `AllocationAdjusted`

### Vì sao cần?

Vì allocation không phải lúc nào cũng cố định sau lần reserve đầu tiên.

Có lúc khách giảm số lượng, ops phải hạ reserve, hoặc cần đổi cách chia hàng giữa các line/order mà vẫn giữ audit trail rõ ràng.

### Nó mở ra những gì?

* ghi lại old/new quantity của reservation thay vì sửa âm thầm
* trả hoặc giữ thêm `available_qty` đúng theo phần delta
* cập nhật lại quota preorder đang bị giữ

Trong phase 1 runtime, đây là event đi ra từ public command `POST /api/v1/orders/{order_id}/allocations/{allocation_id}/adjust`.

---

## `AllocationReleased`

### Vì sao cần?

Vì có những lúc cần bỏ reservation hoàn toàn mà order chưa bị hủy toàn bộ.

Nếu không có event này, hệ sẽ không phân biệt được:

* release reservation có chủ đích
* với một thay đổi trạng thái chung chung trên order

### Nó mở ra những gì?

* trả quantity về `available_qty` của lot qua `release_reservation`
* đưa allocation về trạng thái `released`
* có thể đưa order quay về `confirmed` nếu không còn active allocation nào

Trong phase 1 runtime, đây là event đi ra từ public command `POST /api/v1/orders/{order_id}/allocations/{allocation_id}/release` và cũng được tái dùng khi cancel flow giải phóng reservation.

---

## `OrderPacked`

### Vì sao cần?

Vì đây là lúc hàng **thật sự được gom và đóng gói** để chuẩn bị rời kho.

Đây là một mốc vận hành chứ không chỉ trạng thái đẹp.

### Nó mở ra những gì?

* tạo packing queue / packed queue
* đánh dấu order đã đi qua bước đóng gói
* thay đổi policy hủy đơn
* trigger giao vận
* đo lead time từ allocate đến pack

### Tại sao phải log event riêng?

Vì packed là điểm mà nhiều rule đổi hẳn:

* cancel có thể không còn auto nữa
* sai sót ở đây tạo chi phí thật
* khách đã gần được giao
* kho và CSKH đều cần biết

`OrderPacked` là event cho **sự thật vận hành**, không chỉ để update UI.

---

## `OrderDelivered`

### Vì sao cần?

Vì đây là lúc vòng đời logistics của đơn **thực sự khép lại**.

Nếu chỉ có `OrderShipped`, cậu chưa biết:

* khách đã nhận chưa
* có thể ghi nhận doanh thu/hoàn tất fulfillment chưa
* có nên mở flow chăm sau mua chưa
* có nên tính repeat window chưa

### Nó mở ra những gì?

* trigger after-sales
* bắt đầu đếm thời gian mua lại
* gửi hướng dẫn dùng / feedback / chăm sóc
* tính conversion từ shipped sang delivered
* gắn phản hồi chất lượng với đúng đơn đã nhận

### Tại sao là event mốc?

Vì từ góc nhìn khách hàng, đây mới là lúc “lời hứa giao hàng” hoàn thành.

---

## `CustomerPreferenceUpdated`

### Vì sao cần?

Vì hệ của cậu không chỉ bán hàng, mà còn phải **học dần về khách**.

Ví dụ:

* khách thích gạo mềm hơn
* khách muốn giao theo tháng
* khách thích dòng wellness
* khách chỉ mua quà vào dịp lễ
* khách hợp retreat hơn mua hàng thường

Những thứ này không phải transaction, nhưng lại cực quan trọng cho CRM và agent layer sau này. Trong các mô tả trước, việc biết khách nào mua gì, thích gì, hợp dòng sản phẩm/trải nghiệm nào là một phần rất đáng số hóa sớm. 

### Nó mở ra những gì?

* phân khúc khách
* cá nhân hóa CSKH
* gợi ý sản phẩm tốt hơn
* workflow riêng theo role sau này
* “học từ thị trường” quay ngược lại hệ

### Tại sao không chỉ update một cột trong CRM?

Vì preference không phải chỉ là “giá trị hiện tại”, mà là:

* đã thay đổi khi nào
* vì event nào
* sau tương tác nào
* ai/cái gì đã cập nhật nó

Nên event này là một phần của “học liên tục từ khách”.

---

# 3) Nhìn cả chuỗi thì bộ event này đang làm gì?

Nếu xếp theo chuỗi logic, chúng tạo thành một vòng khá đẹp:

```text id="v2fhuc"
CustomerCreated
   -> PreorderPlaced
   -> HarvestedLotCreated
   -> LotReleased
   -> OrderAllocated
  -> OrderPartiallyAllocated / AllocationAdjusted / AllocationReleased (nếu cần re-balance reservation)
   -> OrderPacked
   -> OrderDelivered
   -> CustomerPreferenceUpdated
```

Ý nghĩa:

* **bắt đầu từ khách**
* kéo ngược về **nhu cầu**
* chuyển sang **sản xuất thành lô**
* đưa lô qua **cổng chất lượng**
* nối lô vào **đơn cụ thể**
* đi qua **fulfillment**
* quay lại **học từ khách**

Đây là lý do tớ nói bộ event này không phải các event rời rạc.
Nó là **xương sống của một feedback loop**.

---

# 4) Vì sao bộ event này phù hợp với giai đoạn hiện tại?

Vì nó bám rất sát vào các đầu mục thực tế mà cậu đang cần:

* quản lý khách hàng
* quản lý đơn hàng và đơn đặt trước
* phân tích hành vi khách hàng cơ bản
* quản lý kho
* quản lý đồng ruộng cơ bản
* phân quyền nhìn thấy dữ liệu

Nó chưa ôm quá rộng, nhưng đủ để tạo ra:

* customer truth
* demand truth
* lot truth
* sellable truth
* fulfillment truth
* learning truth

Tức là **đủ nhỏ để chạy**, nhưng **đúng hướng để mở rộng**.

---

# 5) Bộ event này có phải là tất cả chưa?

Chưa. Đây là **bộ xương sống đầu tiên**, không phải toàn bộ event catalog.

Sau này sẽ cần thêm các event như:

* `CropCyclePlanned`
* `CropTaskCompleted`
* `LotEvidenceAttached`
* `LotBlocked`
* `OrderCancelRequested`
* `InventoryAdjusted`
* `CustomerSegmentChanged`

Nhưng ở giai đoạn đầu, bộ 8 event cậu nêu ra là hợp lý vì nó chạm đúng các điểm chuyển pha lớn nhất của hệ.

---

# 6) Câu chốt

Cậu chia thành các event này vì mỗi event là một **mốc chuyển trạng thái quan trọng của chuỗi giá trị**, và mỗi mốc đó:

* có ý nghĩa nghiệp vụ rõ
* nhiều module khác cần biết
* đáng audit
* dùng được cho dashboard, workflow, policy và agent sau này

Nói ngắn nhất:

**Các event này không được chọn theo “database nghĩ ra gì thì ghi nấy”, mà được chọn theo “chuỗi giá trị của doanh nghiệp chuyển pha ở đâu”.**

Nếu cậu muốn, tin nhắn tiếp theo tớ sẽ làm tiếp cho cậu một bảng rất rõ kiểu:

**Event | Ai phát ra | Module nào dùng | Dashboard nào cần | Agent nào sẽ dùng sau này**
