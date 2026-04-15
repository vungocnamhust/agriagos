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
| Project / Value Stream Scope | `ProjectScope` |
| Project Assignment | `ProjectAssignment` |
| Contribution Ledger | `ProjectContributionEvent` |
| Shared Resource | `SharedResource` |
| Cost Record | `CostRecord` |
| Revenue Record | `RevenueRecord` |
| Financial Allocation | `FinancialAllocation` |
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
| Organization identity | Agri OS Core | legal-operating owner identity, organization code, organization profile tối thiểu, rollout policy cho association | integration systems chỉ giữ external mapping hoặc contract riêng theo nhu cầu của từng org |
| Project / value stream scope | Agri OS Core | project scope identity, type, status, parent-child grouping, assignment rules, contribution and financial attribution baseline | ERP/CRM/LiteFarm chỉ giữ mapping hoặc project refs nếu integration slice cần |
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
- Core giữ `Organization` như business owner aggregate mới, nhưng không được dùng nó để cướp ownership của `CustomerProfile`, `Preorder`, `SalesOrder`, `LotBatch`, `Plot`, hay `CropCycle`.
- `ProjectScope` là lớp scope dưới `Organization`, không thay `Organization` làm owner aggregate và không tự biến thành hard permission boundary trong slice đầu.
- Core không được tạo source of truth thứ hai cho `accounting final` hoặc `conversations`.
- ERP, LiteFarm, CRM không được tạo source of truth thứ hai cho `preorder`, `order vận hành`, `lot`, `allocation`.
- Nếu `plot/crop` do LiteFarm giữ sâu, tenant đó vẫn phải chốt rõ snapshot tối thiểu nào đi vào Core.
- customer identity vẫn là shared ecosystem identity; organization rollout về sau chỉ được gắn transaction, farm-side records, hoặc loyalty/affinity views mà không biến customer thành dữ liệu sở hữu riêng của từng organization.

### `Tenant` trong tài liệu này nghĩa là gì
`Tenant` ở đây là một môi trường vận hành hoặc một đơn vị triển khai có quyết định tích hợp riêng với hệ ngoài.

Ví dụ:
- tenant A dùng LiteFarm như nguồn sâu cho farm data
- tenant B chưa dùng LiteFarm và giữ plot/crop summary trực tiếp trong Core

Phase đầu nên coi mặc định là:
- **Core giữ plot/crop summary đủ dùng**
- LiteFarm chỉ trở thành nguồn sâu khi team đã chốt snapshot contract cho tenant đó

### `Organization` trong tài liệu này nghĩa là gì
`Organization` là chủ thể vận hành hoặc pháp lý mà Core cần mô hình hóa như business owner aggregate.

Trong baseline hiện tại:
- `Organization` **không** đồng nghĩa với `Tenant`
- `Organization` là legal-operating owner của farm-side hoặc commercial-side records khi rollout đã đến slice tương ứng
- customer vẫn là shared identity của toàn hệ sinh thái, không trở thành owned aggregate của từng organization
- brand/business-facing identity được giữ trong profile của `Organization`; chưa tách thành aggregate riêng

### Rollout order cho `organization_id`
Thứ tự rollout chi tiết xem ở `10-assumptions-and-migration-path.md`.

1. standalone Organization aggregate
2. farm-side records: `Plot`, `CropCycle`, `LotBatch`
3. commercial-side records: `Preorder`, `SalesOrder`
4. nếu cần, customer-organization affinity chỉ đi qua read model hoặc relationship view được duyệt riêng; không thêm canonical ownership edge trong baseline này

---

## 4. Danh sách entity lõi

## 4.0 Organization
**Mục đích:** giữ identity của legal-operating owner trong hệ sinh thái Agri OS.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `organization_id`
- `organization_code`
- `name`
- `organization_type`
- `status`
- `region`
- `locality_summary`
- `representative_name`
- `contact_phone`
- `contact_email`
- `short_description`
- `created_at`
- `updated_at`

### Rule baseline
- aggregate này mô hình hóa chủ thể vận hành/pháp lý như hộ sản xuất, gia đình có thương hiệu riêng, solo founder, HTX, hoặc chủ thể tương đương
- aggregate này không thay `tenant_id`
- phase rollout đầu chỉ cần aggregate standalone; association sang farm-side và commercial-side là slice tiếp theo
- brand/business-facing identity ở trong profile của `Organization`, không phải aggregate riêng trong baseline hiện tại

## 4.0A Project / Value Stream Scope
**Mục đích:** giữ lớp scope mềm để gom và theo dõi một dòng giá trị, initiative, experience, hoặc grouping node dưới một `Organization`.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `project_scope_id`
- `organization_id`
- `project_scope_code`
- `name`
- `scope_type`
- `status`
- `season_year`
- `owner_actor_id`
- `description`
- `parent_project_scope_id`
- `metadata_json`

### Field nên có
- `started_at`
- `ended_at`
- `tags`
- `reporting_policy`
- `attribution_mode`

### Rule baseline
- `ProjectScope` là subordinate scope của `Organization`, không phải owner aggregate song song với `Organization`
- một `ProjectScope` có thể đại diện cho gạo mùa 2026, ngải cứu, hoa cúc, mật ong, Farm Visit, retreat, gói quà, hoặc một household livelihood stream
- không ép mọi record canonical phải mang `project_scope_id` ngay; rollout theo assignment hoặc nullable propagation từng domain slice
- `value stream` là business alias; canonical term trong model là `ProjectScope`

## 4.0B Project Assignment
**Mục đích:** gắn một record nghiệp vụ vào một hoặc nhiều `ProjectScope` mà không phá write path hiện tại.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `project_assignment_id`
- `project_scope_id`
- `target_type`
- `target_id`
- `assignment_role`
- `is_primary`
- `attribution_weight`
- `attribution_kind`
- `source`
- `confidence_level`
- `effective_at`
- `ended_at`
- `confirmed_by`
- `confirmed_at`

### Rule baseline
- cùng một target có thể thuộc nhiều `ProjectScope`
- `attribution_kind` phải tách được assignment dùng cho impact reporting với assignment đủ điều kiện financial reporting
- `unassigned` là trạng thái dữ liệu hợp lệ khi chưa có deterministic attribution

## 4.0C Project Contribution Event
**Mục đích:** ghi nhận ai đóng góp gì vào một `ProjectScope`.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `project_contribution_event_id`
- `project_scope_id`
- `organization_id`
- `actor_id`
- `subject_type`
- `subject_id`
- `contribution_type`
- `role`
- `quantity`
- `unit`
- `estimated_value`
- `currency`
- `status`
- `confirmed_by`
- `confirmed_at`
- `source`
- `metadata_json`
- `created_at`

### Rule baseline
- ledger này là append-only; không silent edit contribution đã ghi
- contribution confirmation là fact riêng cần audit
- một contribution có thể đi kèm subject như order, lot, content asset, customer source, hay shared resource allocation

## 4.0D Shared Resource
**Mục đích:** giữ canonical danh mục tài nguyên được nhiều `ProjectScope` cùng sử dụng.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `shared_resource_id`
- `organization_id`
- `resource_code`
- `name`
- `resource_type`
- `status`
- `capacity_value`
- `capacity_unit`
- `description`

### Rule baseline
- shared resource không phải lot inventory hay allocation record của bán hàng
- một shared resource cần đi kèm resource allocation hoặc cost allocation khi được nhiều scope dùng chung

## 4.0E Cost Record
**Mục đích:** giữ operational cost truth đủ dùng để tính hiệu quả theo `ProjectScope`.

**Source of truth:** Agri OS Core cho operational P&L; ERP vẫn có thể giữ accounting final

### Field tối thiểu
- `cost_record_id`
- `organization_id`
- `project_scope_id`
- `cost_type`
- `amount`
- `currency`
- `recognized_at`
- `source_object_type`
- `source_object_id`
- `attribution_policy`
- `metadata_json`

### Rule baseline
- `project_scope_id` có thể null khi cost ban đầu chưa được assign rõ
- nếu cost phục vụ nhiều scope, phải đi qua `FinancialAllocation` thay vì duplicate fact

## 4.0F Revenue Record
**Mục đích:** giữ operational revenue truth đủ dùng để tính hiệu quả theo `ProjectScope`.

**Source of truth:** Agri OS Core cho operational P&L; ERP vẫn có thể giữ invoice/journal final

### Field tối thiểu
- `revenue_record_id`
- `organization_id`
- `project_scope_id`
- `revenue_type`
- `gross_amount`
- `net_amount`
- `currency`
- `recognized_at`
- `source_object_type`
- `source_object_id`
- `customer_id`
- `metadata_json`

### Rule baseline
- revenue có thể seed từ delivered order, experience booking, package sale, hoặc campaign conversion đã confirm
- nếu revenue phục vụ nhiều scope, phải đi qua `FinancialAllocation`

## 4.0G Financial Allocation
**Mục đích:** chia một `CostRecord` hoặc `RevenueRecord` sang nhiều `ProjectScope` một cách minh bạch.

**Source of truth:** Agri OS Core

### Field tối thiểu
- `financial_allocation_id`
- `source_record_type`
- `source_record_id`
- `project_scope_id`
- `allocation_basis`
- `allocation_weight`
- `allocated_amount`
- `currency`
- `confidence_level`
- `confirmed_by`
- `confirmed_at`

### Rule baseline
- không duplicate cost hoặc revenue facts để xử lý shared attribution
- report tài chính phải chỉ dùng allocations đủ điều kiện financial
- report impact có thể đọc thêm assignments hoặc allocations observational mà không làm bẩn P&L

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
- customer không trở thành dữ liệu sở hữu riêng của một `Organization`; nếu về sau cần trả lời loyalty hoặc affinity theo tổ chức, nên dùng association/read model tương ứng thay vì đổi ownership của `CustomerProfile`

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
- `remaining_qty` là quota còn có thể allocate: `committed_qty - allocated_qty - delivered_qty - cancelled_qty`
- `committed_qty` là current commitment sau các lần adjust hợp lệ
- `cancelled_qty` phản ánh phần quota bị hủy ở action cancel, không dùng để phản ánh delta adjust
- mọi điều chỉnh quantity sau confirmed phải có event

### Nên có thêm
- `cadence`
- `delivery_note`
- `deposit_amount`
- `cancelled_qty`
- lịch sử `preorder_adjustments` dạng append-only để audit adjustment riêng với event log

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
- `carrier`
- `tracking_ref`
- `shipped_at`
- `delivered_at`
- `proof_ref`
- `failure_reason`
- `note`
- `delivery_note`
- `created_by`
- `source_preorder_flag`

### Ghi chú
- phase đầu đang snapshot fulfillment trực tiếp trên `SalesOrder` để route `/pack`, `/ship`, `/deliver`, và `/fail-delivery` trả về operational detail ngay từ aggregate chính
- `failure_reason` là snapshot phục vụ audit/tra cứu lane giao hàng thất bại; không làm thay đổi rule chỉ consume preorder khi quantity thật sự delivered

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
