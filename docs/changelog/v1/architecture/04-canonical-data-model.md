# 04. Canonical Data Model

## 1. Mục tiêu

Tài liệu này chốt mô hình dữ liệu chuẩn cho **Agri OS Core**.

Nguyên tắc:
- không phải mọi dữ liệu đều nằm trong cùng một hệ
- nhưng phải có **canonical model** để mọi hệ hiểu nhau
- mỗi loại dữ liệu cần có `source of truth` rõ
- read model và write model là hai chuyện khác nhau

ERD chi tiết xem ở:
- [Canonical Data Model / ERD](../agri_diagrams/03-canonical-data-model-erd.md)

## 2. Cách đọc tài liệu này

Phần này không cố mô tả “mọi bảng có thể tồn tại trong tương lai”.  
Nó chỉ chốt:
- entity lõi phase đầu
- field tối thiểu cần có
- source of truth của từng entity
- quan hệ logic giữa các entity
- chỗ nào là phase đầu, chỗ nào để sau

### 2.1 Mapping tên tài liệu với tên implementation
Để tránh drift giữa docs tiếng Việt và code:

| Tên trong tài liệu này | Tên implementation / canonical alias |
|---|---|
| Customer | `CustomerProfile` |
| Customer Preference | `CustomerPreference` |
| Preorder | `Preorder` |
| Order | `SalesOrder` |
| Order Line | `SalesOrderLine` |
| Product SKU | `ProductSKU` |
| Plot | `Plot` |
| Crop Cycle | `CropCycle` |
| Lot | `LotBatch` |
| Allocation | `Allocation` |
| Inventory Movement | `InventoryMovement` |
| Payment Record | `PaymentRecord` |
| Delivery Record | `DeliveryRecord` |
| External Mapping | `ExternalMapping` |
| Event Log | `DomainEvent` |

Rule đọc tài liệu:
- tên tiếng Việt giúp team nghiệp vụ đọc nhanh
- tên implementation là tên nên ưu tiên khi viết model, DTO, schema, table alias, và code comments

---

## 3. Quy tắc chung

### 3.1 Một loại dữ liệu chỉ nên có một source of truth chính
Ví dụ:
- canonical customer identity: Agri OS Core
- preorder / order / lot / allocation: Agri OS Core
- accounting final: ERP
- field ops sâu: LiteFarm
- conversation history: CRM

### 3.2 Machine ID và business code nên tách nhau
- `id`: dùng trong DB và code
- `code`: dùng cho con người đọc và đối soát

### 3.3 Event log không thay thế canonical tables
Event log giữ lịch sử.  
Canonical tables giữ trạng thái hiện tại.

### 3.4 Read models không phải sự thật gốc
Read models chỉ là góc nhìn phục vụ từng role.

### 3.5 Source-of-truth phải chốt theo domain, không theo màn hình
Một domain có thể xuất hiện ở nhiều hệ và nhiều dashboard, nhưng chỉ một nơi được quyền giữ truth gốc cho write path.

---

## 3A. Domain ownership baseline

| Domain | Canonical owner | Core phải giữ gì | Hệ ngoài chỉ giữ gì |
|---|---|---|---|
| Customer identity | Agri OS Core | customer profile, customer code, external mappings | CRM/ERP chỉ giữ mapped record theo nhu cầu riêng |
| Customer preference confirmed | Agri OS Core | confirmed preference và operational segment dùng cho workflow | CRM và AI chỉ cung cấp candidate/input |
| Preorder | Agri OS Core | commitment, quota balance, trạng thái preorder | ERP/CRM chỉ nhận summary nếu cần |
| Order vận hành | Agri OS Core | order, order lines, link tới preorder, operational payment state | ERP nhận sync phục vụ chứng từ/accounting |
| Lot / Allocation | Agri OS Core | lot truth, release state, allocations, available/reserved/released quantities | ERP chỉ nhận record phục vụ reconcile phase sau |
| Inventory movement vận hành | Agri OS Core | movement audit để giải thích quantity hiện tại | ERP giữ stock/accounting final nếu phase đủ chín |
| Plot / Crop summary | Agri OS Core hoặc LiteFarm snapshot theo tenant | plot ref, crop cycle summary, expected harvest summary cần cho thương mại | LiteFarm giữ field ops sâu và task execution |
| Accounting final | ERP | Core chỉ giữ operational payment status và sync refs | ERP giữ invoice, journal, tax, settled accounting truth |
| Conversations / campaign activity | CRM | Core chỉ giữ summary cần cho workflow và mapping về customer canonical | CRM giữ threads, activities, campaigns |

### Rule baseline
- Core không được tạo source of truth thứ hai cho `accounting final` hoặc `conversations`.
- ERP, LiteFarm, CRM không được tạo source of truth thứ hai cho `preorder`, `order vận hành`, `lot`, `allocation`.
- Nếu `plot/crop` do LiteFarm giữ sâu, tenant đó vẫn phải chốt rõ snapshot tối thiểu nào đi vào Core.

### `Tenant` trong tài liệu này nghĩa là gì
`Tenant` ở đây là một môi trường vận hành hoặc một đơn vị triển khai có quyết định tích hợp riêng với hệ ngoài.

Ví dụ:
- tenant A dùng LiteFarm như nguồn sâu cho farm data
- tenant B chưa dùng LiteFarm và giữ plot/crop summary trực tiếp trong Core

Phase đầu nên coi mặc định là:
- **Core giữ plot/crop summary đủ dùng**
- LiteFarm chỉ trở thành nguồn sâu khi team đã chốt snapshot contract cho tenant đó

---

## 4. Danh sách entity lõi

## 4.1 Customer
**Mục đích:** giữ canonical customer identity.

**Source of truth:** Agri OS Core  
CRM có thể giữ conversation, nhưng customer identity canonical vẫn phải map về core.

### Field tối thiểu
- `customer_id`
- `customer_code`
- `full_name`
- `phone`
- `phone_normalized`
- `status`
- `created_at`

### Field nên có
- `channel_source`
- `default_address`
- `district`
- `province`
- `tags`
- `notes`
- `last_order_at`

### Ghi chú
- phone là natural key quan trọng nhưng không nên làm primary key
- `phone_normalized` là internal canonical key dùng cho rule chống trùng cơ bản; `phone` gốc vẫn giữ cho hiển thị
- merge customer cần event và audit log riêng
- phase hiện tại đã có `customer_duplicate_candidates` để review nghi ngờ trùng; queue này không được auto-merge record canonical

---

## 4.2 Customer Preference
**Mục đích:** lưu các sở thích và xu hướng đã được xác nhận hoặc đang ở mức candidate.

**Source of truth confirmed:** Agri OS Core  
**Nguồn candidate/input:** CRM, AI, operator notes

### Field gợi ý
- `preference_id`
- `customer_id`
- `preference_type`
- `preference_value`
- `confidence_level`
- `source`
- `confirmed_by`
- `confirmed_at`
- `updated_at`

### Rule
- nếu AI gợi ý, `source = ai_suggestion`
- nếu chưa xác nhận, không được coi là truth cứng cho action nhạy cảm
- preference chỉ trở thành canonical khi đã được xác nhận theo policy của core workflow
- trusted integration chỉ được đi vào canonical preference write path khi request mang `actor_role = integration`, có `actor_id`, và có `external_ref` để audit/idempotency boundary rõ ràng
- route public `POST /api/v1/customers/{customer_id}/preferences` hiện là canonical confirm/update path; candidate ingest từ CRM/AI phải đi qua surface khác hoặc integration normalizer, không đi thẳng vào canonical route này với `ai_suggestion`

### Confirmation policy baseline
- CRM, AI, hoặc operator có thể tạo `preference candidate`
- chỉ `Sales`, `CSKH`, `Admin vận hành`, hoặc `Founder / Super Admin` mới được xác nhận candidate thành preference canonical
- integration chỉ được xác nhận trực tiếp vào canonical path nếu là trusted integration theo guard ở trên; nếu không thì vẫn chỉ là candidate/input
- action xác nhận phải để lại `confirmed_by` và audit log
- canonical route hiện không phải candidate queue API; nếu cần giữ raw `ai_suggestion` hoặc CRM candidate thì phải map qua contract khác trước khi vào Core truth
- event tối thiểu cho việc xác nhận hoặc chỉnh sửa là `CustomerPreferenceUpdated`
- permission chi tiết xem ở `07-permission-matrix.md`; event payload xem ở `05-event-catalog.md`

---

## 4.3 Preorder
**Mục đích:** lưu cam kết mua trước.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `preorder_id`
- `preorder_code`
- `customer_id`
- `product_sku_id`
- `committed_qty`
- `allocated_qty`
- `delivered_qty`
- `remaining_qty`
- `status`
- `start_date`

### Rule quan trọng
- `remaining_qty` phải tính được rõ
- mọi điều chỉnh quantity sau confirmed phải có event

### Nên có thêm
- `cadence`
- `delivery_note`
- `deposit_amount`
- `cancelled_qty`

---

## 4.4 Order
**Mục đích:** lưu yêu cầu giao hàng cụ thể.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `order_id`
- `order_code`
- `customer_id`
- `order_date`
- `channel`
- `status`
- `delivery_date_expected`
- `payment_status`

### Field nên có
- `shipping_address`
- `note`
- `created_by`
- `source_preorder_flag`

---

## 4.5 Order Line
**Mục đích:** lưu từng dòng sản phẩm của order.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `order_line_id`
- `order_id`
- `product_sku_id`
- `ordered_qty`
- `allocated_qty`
- `packed_qty`
- `delivered_qty`
- `unit`

### Ghi chú
- một line có thể link tới nhiều allocations
- line có thể gắn với preorder reference

---

## 4.6 Product SKU
**Mục đích:** đơn vị thương mại dùng để bán.

**Source of truth phase đầu:** Agri OS Core  
**Có thể chuyển ownership phase sau:** ERP, nếu ERP item master đủ chín

### Field tối thiểu
- `product_sku_id`
- `sku_code`
- `sku_name`
- `unit`
- `status`

### Field nên có
- `category`
- `pack_size`
- `default_price`
- `is_preorder_supported`

### Ghi chú
SKU là góc nhìn thương mại.  
Lot là góc nhìn vật lý.

---

## 4.7 Plot
**Mục đích:** thửa / khu / vùng trồng.

**Source of truth phase đầu mặc định:** Agri OS Core  
**Future flexibility:** LiteFarm có thể trở thành nguồn sâu theo tenant, nhưng Core vẫn phải giữ snapshot đủ dùng  
**Source sâu về field ops:** LiteFarm nếu đã đưa vào sớm

### Field tối thiểu
- `plot_id`
- `plot_code`
- `name`
- `location_text`
- `area_value`
- `area_unit`
- `status`

### Nên có
- `owner_name`
- `manager_user_id`
- `geo_lat`
- `geo_lng`

### Rule baseline
- tenant phải chốt rõ `plot` đang là canonical record ở Core hay chỉ là snapshot từ LiteFarm
- nếu chỉ là snapshot, Core vẫn phải giữ đủ reference để nối `crop cycle -> lot -> order`
- nếu chưa có quyết định riêng theo tenant thì mặc định build `plot summary` trực tiếp trong Core

---

## 4.8 Crop Cycle
**Mục đích:** vòng đời một vụ trên plot.

**Source of truth summary phase đầu mặc định:** Agri OS Core  
**Source sâu nếu có:** LiteFarm theo tenant đã chốt snapshot contract

### Field tối thiểu
- `crop_cycle_id`
- `plot_id`
- `crop_name`
- `start_date`
- `growth_stage`
- `status`

### Nên có
- `expected_harvest_from`
- `expected_harvest_to`
- `estimated_yield_qty`
- `actual_yield_qty`

### Rule baseline
- core chỉ giữ phần `summary đủ dùng cho thương mại và traceability`
- field task, nhật ký nông học sâu, và operator workflow ngoài đồng không thuộc canonical model phase đầu của core
- nếu tenant dùng LiteFarm làm nguồn sâu, crop cycle summary trong Core vẫn là required snapshot để nối traceability

---

## 4.9 Lot
**Mục đích:** lô vật lý có thể trace.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `lot_id`
- `lot_code`
- `product_sku_id`
- `source_type`
- `source_ref_id`
- `harvest_or_production_date`
- `actual_qty`
- `released_qty`
- `available_qty`
- `reserved_qty`
- `status`

### Source type gợi ý
- `crop_cycle`
- `processing_batch`
- `purchase_inbound`

### Rule
- `available_qty` không được là một số “muốn điền sao cũng được”
- nó phải xuất phát từ movement + policy

---

## 4.10 Allocation
**Mục đích:** gắn quantity của lot vào order line.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `allocation_id`
- `order_line_id`
- `lot_id`
- `allocated_qty`
- `status`
- `allocated_at`

### Status gợi ý
- `active`
- `released`
- `consumed`
- `cancelled`

---

## 4.11 Inventory Movement
**Mục đích:** ghi lại biến động tồn kho có thể audit.

**Source of truth operational:** Agri OS Core  
**Accounting / stock final nếu phase chín:** ERP

### Vì sao phải có entity này
Nếu chỉ có `lot.available_qty`, hệ rất dễ bị:
- sửa tay
- khó audit
- khó đối soát với ERP
- khó hiểu vì sao available lại ra con số hiện tại

### Rule baseline
- `inventory movement` là operational truth của core để giải thích số lượng hiện tại
- `accounting stock final` nếu có ở phase sau vẫn thuộc ERP, không thay thế movement audit của core

### Field tối thiểu
- `inventory_movement_id`
- `movement_type`
- `lot_id`
- `related_object_type`
- `related_object_id`
- `qty`
- `unit`
- `occurred_at`
- `created_by`
- `reason_code`

### Movement type gợi ý
- `release`
- `reserve`
- `reserve_release`
- `consume`
- `adjust`
- `discard`
- `return`

---

## 4.12 Payment Record
**Mục đích:** giữ payment status phục vụ vận hành.

**Source of truth operational:** Agri OS Core  
**Accounting final:** ERP

### Field tối thiểu
- `payment_record_id`
- `order_id`
- `payment_status`
- `payment_method`
- `amount_expected`
- `amount_received`
- `received_at`

### Ghi chú
Core không cần làm full accounting ngay.  
Nhưng phải giữ đủ để sales / CSKH / ops làm việc.

---

## 4.13 Delivery Record
**Mục đích:** giữ trạng thái giao hàng.

**Source of truth operational:** Agri OS Core  
**Có thể nhận sync từ logistics:** phase sau

### Field tối thiểu
- `delivery_record_id`
- `order_id`
- `delivery_status`
- `carrier`
- `tracking_ref`
- `shipped_at`
- `delivered_at`

### Nên có
- `failed_at`
- `failure_reason`
- `delivery_note`
- `confirmed_by`

### Rule baseline
- logistics phase đầu có thể chỉ là nguồn cập nhật bán thủ công
- trạng thái `delivered` trong core chỉ được coi là operational truth sau khi đi qua policy xác nhận của core
- logistics carrier update không được overwrite âm thầm nếu policy giao hàng của core chưa xác nhận xong

---

## 4.14 External Mapping
**Mục đích:** map object giữa Agri OS Core và các hệ ngoài.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `external_system`
- `external_object_type`
- `external_object_id`
- `internal_object_type`
- `internal_object_id`
- `sync_status`
- `last_synced_at`

### Hệ nào sẽ dùng
- ERP
- LiteFarm
- CRM
- logistics / payment về sau

### Ghi chú
Đây là bảng rất quan trọng để tránh hardcode mapping khắp codebase.

---

## 4.15 Event Log
**Mục đích:** giữ lịch sử nghiệp vụ.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `event_id`
- `event_name`
- `aggregate_type`
- `aggregate_id`
- `occurred_at`
- `actor_type`
- `actor_id`
- `payload`
- `correlation_id`
- `source`

---

## 5. Quan hệ logic giữa các entity

Quan hệ chính:
- Customer → Preorder
- Customer → Order
- Customer → Customer Preference
- Product SKU → Preorder
- Product SKU → Order Line
- Product SKU → Lot
- Plot → Crop Cycle
- Crop Cycle → Lot
- Order → Order Line
- Order Line → Allocation
- Lot → Allocation
- Order → Payment Record
- Order → Delivery Record
- External Mapping → mọi aggregate khi cần tích hợp

## 6. Read models quan trọng

Phase đầu nên có:
- `customer_360_view`
- `available_lots_board`
- `pending_fulfillment_board`
- `farm_summary_board`
- `preorder_balance_view`

Current Phase 1 runtime đã kéo lane này lên sớm theo hướng SQL-views-first:
- `customer_360_view` là detail projection dạng nested JSON để match `Customer360View` trên PostgreSQL path
- `available_lots_board`, `pending_fulfillment_board`, và `farm_summary_board` đang là operational boards trực tiếp phục vụ `/api/v1/views/*`
- projection workers vẫn chưa là runtime mặc định; freshness hiện tại đến từ read trực tiếp vào SQL view và canonical tables

Phase sau có thể thêm:
- `ops_metrics_view`
- `agent_scoped_views`
- `customer_traceability_view`

## 7. Dữ liệu chưa cần quá sâu ở phase đầu

Chưa cần:
- IoT / sensor data dày
- nhật ký nông học vi mô từng giờ
- accounting bút toán kép trong core
- analytics quá nhiều tầng

Cần ngay:
- customer
- preorder
- order
- SKU
- lot
- allocation
- inventory movement
- plot
- crop cycle summary
- event log
- external mapping

## 8. Kết luận

Mô hình dữ liệu phase đầu phải đủ để:
- chạy workflow thật
- audit được
- tích hợp được
- mở đường cho read models và AI sau này

Nó không cần “đẹp như textbook”, nhưng phải:
- rõ source of truth
- rõ quan hệ
- rõ movement
- rõ đường sync với hệ ngoài
