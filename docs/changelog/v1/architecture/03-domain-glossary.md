# 03. Domain Glossary

## 1. Mục tiêu

Tài liệu này giúp team dùng cùng một ngôn ngữ.

Nhiều project hỏng không phải vì code dở, mà vì:
- mỗi người hiểu cùng một từ theo một kiểu
- một từ dùng cho 2 khái niệm khác nhau
- team technical và team nghiệp vụ nói lệch nhau

## 2. Quy tắc dùng từ

- tên gọi phải bám vào **nghiệp vụ thật**
- mỗi khái niệm nên có **một nghĩa chính**
- nếu một từ dễ gây nhầm, phải ghi rõ “không nên nhầm với”
- event là quá khứ
- command là mệnh lệnh
- state là trạng thái hiện tại
- read model là góc nhìn để đọc, không phải sự thật gốc

---

## 3. Agri OS Core

**Định nghĩa:** lớp lõi deterministic mà team đang tự build.

Nó giữ:
- canonical identity
- preorder / order / lot / allocation truth
- event log / audit
- policy / workflow
- role-based views

**Không nên nhầm với:**
- ERP
- CRM
- LiteFarm
- agent orchestrator

---

## 3.1 Organization

**Định nghĩa:** chủ thể vận hành hoặc pháp lý mà Agri OS cần mô hình hóa như một legal-operating owner.

Ví dụ có thể là:
- một hộ sản xuất
- một gia đình có thương hiệu riêng
- một người khởi nghiệp
- một HTX hoặc chủ thể sở hữu tương đương

Organization dùng để trả lời các câu hỏi như:
- lô hàng hoặc vụ mùa này đang thuộc vận hành của ai
- đơn hàng này là giao dịch của tổ chức nào
- về sau integration nào đang tương tác cho tổ chức nào

**Không nên nhầm với:**
- `Tenant`: boundary triển khai hoặc tích hợp
- Customer: identity người mua dùng chung toàn hệ sinh thái
- Brand: business-facing identity; phase này chưa tách thành aggregate riêng

## 3.2 Tenant

**Định nghĩa:** một đơn vị triển khai hoặc môi trường vận hành có lựa chọn integration riêng.

Tenant giúp mô tả các quyết định như:
- tenant nào dùng FarmOS
- tenant nào giữ plot/crop summary trực tiếp trong Core
- tenant nào cần contract integration riêng

**Không nên nhầm với:**
- Organization: business owner aggregate của domain
- Customer segment
- Brand identity

## 3.3 Brand Identity

**Định nghĩa:** lớp business-facing identity mà thị trường hoặc khách hàng nhìn thấy của một organization.

Ví dụ:
- tên thương mại
- mô tả giới thiệu ngắn
- profile nhận diện mà customer nhớ tới

Phase hiện tại **không** tách brand thành aggregate riêng.
Nếu một organization chỉ có một business-facing identity đơn giản, giữ nó trong profile của `Organization` là đủ.

## 3.4 ProjectScope / Value Stream

**Định nghĩa:** lớp scope mềm dưới `Organization` dùng để gom một dòng giá trị, initiative, experience, household livelihood stream, hoặc grouping node mà team cần theo dõi riêng.

ProjectScope dùng để trả lời các câu hỏi như:
- việc này thuộc dòng giá trị nào
- dòng giá trị đó đang lời hay lỗ
- những hộ hoặc actor nào đang bị tác động
- tài nguyên nào đang được nhiều dòng giá trị dùng chung
- ai đã đóng góp vào kết quả của dòng giá trị đó

`value stream` là cách gọi nghiệp vụ gần nghĩa; `ProjectScope` là canonical term nên ưu tiên trong docs, model, schema, và API contracts khi rollout bắt đầu.

**Không nên nhầm với:**
- `Organization`: legal-operating owner của domain
- `Tenant`: boundary triển khai hoặc tích hợp
- Brand identity: lớp business-facing identity
- task list hoặc PM board: ProjectScope không phải công cụ quản lý việc cứng

## 3.5 Project Assignment

**Định nghĩa:** liên kết additive gắn một record nghiệp vụ với một hoặc nhiều `ProjectScope`.

Project assignment dùng khi:
- một lot feed nhiều dòng giá trị
- một resource dùng chung cho nhiều scope
- một order hoặc inventory movement cần được gắn vào project sau khi write path đã hoàn tất

Assignment có thể là:
- primary
- secondary
- observational
- financially eligible

## 3.6 Contribution Ledger

**Định nghĩa:** append-only ledger ghi nhận ai đã đóng góp gì vào một `ProjectScope`.

Đóng góp có thể là:
- công
- tài sản
- khách hàng hoặc lead source
- nội dung
- vốn
- vận hành
- tri thức
- quan hệ

Ledger này không thay thế event log toàn hệ; nó là canonical fact lane cho contribution của dòng giá trị.

## 3.6A Actor Identity

**Định nghĩa:** canonical hồ sơ actor dùng để nhận diện chủ thể con người, tổ chức, hộ gia đình, hay automation principal được nhắc đến trong contribution, assignment, stewardship, và authority docs.

Actor identity trả lời các câu hỏi như:
- ai là chủ thể đang được ghi nhận
- actor này là person, household, organization seat, hay automation principal
- canonical actor code nào được dùng để map affiliation và future permission grants

**Không nên nhầm với:**
- Customer: người mua trong commercial domain
- User account hay login subject: authn credential là lane khác
- delegated actor trong request meta: đó là runtime context, không phải canonical actor record

Runtime hiện đã mount lane tối thiểu cho `Actor Identity` (`POST /api/v1/actors`, `GET /api/v1/actors/{actor_id}`) và `Actor Affiliation` (`POST /api/v1/affiliations`). Draft contract tại `docs/changelog/v1/openapi/actor-authority-vnext-draft.yaml` vẫn được giữ riêng cho future expansion, đặc biệt là `PermissionGrant`.

## 3.6B Actor Affiliation

**Định nghĩa:** canonical fact ghi actor đang gắn với `Organization` hoặc `ProjectScope` nào theo kiểu affiliation nào và trong khoảng thời gian nào.

Affiliation dùng để trả lời:
- actor đang thuộc organization hoặc scope nào
- affiliation này là membership, stewardship, contractor, partner, hay observer
- affiliation còn hiệu lực hay đã kết thúc

**Không nên nhầm với:**
- permission runtime: affiliation không tự cấp quyền
- contribution role: đóng góp ở một fact cụ thể không đồng nghĩa actor có affiliation bền vững

## 3.6C Permission Grant

**Định nghĩa:** future authority contract dùng để mô hình hóa explicit runtime grants cho read, write, approve, hoặc tool-use actions.

Trong baseline hiện tại:
- permission runtime vẫn đến từ baseline roles và explicit service checks
- `PermissionGrant` mới là future lane, chưa phải canonical runtime source đang được enforce
- mọi draft contract cho lane này phải giữ rõ separation giữa context facts và authority facts

## 3.7 Shared Resource

**Định nghĩa:** tài nguyên được nhiều `ProjectScope` cùng sử dụng và cần theo dõi allocation.

Ví dụ:
- labor pool
- xe vận chuyển
- sân phơi hoặc kho chung
- marketing budget
- content asset
- host capacity cho Farm Visit hoặc retreat

Shared resource không đồng nghĩa với lot inventory. Nó là resource allocation problem, không phải stock ownership problem.

## 3.8 Cost Record

**Định nghĩa:** một canonical operational fact ghi nhận chi phí phát sinh mà Agri OS cần dùng để tính hiệu quả theo `ProjectScope`.

Cost record có thể đến từ:
- input vật tư
- công lao động
- chi phí logistics
- chi phí trải nghiệm hoặc vận hành
- phân bổ shared resource

Accounting final vẫn có thể nằm ở ERP, nhưng cost record trong Core phục vụ operational P&L theo project.

Runtime Phase 1 hiện mới mở lane đầu tiên: `CostRecord` được ghi dưới `ProjectScope` từ confirmed `ProjectContributionEvent` bằng chính sách `direct_source_link`. Các nguồn cost khác và split allocation vẫn là rollout sau.

## 3.9 Revenue Record

**Định nghĩa:** một canonical operational fact ghi nhận doanh thu hoặc giá trị thương mại được nhận diện cho `ProjectScope`.

Runtime Phase 1 hiện đã mở baseline đầu tiên: `RevenueRecord` được ghi dưới `ProjectScope` từ delivered `Order` đã có active `ProjectAssignment` vào cùng scope. Các nguồn revenue khác và split allocation vẫn là rollout sau.

Revenue record có thể seed từ:
- delivered order
- experience booking
- package sale
- campaign conversion được confirm

Revenue record không thay thế invoice hoặc journal accounting final của ERP.

## 3.10 Financial Allocation

**Định nghĩa:** fact dùng để tách một cost hoặc revenue record sang nhiều `ProjectScope` khi tác động không thuộc duy nhất một scope.

Financial allocation tồn tại để:
- tránh duplicate cost hoặc revenue facts
- cho phép shared-cost và shared-revenue attribution minh bạch
- giữ tách biệt giữa impact reporting và financially eligible attribution

---

## 4. Customer

**Định nghĩa:** người mua hoặc tổ chức mua hàng.

Customer là thực thể gốc để gắn:
- preorder
- order
- lịch sử mua
- preference
- segment

Trong baseline hiện tại, customer identity là **shared ecosystem identity**.
Điều cần trả lời về sau không phải là “customer có thuộc về organization nào không”, mà là:
- customer có giao dịch với organization nào
- customer có mức độ trung thành hay affinity với organization nào
- customer có mức độ trung thành với toàn hệ sinh thái ra sao

**Không nên nhầm với:**
- Lead: mới quan tâm nhưng chưa trở thành khách chính thức
- Contact: người liên hệ cụ thể của một tổ chức

---

## 5. Canonical Customer Identity

**Định nghĩa:** hồ sơ khách chuẩn dùng cho core workflow.

Đây là identity để:
- tạo order
- tạo preorder
- gắn purchase history
- gắn preference
- map với CRM / chat / ERP

**Lưu ý:**  
CRM có thể giữ conversation history, nhưng **canonical customer identity** phải rõ và không được mơ hồ.

---

## 6. Customer Profile

**Định nghĩa:** hồ sơ tổng hợp về khách hàng.

Bao gồm:
- thông tin nhận diện
- lịch sử mua
- source channel
- preference
- segment tags
- ghi chú CSKH

---

## 7. Preorder

**Định nghĩa:** cam kết mua trước một lượng hàng sẽ giao dần theo thời gian.

Ví dụ:
- 100kg gạo vụ tới
- giao theo tháng
- trừ dần theo thực giao

Preorder có:
- `committed_qty`
- `allocated_qty`
- `delivered_qty`
- `remaining_qty`

**Không nên nhầm với:**
- order giao ngay
- booking giữ chỗ không ràng buộc quota

---

## 8. Order

**Định nghĩa:** một yêu cầu giao hàng cụ thể.

Một order có:
- customer
- order lines
- địa chỉ giao
- payment status vận hành
- delivery status
- có thể liên kết với preorder hoặc không

---

## 9. Order Line

**Định nghĩa:** một dòng sản phẩm trong order.

Một line cần biết:
- bán SKU nào
- số lượng bao nhiêu
- lấy hàng từ lot nào
- có liên quan đến preorder nào không

---

## 10. Product SKU

**Định nghĩa:** đơn vị thương mại dùng để bán.

Ví dụ:
- Gạo mùa 5kg
- Trà hoa cúc 100g
- Mật ong 500ml

**Không nên nhầm với:**
- Lot: lô vật lý
- Crop: loại cây
- Raw material: nguyên liệu đầu vào

---

## 11. Plot

**Định nghĩa:** thửa / khu / vùng trồng có ranh giới quản lý.

Các thuộc tính phổ biến:
- code
- location
- area
- owner / operator
- manager

---

## 12. Crop Cycle

**Định nghĩa:** vòng đời một vụ cụ thể trên một plot.

Ví dụ:
- vụ lúa mùa 2026 ở Plot A
- vụ hoa cúc tháng 9 ở Plot B

Crop cycle là cầu nối giữa:
- field reality
- expected harvest
- lot creation sau này

---

## 13. Growth Stage

**Định nghĩa:** giai đoạn sinh trưởng hiện tại của crop cycle.

Phase đầu chỉ cần mức đơn giản:
- seeded
- growing
- maturing
- harvest_window
- harvested

---

## 14. Lot / Batch

**Định nghĩa:** một lô vật lý có thể truy vết được.

Lot có thể đến từ:
- thu hoạch
- sơ chế
- chế biến
- nhập mua ngoài nếu sau này cần

Một lot nên biết:
- đến từ đâu
- thuộc sản phẩm nào
- actual quantity
- released quantity
- available quantity
- trạng thái chất lượng / release

**Không nên nhầm với:**
- SKU
- inventory summary

---

## 15. Release

**Định nghĩa:** hành động cho phép một lot trở thành hàng khả dụng để allocate.

Lot có thể đã thu hoạch, nhưng chưa chắc đã được phép dùng.
`released` là mốc chuyển lot từ “đã có hàng” sang “được phép dùng cho order”.

---

## 16. Allocation

**Định nghĩa:** hành động gắn một phần quantity của lot vào order line.

Allocation trả lời 2 câu hỏi:
- đơn này lấy hàng từ lô nào?
- lô này đã được dành cho những đơn nào?

---

## 17. Inventory Movement

**Định nghĩa:** một biến động tồn kho có thể audit được.

Ví dụ:
- lot được release
- quantity bị reserve cho order
- reserve bị trả lại
- quantity bị consumed khi pack / deliver
- quantity bị adjust / discard / return

Đây là khái niệm rất quan trọng để không đồng nhất “lot” với “tồn kho”.

---

## 18. Packing

**Định nghĩa:** bước chuẩn bị hàng thực tế trước giao.

Packing không chỉ là một status đẹp trên màn hình.  
Nó là mốc xác nhận:
- đã gom hàng thật hay chưa
- quantity packed là bao nhiêu
- có thiếu so với allocate không

---

## 19. Delivery

**Định nghĩa:** bước giao hàng thực tế tới khách.

Phải phân biệt rõ:
- shipped
- delivered
- failed
- partially delivered
- returned

---

## 20. Preference

**Định nghĩa:** sở thích hoặc xu hướng mua của khách.

Ví dụ:
- thích gạo mềm
- hay mua theo tháng
- thích combo quà
- hợp dòng wellness hơn dòng quà biếu

Preference là dữ liệu CRM hỗ trợ quyết định, không phải dữ liệu kế toán.

---

## 21. Event

**Định nghĩa:** một sự kiện nghiệp vụ đã xảy ra và được ghi log có cấu trúc.

Ví dụ:
- `PreorderPlaced`
- `LotReleased`
- `OrderAllocated`

Event dùng để:
- audit
- debug
- analytics
- automation
- nuôi agent context sau này

---

## 22. Command

**Định nghĩa:** yêu cầu hệ thống thực hiện một hành động.

Ví dụ:
- `CreateOrder`
- `ReleaseLot`
- `RequestCancelOrder`

Khác với event ở chỗ:
- command = mong muốn làm gì
- event = chuyện gì đã xảy ra

---

## 23. Read Model

**Định nghĩa:** mô hình đọc tối ưu cho một vai trò hoặc màn hình.

Ví dụ:
- customer 360 cho sales
- available lots board cho ops
- farm view cho farm manager
- traceability view cho khách

Read model có thể được build từ event + canonical tables.  
Nó **không phải source of truth gốc**.

---

## 24. Source of Truth

**Định nghĩa:** nơi được coi là dữ liệu chính thức cuối cùng cho một loại thông tin.

Nguyên tắc:
- một loại dữ liệu chỉ nên có **một nguồn sự thật chính**
- hệ khác có thể giữ snapshot, cache, mirror hoặc read model

---

## 25. External Mapping

**Định nghĩa:** bảng hoặc logic map object giữa Agri OS Core và hệ ngoài.

Ví dụ:
- customer trong core ↔ contact trong CRM
- order trong core ↔ sales order trong ERP
- plot trong core ↔ field record trong LiteFarm

Không có mapping rõ thì tích hợp sẽ thành hardcode.

---

## 26. Agent

**Định nghĩa:** một lớp automation có dùng AI để đọc ngữ cảnh, gợi ý hoặc điều phối.

Agent là **actor hỗ trợ**, không phải source of truth.

Trong phase đầu, agent chỉ nên:
- đọc
- hỏi thiếu thông tin
- gợi ý
- tạo draft
- tóm tắt

---

## 27. Assumption

**Định nghĩa:** giả định tạm thời mà team chấp nhận để build nhanh.

Ví dụ:
- tạm dùng chung DB
- tạm nhập dữ liệu plot bằng tay
- tạm chưa sync realtime
- tạm để SKU do core quản phase đầu

Assumption phải được ghi ra, không để nằm trong đầu từng người.
