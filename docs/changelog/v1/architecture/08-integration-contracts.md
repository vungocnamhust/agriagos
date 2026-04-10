# 08. Integration Contracts

## 1. Mục tiêu

Hệ thống này sẽ không tự code mọi thứ.  
Nó cần cắm với:
- ERP
- Farm management
- CRM / omnichannel
- logistics / payment về sau

Tài liệu này chốt:
- hệ nào giữ source of truth cho loại dữ liệu nào
- đồng bộ theo hướng nào
- sync bằng API, event hay batch
- conflict xử lý ra sao
- mapping và idempotency phải giữ thế nào

Integration flow tổng thể xem ở:
- [Integration Flow: LiteFarm / ERP / CRM ↔ Core](../agri_diagrams/07-integration-flow-litefarm-erp-crm-core.md)

## 2. Nguyên tắc tích hợp

1. **Không để 3 hệ cùng là source of truth cho một dữ liệu**
2. **Agri OS Core giữ orchestration truth và event log**
3. **ERP giữ accounting final**
4. **LiteFarm giữ field ops / nông học sâu nếu cần**
5. **CRM giữ conversation và lifecycle interactions**
6. Sync phải:
   - deterministic
   - idempotent
   - observable
   - có retry / reconciliation

---

## 3. Phân vai hệ thống theo domain

| Domain | Source of truth chính | Ghi chú |
|---|---|---|
| Canonical customer identity | Agri OS Core | CRM giữ conversation, không giữ truth giao dịch cuối |
| Customer conversations / outreach | CRM | Core chỉ giữ summary cần cho workflow |
| Preorder | Agri OS Core | Không đẩy logic preorder sang ERP phase đầu |
| Order vận hành | Agri OS Core | ERP nhận sync để đi tới chứng từ / accounting |
| Lot / allocation / inventory movement vận hành | Agri OS Core | ERP có thể nhận snapshot / chứng từ phase sau |
| Plot / crop cycle summary | Agri OS Core hoặc LiteFarm snapshot | Phase đầu linh hoạt, nhưng phải chốt rõ từng tenant |
| Nông học sâu / field tasks | LiteFarm | Core chỉ giữ phần cần điều phối thương mại |
| Accounting / invoice / journal final | ERP | Không tranh source of truth với ERP |
| Event log orchestration | Agri OS Core | Đây là vai trò riêng của core |

## 3.1 Boundary baseline phải chốt trước implementation sâu

| Boundary | Quyết định baseline |
|---|---|
| Core vs ERP | Core giữ `preorder`, `order vận hành`, `lot/allocation`, `operational payment status`; ERP giữ `invoice`, `journal`, `tax`, `accounting final` |
| Core vs LiteFarm | Core giữ `plot/crop summary` đủ dùng cho thương mại; LiteFarm giữ `field ops sâu`, `field tasks`, `farm nhật ký sâu` |
| Core vs CRM | Core giữ `canonical customer identity`, `purchase truth`, `confirmed preference`; CRM giữ `conversation threads`, `campaign`, `activity timeline` |

### Rule baseline
- Nếu boundary chưa chốt, không được để hai hệ cùng mutate cùng một domain.
- Nếu một tenant chọn LiteFarm là nguồn sâu cho `plot/crop`, tenant đó phải chốt snapshot contract trước khi build sync.
- Nếu CRM gửi `preference_candidate`, candidate đó không được trở thành truth confirmed nếu chưa đi qua policy của Core.
- Nếu ERP trả về accounting state mâu thuẫn với Core operational payment state, conflict phải được gắn cờ reconcile chứ không overwrite âm thầm.

### `Tenant` nghĩa là gì trong integration baseline
`Tenant` là một đơn vị triển khai hoặc môi trường vận hành có lựa chọn tích hợp riêng.

Ví dụ:
- tenant chưa dùng LiteFarm: Core giữ trực tiếp `plot/crop summary`
- tenant đã dùng LiteFarm: Core giữ `snapshot đủ dùng`, LiteFarm giữ dữ liệu sâu

### Snapshot contract tối thiểu khi LiteFarm là nguồn sâu
Core tối thiểu phải nhận được:
- `plot_id` hoặc external mapping để map plot
- `crop_cycle_id` hoặc external mapping để map crop cycle
- `crop_name`
- `growth_stage`
- `expected_harvest_from`
- `expected_harvest_to`
- `status`

Nếu chưa chốt được contract tối thiểu này thì chưa nên build sync plot/crop sâu.

---

## 4. Chốt dứt khoát về Customer

Đây là chỗ rất dễ loạn nếu nói nửa nạc nửa mỡ.

### Quy ước nên dùng
- **Agri OS Core** = source of truth cho `canonical customer identity` dùng cho preorder/order/purchase history
- **CRM** = source of truth cho conversation, activity, campaign response, lifecycle touchpoints
- **ERP** = giữ customer record phục vụ chứng từ / accounting sync

Nói dễ hiểu:
- khách là ai trong chuỗi giao dịch → Core
- khách đã nói chuyện gì, trên kênh nào → CRM
- khách lên hóa đơn thế nào → ERP

---

## 5. Integration A - ERP

### ERP nên giữ
- accounting final
- invoice / journal / tax-related records
- item master khi phase đủ chín
- stock/accounting records nếu sau này đồng bộ sâu

### Core cần gửi sang ERP
- customer tối thiểu
- order summary hoặc sales order sync
- delivery summary
- payment reference / status cần cho accounting

### ERP trả về cho Core
- invoice reference
- invoice paid / accounting settled
- item master changes nếu ERP được chọn làm owner phase sau

### Contract gợi ý

#### Outbound Core → ERP
- `customer_sync`
- `sales_order_sync`
- `delivery_sync`
- `payment_reference_sync`

#### Inbound ERP → Core
- `invoice_created`
- `invoice_paid`
- `accounting_status_updated`

### Rule
- preorder logic ở core
- allocation lot ở core
- ERP không nên quyết định lot nào cấp cho order phase đầu
- payment state ở core chỉ là `operational truth`; ERP mới là `accounting final truth`

### Conflict: operational quantity ở Core vs accounting stock ở ERP
- quyết định fulfillment và allocation vẫn dùng `available_qty` của Core làm nguồn vận hành chính
- nếu ERP trả về stock/accounting state lệch với Core, hệ phải gắn cờ `needs_reconciliation`
- phase đầu cho phép reconcile thủ công giữa Ops và Finance thay vì auto-overwrite
- phase sau mới cân nhắc job đối soát định kỳ và rule auto-adjust nếu policy đủ chín

---

## 6. Integration B - LiteFarm

### LiteFarm nên giữ
- field tasks
- farm nhật ký sâu
- crop detail sâu
- operator workflow ngoài đồng

### Core giữ
- plot canonical ref
- crop cycle summary
- expected harvest summary
- harvested lot
- link từ crop cycle → lot → order

### Contract gợi ý

#### Inbound LiteFarm → Core
- `plot_created_or_synced`
- `crop_cycle_started`
- `growth_stage_updated`
- `expected_harvest_updated`
- `harvest_reported`

#### Outbound Core → LiteFarm
- phase đầu có thể rất ít
- chỉ push reference hoặc tags nếu cần

### Rule
- nếu LiteFarm là source sâu của plot/crop, Core chỉ giữ snapshot tối thiểu
- nhưng harvested lot khi đi vào chuỗi thương mại phải được canonicalize ở Core
- baseline phải ghi rõ với từng tenant snapshot tối thiểu gồm những field nào để nối từ farm sang lot/order

---

## 7. Integration C - CRM / Omnichannel

### CRM nên giữ
- conversation threads
- inbox / follow-up
- lead management
- activity timeline
- campaign / segmentation mềm

### Core giữ
- canonical customer identity
- preorder / order / purchase truth
- confirmed preference
- operational segments thật sự dùng cho workflow

### Contract gợi ý

#### CRM → Core
- `lead_converted_to_customer`
- `conversation_summary`
- `preference_candidate`
- `channel_tags`

#### Core → CRM
- `order_summary`
- `preorder_summary`
- `delivery_status_summary`
- `customer_segment_summary`

### Rule
- một số điện thoại / customer code phải map rõ giữa core và CRM
- CRM không được âm thầm tạo “customer truth” riêng lệch khỏi core
- candidate preference từ CRM hoặc AI không tự thành preference confirmed
- core chỉ nhận `conversation summary` hoặc `workflow summary` cần cho vận hành, không nhận ownership của conversation thread

---

## 8. Integration D - Logistics

### Phase đầu
Chỉ cần:
- carrier
- tracking ref
- shipped / delivered / failed update
- có thể manual trước

### Phase sau
- webhook status
- COD settlement
- carrier exception sync

### Rule
- delivered từ carrier không phải lúc nào cũng là delivered truth cuối cùng ngay
- có thể cần policy xác nhận trước khi core chuyển order sang `delivered`

---

## 9. Integration E - Payments

### Phase đầu
- ghi payment status thủ công hoặc bán tự động
- sync transaction reference nếu có

### Phase sau
- tích hợp cổng thanh toán
- auto reconcile một phần
- nối ERP sâu hơn

### Rule
- transaction external không tự động đồng nghĩa accounting final
- vẫn cần reconciliation

---

## 10. Đồng bộ dữ liệu: realtime hay batch

### Realtime / near realtime nên dùng cho
- order created / updated
- delivery status
- customer update quan trọng
- lot release nếu ảnh hưởng fulfillment ngay

### Batch phù hợp cho
- analytics
- segment refresh
- nightly reconciliation
- non-critical sync

---

## 11. Idempotency và retry

Mọi integration command hoặc webhook nên có:
- `external_ref`
- `idempotency_key`
- `attempt_count`
- `last_error`

Nguyên tắc:
- gửi lại không tạo bản ghi trùng
- lỗi sync phải nhìn thấy được
- retry phải có giới hạn và có nơi cho người xử lý

---

## 12. Conflict resolution

### Ví dụ conflict
- customer sửa tên ở CRM và core cùng lúc
- payment status core khác ERP
- plot info LiteFarm khác core snapshot

### Rule gợi ý
- ưu tiên source of truth đã chỉ định
- hệ còn lại cập nhật theo event / sync
- conflict nghiêm trọng gắn cờ `needs_review`

### Conflict phải review bằng người
- accounting state giữa Core và ERP
- customer identity mapping lệch giữa Core và CRM
- plot/crop snapshot lệch giữa Core và LiteFarm ở tenant đã chọn LiteFarm làm nguồn sâu

---

## 13. Mapping table bắt buộc nên có

Đây là phần phase đầu rất nên làm ngay.

Field tối thiểu:
- `external_system`
- `external_object_type`
- `external_object_id`
- `internal_object_type`
- `internal_object_id`
- `sync_status`
- `last_synced_at`

Không nên hardcode mapping rải rác trong code.

---

## 14. Thứ tự tích hợp nên làm

1. Core app chạy được workflow chính trước
2. ERP sync phần tối thiểu
3. CRM sync customer / order summary
4. LiteFarm sync plot / crop summary
5. Logistics / payments nâng dần

Không nên tích hợp tất cả cùng lúc.

## 15. Kết luận

Integration tốt không phải integration “càng realtime càng hay”.  
Integration tốt là integration:
- đúng source of truth
- idempotent
- audit được
- conflict xử lý được
- không làm mờ ranh giới giữa core và hệ ngoài
