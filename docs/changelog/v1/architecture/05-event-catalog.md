# 05. Event Catalog

## 1. Mục tiêu

Tài liệu này chốt các event nghiệp vụ quan trọng.

Event có 4 vai trò chính:
1. audit
2. debug
3. analytics
4. automation / AI context

Nguyên tắc:
- tên event phải nói rõ **điều gì đã xảy ra**
- event là quá khứ, không phải mệnh lệnh
- event phải đủ payload để lần lại chuyện đã xảy ra
- event catalog phải khớp với state transitions

Event map tổng thể xem ở:
- [Event Storming / Event Map](../agri_diagrams/04-event-storming-event-map.md)

## 2. Cấu trúc event chuẩn

Mỗi event tối thiểu nên có:
- `event_id`
- `event_name`
- `event_type`
- `event_version`
- `aggregate_type`
- `aggregate_id`
- `occurred_at`
- `actor_type`
- `actor_id`
- `payload`
- `correlation_id`
- `causation_id`
- `idempotency_key`
- `source`

### Giải thích ngắn
- `aggregate_type`: thực thể chính bị tác động
- `aggregate_id`: id của thực thể đó
- `correlation_id`: gom nhiều event của cùng một flow
- `causation_id`: trỏ tới event gần nhất đã dẫn tới event hiện tại trong cùng flow
- `idempotency_key`: gắn event với write command đã được deduplicate
- `source`: event đến từ core, integration, system job hay agent-support flow

---

## 3. Nhóm event theo aggregate

## 3.0 Organization events

> Standalone Organization runtime hiện đã emit các event dưới đây cho schema/API slice đầu tiên. Additive `organization_id` propagation đã bắt đầu trên farm-side, canonical commercial records, current read-model surfaces, và `external_mappings`; integration sync jobs và adapter-facing flows vẫn là phase rollout sau.

### `OrganizationCreated`
Khi một legal-operating owner record được tạo lần đầu.

Payload tối thiểu:
- organization_id
- organization_code
- name
- organization_type
- status

### `OrganizationUpdated`
Khi profile của organization thay đổi.

Payload tối thiểu:
- organization_id
- changed_fields
- after_summary

### `OrganizationActivated`
Khi organization chuyển từ `draft` hoặc `paused` sang `active`.

Payload tối thiểu:
- organization_id
- old_status
- new_status

### `OrganizationPaused`
Khi organization bị tạm dừng.

Payload tối thiểu:
- organization_id
- old_status
- new_status
- reason

### `OrganizationClosed`
Khi organization bị đóng và không còn tiếp tục lifecycle hiện tại.

Payload tối thiểu:
- organization_id
- old_status
- new_status
- reason

## 3.0A ProjectScope events

> `ProjectScope` là docs-first baseline trong PR này. Runtime event emission sẽ đến theo rollout sau, nên nhóm event này đang là canonical contract trước implementation.

### `ProjectScopeCreated`
Khi một project/value stream scope được tạo dưới một `Organization`.

Payload tối thiểu:
- project_scope_id
- organization_id
- project_scope_code
- name
- scope_type
- status

### `ProjectScopeUpdated`
Khi profile, metadata, parent-child grouping, hoặc owner context của scope thay đổi.

Payload tối thiểu:
- project_scope_id
- changed_fields
- after_summary

### `ProjectScopeActivated`
Khi scope chuyển từ `draft` hoặc `paused` sang `active`.

Payload tối thiểu:
- project_scope_id
- old_status
- new_status

### `ProjectScopePaused`
Khi scope bị tạm dừng mà chưa đóng lifecycle.

Payload tối thiểu:
- project_scope_id
- old_status
- new_status
- reason

### `ProjectScopeClosed`
Khi scope được kết thúc ở mức nghiệp vụ.

Payload tối thiểu:
- project_scope_id
- old_status
- new_status
- reason

### `ProjectScopeArchived`
Khi scope được archive khỏi lane vận hành thường xuyên nhưng vẫn giữ để audit/report.

Payload tối thiểu:
- project_scope_id
- old_status
- new_status

## 3.0B Project assignment, contribution, và financial attribution events

> Nhóm event này cũng là docs-first baseline. Chúng tồn tại để lock payload shape và semantics trước khi runtime slice được ship.

### `ProjectAssignmentAdded`
Khi một target được gắn vào một `ProjectScope`.

Payload tối thiểu:
- project_assignment_id
- project_scope_id
- target_type
- target_id
- assignment_role
- attribution_kind
- attribution_weight
- confidence_level

### `ProjectAssignmentConfirmed`
Khi assignment được xác nhận là đủ tin cậy cho reporting hoặc workflow tiếp theo.

Payload tối thiểu:
- project_assignment_id
- project_scope_id
- target_type
- target_id
- confirmed_by
- confirmed_at

### `ProjectAssignmentAdjusted`
Khi assignment đổi weight, đổi primary flag, hoặc đổi attribution kind.

Payload tối thiểu:
- project_assignment_id
- old_summary
- new_summary

### `ProjectAssignmentRemoved`
Khi assignment bị kết thúc hoặc revoke.

Payload tối thiểu:
- project_assignment_id
- project_scope_id
- target_type
- target_id
- reason

### `ProjectContributionRecorded`
Khi một contribution fact được ghi vào contribution ledger.

Payload tối thiểu:
- project_contribution_event_id
- project_scope_id
- actor_id
- contribution_type
- role
- quantity
- estimated_value
- status

### `ProjectContributionConfirmed`
Khi contribution được xác nhận hợp lệ.

Payload tối thiểu:
- project_contribution_event_id
- project_scope_id
- confirmed_by
- confirmed_at

### `ProjectContributionRejected`
Khi contribution bị từ chối.

Payload tối thiểu:
- project_contribution_event_id
- project_scope_id
- reason

### `ProjectContributionReversed`
Khi một contribution đã ghi cần bị đảo hoặc bù trừ bằng fact mới.

Payload tối thiểu:
- project_contribution_event_id
- project_scope_id
- reason

### `CostRecorded`
Khi một operational cost fact được ghi nhận.

Payload tối thiểu:
- cost_record_id
- organization_id
- project_scope_id
- cost_type
- amount
- currency
- recognized_at

### `RevenueRecorded`
Khi một operational revenue fact được ghi nhận.

Payload tối thiểu:
- revenue_record_id
- organization_id
- project_scope_id
- revenue_type
- gross_amount
- net_amount
- currency
- recognized_at

### `FinancialAllocationRecorded`
Khi một cost hoặc revenue được split sang nhiều `ProjectScope`.

Payload tối thiểu:
- financial_allocation_id
- source_record_type
- source_record_id
- project_scope_id
- allocation_basis
- allocation_weight
- allocated_amount

### `SharedResourceAllocated`
Khi một shared resource được allocate cho một `ProjectScope`.

Payload tối thiểu:
- shared_resource_id
- project_scope_id
- allocation_basis
- allocated_capacity
- effective_at

### `SharedResourceReleased`
Khi một shared resource allocation kết thúc hoặc được trả lại.

Payload tối thiểu:
- shared_resource_id
- project_scope_id
- released_capacity
- released_at

## 3.1 Customer events

### `CustomerCreated`
Khi hồ sơ khách được tạo lần đầu.

Payload tối thiểu:
- customer_id
- customer_code
- phone
- channel_source

### `CustomerUpdated`
Khi thông tin khách thay đổi.

Payload tối thiểu:
- changed_fields
- after_summary

### `CustomerMerged`
Khi 2 hồ sơ được hợp nhất.

Payload tối thiểu:
- source_customer_ids
- target_customer_id

### `CustomerPreferenceUpdated`
Khi preference được xác nhận hoặc chỉnh sửa.

Payload tối thiểu:
- preference_type
- preference_value
- source
- confidence_level
- confirmed_by
- confirmed_at

Rule baseline:
- event này dùng cho cả hai trường hợp: xác nhận candidate thành canonical, hoặc chỉnh sửa một preference đã canonicalized
- chỉ `Sales`, `CSKH`, `Admin vận hành`, hoặc `Founder / Super Admin` mới được phát sinh event xác nhận preference canonical
- trusted integration chỉ được phát sinh event này khi request có `actor_role=integration`, `actor_id`, và `external_ref`; nếu không thì payload integration vẫn là candidate/input
- nếu source là CRM hoặc AI nhưng chưa có người xác nhận, dữ liệu vẫn chỉ là candidate/input cho workflow
- route `POST /api/v1/customers/{customer_id}/preferences` hiện chỉ phát event cho canonical confirmation/update; candidate ingest raw từ AI/CRM chưa có public customer API riêng trong phase này
- event này phải đủ để audit được ai đã xác nhận và candidate nào đã được canonicalize

### `CustomerDuplicateCandidateReviewed`
Phase hiện tại chưa phát domain event riêng cho duplicate-candidate review.

Rule baseline:
- quyết định review vẫn phải có audit log đầy đủ
- action review chỉ mở cho `Sales`, `CSKH`, `Admin vận hành`, hoặc `Founder / Super Admin`
- nếu sau này review outcome bắt đầu kích projection hay workflow liên domain, cần thêm event riêng thay vì chỉ dựa vào audit log

### `CustomerSegmentChanged`
Khi khách được chuyển segment.

Payload tối thiểu:
- old_segment
- new_segment

### `CustomerLastPurchaseUpdated`
Khi hệ xác nhận đơn delivered và cập nhật lần mua gần nhất.

Payload tối thiểu:
- customer_id
- last_order_id
- last_purchase_at

---

## 3.2 Preorder events

Phase 1.x note:
- preorder event payloads on the live runtime now carry nullable `organization_id` / `organizationId` context when the preorder belongs to an organization.

### `PreorderPlaced`
Khi tạo một cam kết preorder mới.

Payload:
- preorder_id
- customer_id
- sku_id
- committed_qty

### `PreorderAdjusted`
Khi preorder bị tăng/giảm.

Payload:
- preorder_id
- old_committed_qty
- new_committed_qty
- reason

### `PreorderConfirmed`
Khi preorder chuyển từ draft sang confirmed.

Payload:
- preorder_id
- status

### `PreorderActivated`
Khi preorder chuyển sang trạng thái active và bắt đầu có thể giao dần.

Payload:
- preorder_id
- active_from

### `PreorderCancelled`
Khi preorder bị hủy.

Payload:
- preorder_id
- cancelled_qty
- reason

### `PreorderQuotaConsumed`
Khi delivery làm giảm quota thật của preorder.

Payload:
- preorder_id
- order_id
- consumed_qty

### `PreorderCompleted`
Khi preorder đã giao đủ hoặc kết thúc hợp lệ.

Payload:
- preorder_id
- final_delivered_qty

---

## 3.3 Plot / Crop events

Rule baseline:
- phase đầu mặc định phát sinh plot/crop events từ Core-owned summary workflow
- nếu phase sau LiteFarm trở thành nguồn sâu cho một tenant, các event sync vẫn phải map về snapshot tối thiểu trong Core trước khi đi vào flow thương mại

### `PlotCreated`
Payload:
- plot_id
- area
- location

### `CropCycleStarted`
Payload:
- crop_cycle_id
- plot_id
- crop_name
- start_date

### `GrowthStageUpdated`
Payload:
- crop_cycle_id
- old_stage
- new_stage

### `ExpectedHarvestUpdated`
Payload:
- crop_cycle_id
- expected_harvest_from
- expected_harvest_to

### `CropCycleClosed`
Payload:
- crop_cycle_id
- final_yield_qty
- status

---

## 3.4 Lot events

Phase 1.x note:
- lot event payloads on the live runtime now carry nullable `organization_id` / `organizationId` context when the lot belongs to an organization.

### `HarvestedLotCreated`
Khi một harvested lot mới được tạo từ crop cycle.

Payload:
- lot_id
- source_ref_id
- sku_id
- actual_qty
- harvest_date

### `ProcessedLotCreated`
Khi một processed lot mới được tạo từ processing batch hoặc process run đã xác định rõ.

Payload:
- lot_id
- process_ref_id
- sku_id
- actual_qty
- production_date

### `LotAdjusted`
Khi quantity thực tế của một lot thay đổi sau cân lại, kiểm kho hoặc correction hợp lệ.

Payload:
- lot_id
- old_qty
- new_qty
- reason

### `LotQualityChecked`
Payload:
- lot_id
- quality_status
- checked_by

### `LotReleaseRequested`
Khi có yêu cầu release lot, dùng nếu workflow cần tách bước request và approval.

Payload:
- lot_id
- requested_qty
- requested_by

Rule baseline:
- dùng cho case release nhạy cảm, release ngoài threshold, hoặc release khi policy cần lớp approve riêng

### `LotReleased`
Khi lot được mở để allocate.

Payload:
- lot_id
- released_qty
- available_qty
- reserved_qty

Nên có thêm khi policy yêu cầu:
- released_by
- approval_ref

### `LotReleaseAdjusted`
Phase sau, dùng khi release quantity được chỉnh như một workflow riêng thay vì đi qua `LotAdjusted`.

Payload:
- lot_id
- old_released_qty
- new_released_qty
- reason

### `LotBlocked`
Khi lot bị chặn.

Payload:
- lot_id
- reason
- released_qty
- available_qty
- reserved_qty

### `LotUnblocked`
Payload:
- lot_id
- reason
- released_qty
- available_qty
- reserved_qty

---

## 3.5 Order events

Phase 1.x note:
- order event payloads on the live runtime now carry nullable `organization_id` / `organizationId` context when the order belongs to an organization.

### `OrderCreated`
Payload:
- order_id
- customer_id
- channel
- line_count

### `OrderConfirmed`
Payload:
- order_id
- confirmed_by

### `OrderUpdated`
Payload:
- changed_fields

### `OrderCancelRequested`
Payload:
- order_id
- requested_by
- reason

Rule baseline:
- event này là bắt buộc khi order đã qua mốc `packed` mà cần đi tới cancel flow
- cancel request không đồng nghĩa cancel đã được approve

### `OrderCancelled`
Payload:
- order_id
- cancelled_by
- reason

Rule baseline:
- nếu cancel xảy ra sau `packed`, event này phải có dấu vết approval hoặc policy reference đi kèm

---

## 3.6 Allocation / inventory events

### `OrderAllocated`
Payload:
- order_id
- order_line_id
- lot_id
- allocated_qty

### `OrderPartiallyAllocated`
Payload:
- order_id
- allocated_qty_summary
- remaining_unallocated_qty

### `AllocationAdjusted`
Payload:
- allocation_id
- order_id
- order_line_id
- lot_id
- old_qty
- new_qty
- reason
- approval_ref

Rule baseline:
- nếu adjustment là override ngoài policy thường, event phải có `approved_by` hoặc `approval_ref`
- phase 1 runtime phát event này từ public command `POST /api/v1/orders/{order_id}/allocations/{allocation_id}/adjust`

### `AllocationReleased`
Khi bỏ giữ chỗ của lot.

Payload:
- allocation_id
- order_id
- order_line_id
- lot_id
- released_qty
- reason
- approval_ref

Rule baseline:
- phase 1 runtime phát event này từ public command `POST /api/v1/orders/{order_id}/allocations/{allocation_id}/release`
- khi release xảy ra qua adjust-down, release route, hoặc cancel flow thì quantity phải quay lại lot bằng `release_reservation` inventory movement

### `InventoryReleased`
Khi quantity của lot được đưa vào pool có thể reserve.

Payload:
- lot_id
- qty

### `InventoryReserved`
Khi quantity bị giữ chỗ cho order.

Payload:
- lot_id
- order_id
- qty

### `InventoryReserveReleased`
Khi quantity đã reserve được trả lại.

Payload:
- lot_id
- order_id
- qty

### `InventoryConsumed`
Khi quantity thực sự được tiêu thụ bởi packing / delivery logic.

Payload:
- lot_id
- order_id
- qty

### `InventoryAdjusted`
Khi quantity bị chỉnh tay có kiểm soát.

Payload:
- lot_id
- old_qty
- new_qty
- reason

### `InventoryDiscarded`
Khi hàng bị bỏ / hỏng / không dùng được.

Payload:
- lot_id
- qty
- reason

---

## 3.7 Packing / delivery events

### `OrderPacked`
Payload:
- order_id
- packed_qty_summary
- packed_by

### `OrderPartiallyPacked`
Payload:
- order_id
- packed_qty
- shortage_qty

### `OrderPackingAdjusted`
Payload:
- order_id
- old_packed_qty
- new_packed_qty
- reason

### `OrderShipped`
Payload:
- order_id
- carrier
- tracking_ref

### `OrderDelivered`
Payload:
- order_id
- delivered_qty_summary
- delivered_at

### `OrderPartiallyDelivered`
Payload:
- order_id
- delivered_qty
- remaining_qty

### `OrderDeliveryFailed`
Payload:
- order_id
- reason
- note

---

## 3.8 Payment events

### `PaymentExpected`
Payload:
- order_id
- amount_expected

### `PaymentReceived`
Payload:
- order_id
- amount_received
- method

### `PaymentAdjusted`
Payload:
- order_id
- old_amount
- new_amount
- reason

Rule baseline:
- payment status trong Core là operational truth
- adjustment nhạy cảm phải có approval theo permission matrix

### `PaymentReconciliationFlagged`
Khi operational payment state ở Core lệch khỏi accounting final ở ERP.

Payload:
- order_id
- core_payment_status
- erp_accounting_status
- reason
- flagged_by

---

## 3.9 Integration events

### `ERPOrderSynced`
Payload:
- order_id
- erp_ref

### `FarmPlotSynced`
Payload:
- plot_id
- external_ref

### `CRMCustomerSynced`
Payload:
- customer_id
- crm_ref

### `IntegrationSyncFailed`
Payload:
- object_type
- object_id
- target_system
- reason

### `LiteFarmSnapshotApplied`
Khi snapshot plot/crop từ LiteFarm được apply vào Core cho tenant đã chốt integration.

Payload:
- tenant_ref
- plot_id
- crop_cycle_id
- external_ref

### `ERPReconciliationConfirmed`
Khi conflict giữa Core operational state và ERP accounting final state đã được con người xác nhận xử lý xong.

Payload:
- order_id
- resolved_by
- resolution_note

---

## 3.10 Agent / automation support events

### `AgentSuggestionCreated`
Payload:
- suggestion_type
- target_object
- confidence

### `AgentActionProposed`
Payload:
- action_type
- target_object
- requires_approval

### `AgentActionApproved`
Payload:
- action_type
- approved_by

### `AgentActionRejected`
Payload:
- action_type
- rejected_by
- reason

---

## 4. Event naming rules

### Nên dùng
- `CustomerCreated`
- `LotReleased`
- `OrderDelivered`

### Không nên dùng
- `CreateCustomer`
- `DoAllocation`
- `HandleDelivery`

Lý do:
- event là **sự việc đã xảy ra**
- command mới là “hãy làm”

---

## 5. Event nào bắt buộc phải có ngay trong phase đầu

Bộ xương sống phase đầu:

- `CustomerCreated`
- `PreorderPlaced`
- `PreorderQuotaConsumed`
- `OrderCreated`
- `HarvestedLotCreated`
- `ProcessedLotCreated`
- `LotReleased`
- `OrderAllocated`
- `OrderPacked`
- `OrderDelivered`
- `CustomerPreferenceUpdated`

Các event sau nên được chuẩn bị ngay khi workflow nhạy cảm bắt đầu xuất hiện:
- `LotReleaseRequested`
- `OrderCancelRequested`
- `PaymentReconciliationFlagged`

Chúng không nhất thiết phải được emit ở mọi flow phase đầu, nhưng phải có chỗ đứng rõ trong catalog để tránh approval path bị làm âm thầm.

Nếu thiếu bộ này, hệ rất khó:
- debug
- build dashboard
- build AI support sau này

## 6. Quan hệ giữa event và state

Một nguyên tắc quan trọng:
- state là ảnh chụp hiện tại
- event là lịch sử tạo ra state đó

Khi team thêm state quan trọng mới, phải tự hỏi:
- event tương ứng đã có chưa?
- payload tối thiểu đã đủ chưa?
- event này có giúp audit / replay / phân tích không?

## 7. Kết luận

Event catalog không phải để “làm event sourcing cho sang”.  
Nó là ngôn ngữ vận hành chung của hệ.

Nếu 6 tháng nữa team không nhớ:
- vì sao order lại ở trạng thái này
- vì sao available_qty còn số đó
- vì sao quota preorder bị trừ

thì gần như chắc chắn là event log đang thiếu hoặc event đang quá nghèo.
