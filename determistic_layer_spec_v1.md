Ok, tớ viết luôn bản **module spec của deterministic layer** theo kiểu có thể giao thẳng cho team backend.

Tớ bám đúng hướng mà cậu đã chốt: phải làm **xương sống dữ liệu trước**, rồi mới tới **tự động hóa vận hành cứng** cho đơn hàng, tồn/lô, QC-truy xuất, nhắc việc mùa vụ và cảnh báo đứt dữ liệu. Lõi này phải có **canonical data model**, mọi ghi nhận đi qua **event bus + schema chuẩn**, và toàn bộ hệ đi theo nguyên tắc **one truth, many views**.    

---

# Deterministic Layer Spec — Agri OS v1

## 1. Mục tiêu

Xây một **Deterministic Operating Core** để:

* chuẩn hóa dữ liệu vận hành
* ghi nhận sự kiện xuyên suốt từ đồng ruộng tới đơn hàng
* cưỡng chế workflow/policy cứng
* sinh read models cho từng vai trò
* tạo nền để sau này AI chỉ là một lớp caller đặc biệt của command gateway, không được ghi bừa vào dữ liệu chuẩn

Phạm vi v1:

* `CropTask / mùa vụ`
* `Lot / QC / Traceability`
* `Order / Allocation / Shipping`
* `Customer identity tối thiểu`
* `Audit / Event log / Read models`

Không làm ở v1:

* supervisor agent
* multi-agent
* CRM automation sâu
* content/marketing AI
* planning bằng LLM
* memory/RAG sâu

---

## 2. Kiến trúc tổng thể

```text
Channels / Internal UI / Webhooks
        |
        v
API Layer
        |
        v
Command Gateway
- validate input
- authz / RBAC
- idempotency
- audit
        |
        v
Application Services
- farmer service
- crop-cycle service
- crop-task service
- lot service
- qc service
- order service
- shipping service
        |
        v
Policy + Workflow Engine
        |
        v
Event Store + Core Tables + Outbox
        |
        +--> Projection Workers --> Read Models / BFF Views
        +--> Notifications / Reminders / Alerts
```

Nguyên tắc:

* **write = command -> policy -> domain event -> state update**
* **read = projection/read model**
* **không update row canonical trực tiếp từ UI hoặc AI**
* **mọi thay đổi quan trọng đều để lại event + audit record**

---

## 3. Bounded contexts / module boundaries

## 3.1 `identity`

Quản lý định danh người, hộ, nhân sự, khách hàng, mapping đa kênh.

Phụ trách:

* farmer profile
* worker/user profile
* customer profile
* channel identity binding

Không phụ trách:

* workflow mùa vụ
* order lifecycle
* QC

## 3.2 `farm_core`

Quản lý thửa, vụ, danh mục cây trồng, mùa vụ.

Phụ trách:

* plot
* crop cycle
* crop spec
* planned yield baseline

## 3.3 `crop_task`

Quản lý kế hoạch việc đồng ruộng và xác nhận hoàn thành.

Phụ trách:

* task template
* task instance
* assignment
* overdue/escalation

## 3.4 `lot_traceability`

Quản lý lô thu hoạch/chế biến, chứng cứ, hồ sơ truy xuất.

Phụ trách:

* lot creation
* evidence attachment
* genealogy tối thiểu
* release/block

## 3.5 `qc_workflow`

Quản lý kiểm tra chất lượng và quyết định release/block.

Phụ trách:

* QC checklist
* QC review
* release decision

## 3.6 `order_ops`

Quản lý đơn hàng, cấp phát lot, đóng gói, giao hàng, hủy đơn.

Phụ trách:

* order
* order line
* allocation
* pack/ship
* cancel request

## 3.7 `policy_workflow`

Chứa state machine, transition rules, approval rules.

Phụ trách:

* allowed transitions
* guards
* escalation policies
* approval requirements

## 3.8 `eventing_audit`

Hạ tầng event store, outbox, audit trail.

## 3.9 `projections`

Sinh read models cho:

* farmer task view
* QC board
* lot traceability view
* order board
* customer traceability page

---

## 4. Canonical entities

Bản gốc cậu đã chốt 8 thực thể lõi: Farmer, Plot, Crop Cycle, Lot/Batch, Product SKU, Order, Customer Profile, Interaction/Event. V1 của deterministic layer sẽ dùng gần như đủ bộ này, nhưng triển khai sâu nhất ở `CropCycle`, `Lot`, `Order`, `Event`.  

## 4.1 Farmer

```yaml
Farmer:
  farmer_id: string
  code: string
  name: string
  phone: string?
  status: enum(active, inactive)
  tags: string[]
  created_at: datetime
  updated_at: datetime
```

## 4.2 Plot

```yaml
Plot:
  plot_id: string
  farmer_id: string
  code: string
  name: string
  area_m2: decimal
  location_text: string?
  status: enum(active, inactive)
  created_at: datetime
  updated_at: datetime
```

## 4.3 CropCycle

```yaml
CropCycle:
  crop_cycle_id: string
  plot_id: string
  crop_type: string
  variety: string?
  start_date: date
  expected_harvest_date: date?
  status: enum(planned, active, harvested, closed, cancelled)
  expected_yield_kg: decimal?
  actual_yield_kg: decimal?
  created_at: datetime
  updated_at: datetime
```

## 4.4 CropTask

```yaml
CropTask:
  crop_task_id: string
  crop_cycle_id: string
  task_type: enum(plant, water, weed, fertilize, inspect, harvest, process, other)
  title: string
  due_date: datetime
  assigned_to_user_id: string?
  status: enum(planned, assigned, in_progress, completed, verified, overdue, cancelled)
  evidence_required: boolean
  completed_at: datetime?
  verified_at: datetime?
  created_at: datetime
  updated_at: datetime
```

## 4.5 LotBatch

```yaml
LotBatch:
  lot_id: string
  code: string
  lot_type: enum(harvest, processed)
  source_crop_cycle_id: string?
  source_lot_id: string?
  product_type: string
  quantity_kg: decimal
  unit: string
  harvested_at: datetime?
  processed_at: datetime?
  status: enum(created, in_progress, waiting_evidence, qc_review, released, blocked, consumed, archived)
  created_at: datetime
  updated_at: datetime
```

## 4.6 LotEvidence

```yaml
LotEvidence:
  evidence_id: string
  lot_id: string
  evidence_type: enum(photo, video, checklist, note, document, measurement)
  object_key: string?
  text_value: string?
  captured_at: datetime
  captured_by_user_id: string?
  status: enum(active, rejected)
  created_at: datetime
```

## 4.7 QCReview

```yaml
QCReview:
  qc_review_id: string
  lot_id: string
  checklist_version: string
  result: enum(pending, passed, failed, needs_more_evidence)
  reviewed_by_user_id: string?
  reviewed_at: datetime?
  notes: string?
  created_at: datetime
  updated_at: datetime
```

## 4.8 CustomerProfile

```yaml
CustomerProfile:
  customer_id: string
  code: string
  name: string
  phone: string?
  zalo_id: string?
  fb_psid: string?
  tags: string[]
  created_at: datetime
  updated_at: datetime
```

## 4.9 SalesOrder

```yaml
SalesOrder:
  order_id: string
  code: string
  customer_id: string
  order_channel: enum(zalo, fb, web, admin, phone)
  status: enum(draft, confirmed, allocated, packed, shipped, delivered, cancel_requested, cancelled)
  requested_ship_date: datetime?
  packed_at: datetime?
  shipped_at: datetime?
  delivered_at: datetime?
  cancel_reason: string?
  created_at: datetime
  updated_at: datetime
```

## 4.10 SalesOrderLine

```yaml
SalesOrderLine:
  order_line_id: string
  order_id: string
  sku_code: string
  qty: decimal
  unit: string
  allocated_qty: decimal
  status: enum(open, allocated, packed, shipped, cancelled)
```

## 4.11 Allocation

```yaml
Allocation:
  allocation_id: string
  order_line_id: string
  lot_id: string
  allocated_qty: decimal
  status: enum(active, released, cancelled)
  created_at: datetime
```

## 4.12 Event

```yaml
DomainEvent:
  event_id: string
  aggregate_type: string
  aggregate_id: string
  event_type: string
  event_version: integer
  occurred_at: datetime
  actor_type: enum(user, system, api, future_ai)
  actor_id: string?
  idempotency_key: string?
  correlation_id: string?
  causation_id: string?
  payload_json: jsonb
```

---

## 5. Database tables

Tớ khuyên dùng PostgreSQL.

## 5.1 Core tables

* `farmers`
* `plots`
* `crop_cycles`
* `crop_tasks`
* `lot_batches`
* `lot_evidences`
* `qc_reviews`
* `customer_profiles`
* `sales_orders`
* `sales_order_lines`
* `allocations`

## 5.2 Infrastructure tables

* `domain_events`
* `outbox_events`
* `audit_logs`
* `idempotency_records`
* `workflow_locks`
* `projection_checkpoints`

## 5.3 Suggested technical columns

Mọi bảng canonical nên có:

* `id`
* `version`
* `created_at`
* `updated_at`
* `created_by`
* `updated_by`
* `tenant_id` nếu sau này multi-tenant

Mọi bảng command/event liên quan write nên có:

* `idempotency_key`
* `correlation_id`
* `causation_id`

---

## 6. Domain events

## 6.1 Farm / crop events

* `FarmerRegistered`
* `PlotRegistered`
* `CropCyclePlanned`
* `CropCycleActivated`
* `CropTaskPlanned`
* `CropTaskAssigned`
* `CropTaskCompleted`
* `CropTaskVerified`
* `CropTaskOverdue`
* `HarvestedLotCreated`

## 6.2 Lot / traceability events

* `LotCreated`
* `LotEvidenceAttached`
* `LotEvidenceRejected`
* `LotSubmittedForQC`
* `LotQCRequestedMoreEvidence`
* `LotPassedQC`
* `LotFailedQC`
* `LotReleased`
* `LotBlocked`

## 6.3 Order events

* `OrderPlaced`
* `OrderConfirmed`
* `OrderAllocated`
* `OrderPacked`
* `OrderShipped`
* `OrderDelivered`
* `OrderCancelRequested`
* `OrderCancelled`

## 6.4 Reminder / system events

* `ReminderDue`
* `MissingEvidenceDetected`
* `DataGapDetected`
* `OrderStuckDetected`

---

## 7. Commands

Nguyên tắc: mọi write đi qua **typed domain commands**. Tool/action phải có schema rõ, idempotent, có permission check và audit. Đây cũng khớp với các nguyên tắc tool gateway, schema validation, least privilege và deny-by-default mà cậu đã chốt ở phần kiến trúc.   

## 7.1 Identity / farm commands

* `RegisterFarmer`
* `RegisterPlot`
* `PlanCropCycle`
* `ActivateCropCycle`

## 7.2 Crop task commands

* `PlanCropTask`
* `AssignCropTask`
* `CompleteCropTask`
* `VerifyCropTask`
* `CancelCropTask`

## 7.3 Lot / QC commands

* `CreateHarvestLot`
* `AttachLotEvidence`
* `RejectLotEvidence`
* `SubmitLotForQC`
* `RequestMoreLotEvidence`
* `PassLotQC`
* `FailLotQC`
* `ReleaseLot`
* `BlockLot`

## 7.4 Order commands

* `CreateOrder`
* `ConfirmOrder`
* `AllocateOrderLine`
* `PackOrder`
* `ShipOrder`
* `DeliverOrder`
* `RequestCancelOrder`
* `CancelOrder`

## 7.5 System commands

* `DetectMissingEvidence`
* `MarkTaskOverdue`
* `DetectOrderStuck`
* `RebuildProjection`

---

## 8. Command schemas

Ví dụ schema:

```json
{
  "command": "AttachLotEvidence",
  "idempotency_key": "uuid",
  "actor": {
    "actor_type": "user",
    "actor_id": "usr_123"
  },
  "payload": {
    "lot_id": "lot_001",
    "evidence_type": "photo",
    "object_key": "s3://bucket/path.jpg",
    "captured_at": "2026-04-10T10:30:00Z"
  }
}
```

```json
{
  "command": "RequestCancelOrder",
  "idempotency_key": "uuid",
  "actor": {
    "actor_type": "user",
    "actor_id": "usr_123"
  },
  "payload": {
    "order_id": "ord_001",
    "reason": "khách đổi kế hoạch"
  }
}
```

---

## 9. State machines

## 9.1 CropTask state machine

```text
planned -> assigned -> in_progress -> completed -> verified
planned -> cancelled
assigned -> cancelled
completed -> overdue? no
assigned/in_progress -> overdue
overdue -> completed
```

### Guards

* `AssignCropTask`: task chưa bị cancel
* `CompleteCropTask`: actor là assignee hoặc supervisor
* `VerifyCropTask`: chỉ role `ops_lead` hoặc `qc`
* `MarkTaskOverdue`: chỉ system scheduler

### Rules

* nếu `evidence_required = true` mà không có evidence thì không cho `verified`
* nếu quá `due_date` mà chưa `completed` thì sinh `CropTaskOverdue`

## 9.2 Lot / QC state machine

```text
created -> in_progress -> waiting_evidence -> qc_review -> released
qc_review -> blocked
waiting_evidence -> qc_review
released -> consumed
blocked -> waiting_evidence
```

### Guards

* `SubmitLotForQC`: phải có evidence tối thiểu
* `ReleaseLot`: QCReview.result = passed
* `BlockLot`: fail QC hoặc policy block
* `PassLotQC`: chỉ role `qc_reviewer`
* `FailLotQC`: chỉ role `qc_reviewer`

### Mandatory evidence set

V1 configurable theo `product_type`:

* `photo_harvest`
* `quantity_confirmation`
* `basic_process_note`

## 9.3 Order state machine

```text
draft -> confirmed -> allocated -> packed -> shipped -> delivered
confirmed -> cancel_requested
allocated -> cancel_requested
packed -> cancel_requested
cancel_requested -> cancelled
```

### Guards

* `AllocateOrderLine`: lot phải `released`
* `PackOrder`: tất cả lines phải allocated
* `ShipOrder`: order phải packed
* `CancelOrder`: policy cho phép
* `CancelOrder` trực tiếp bị cấm từ `shipped` trở đi

### Cancel policy

* `confirmed`, `allocated`: có thể auto-cancel
* `packed`: cần approval hoặc reason code
* `shipped`, `delivered`: không cancel, chỉ mở complaint/refund flow sau này

---

## 10. Policy engine rules

## 10.1 Rule categories

* `transition_rules`
* `evidence_rules`
* `allocation_rules`
* `cancel_rules`
* `approval_rules`
* `notification_rules`

## 10.2 Examples

### Rule: lot cannot be allocated if not released

```yaml
rule_id: LOT_RELEASE_REQUIRED_FOR_ALLOCATION
when: command == AllocateOrderLine
assert:
  - lot.status == released
on_fail:
  code: LOT_NOT_RELEASED
  message: "Lot chưa được release nên không thể allocate cho order."
```

### Rule: order cancel after packed requires approval

```yaml
rule_id: ORDER_CANCEL_PACKED_NEEDS_APPROVAL
when: command == CancelOrder
assert:
  - order.status in [confirmed, allocated]
on_fail:
  escalate: true
```

### Rule: lot submission requires minimum evidence

```yaml
rule_id: LOT_MIN_EVIDENCE_REQUIRED
when: command == SubmitLotForQC
assert:
  - evidence.count >= required_min
  - required_types subset_of evidence.types
on_fail:
  code: MISSING_EVIDENCE
```

---

## 11. Read models / projections

Theo nguyên tắc **one truth, many views**, deterministic layer phải sinh projection riêng cho từng vai trò thay vì cho mọi người nhìn cùng một bảng thô.  

## 11.1 `farmer_task_view`

Hiển thị cho nông hộ:

* task hôm nay
* task quá hạn
* lot đang chờ chứng cứ
* sản lượng dự kiến gần thu hoạch

## 11.2 `qc_board_view`

Hiển thị cho QC:

* lots waiting evidence
* lots waiting review
* blocked lots
* evidence completeness %

## 11.3 `order_board_view`

Hiển thị cho ops/sales:

* confirmed orders
* allocated orders
* packed but not shipped
* cancel requested
* stuck orders

## 11.4 `traceability_view`

Hiển thị cho khách/CSKH:

* product
* source lot
* farm/plot summary
* evidence summary đã được công bố
* released status

## 11.5 `ops_dashboard_metrics`

* số task overdue
* số lot waiting evidence
* % lot released đúng hạn
* số order stuck > X giờ
* lead time từ harvest tới released
* lead time từ order tới shipped

---

## 12. API endpoints

## 12.1 Command APIs

```http
POST /api/v1/commands/farmers/register
POST /api/v1/commands/plots/register
POST /api/v1/commands/crop-cycles/plan
POST /api/v1/commands/crop-tasks/plan
POST /api/v1/commands/crop-tasks/assign
POST /api/v1/commands/crop-tasks/complete
POST /api/v1/commands/crop-tasks/verify

POST /api/v1/commands/lots/create-harvest
POST /api/v1/commands/lots/attach-evidence
POST /api/v1/commands/lots/submit-qc
POST /api/v1/commands/lots/pass-qc
POST /api/v1/commands/lots/fail-qc
POST /api/v1/commands/lots/release
POST /api/v1/commands/lots/block

POST /api/v1/commands/orders/create
POST /api/v1/commands/orders/confirm
POST /api/v1/commands/orders/allocate
POST /api/v1/commands/orders/pack
POST /api/v1/commands/orders/ship
POST /api/v1/commands/orders/deliver
POST /api/v1/commands/orders/request-cancel
POST /api/v1/commands/orders/cancel
```

## 12.2 Query APIs

```http
GET /api/v1/farmers/:id
GET /api/v1/plots/:id
GET /api/v1/crop-cycles/:id
GET /api/v1/lots/:id
GET /api/v1/orders/:id

GET /api/v1/views/farmer-task?farmer_id=
GET /api/v1/views/qc-board
GET /api/v1/views/order-board
GET /api/v1/views/traceability/:lot_id
GET /api/v1/views/ops-metrics
```

## 12.3 Event / audit APIs

```http
GET /api/v1/events?aggregate_type=&aggregate_id=
GET /api/v1/audit?actor_id=&from=&to=
```

---

## 13. Background workers

## 13.1 Scheduler worker

Chạy theo cron:

* detect overdue crop tasks
* detect missing lot evidence
* detect stuck orders
* create reminders

## 13.2 Projection worker

Đọc `outbox_events` rồi cập nhật:

* `farmer_task_view`
* `qc_board_view`
* `order_board_view`
* `traceability_view`
* `ops_dashboard_metrics`

## 13.3 Notification worker

Phát thông báo:

* task overdue
* lot thiếu chứng cứ
* lot QC requested more evidence
* order cancel requested

---

## 14. RBAC

## Roles v1

* `admin`
* `ops_lead`
* `farm_manager`
* `qc_reviewer`
* `sales_ops`
* `farmer_user`
* `viewer`

## Permission examples

* `farmer_user`: complete own crop tasks, upload evidence
* `farm_manager`: plan/assign tasks, create lots
* `qc_reviewer`: review QC, release/block lots
* `sales_ops`: create/confirm/pack/ship orders
* `ops_lead`: cancel packed orders, override with audit reason
* `admin`: full access

---

## 15. Audit log spec

Mỗi command phải ghi:

```yaml
AuditLog:
  audit_id: string
  actor_id: string?
  actor_role: string?
  command_name: string
  target_type: string
  target_id: string
  decision: enum(allowed, denied, escalated, failed)
  reason_code: string?
  correlation_id: string?
  created_at: datetime
  metadata_json: jsonb
```

Bắt buộc log:

* command name
* actor
* target
* policy decision
* reason_code nếu deny/escalate
* idempotency_key
* correlation_id

Không log payload nhạy cảm thô.

---

## 16. Idempotency rules

Mọi command write phải nhận `Idempotency-Key`.

Ví dụ:

* retry webhook không tạo 2 order
* upload evidence retry không ghi 2 event giống nhau
* cancel order retry không cancel hai lần

Table:

```yaml
idempotency_records:
  key: string
  command_name: string
  request_hash: string
  response_snapshot: jsonb
  created_at: datetime
  expires_at: datetime
```

---

## 17. Error model

```yaml
ErrorResponse:
  code: string
  message: string
  details: object?
  correlation_id: string
```

Ví dụ:

* `LOT_NOT_RELEASED`
* `MISSING_EVIDENCE`
* `INVALID_TRANSITION`
* `ORDER_ALREADY_SHIPPED`
* `IDEMPOTENCY_CONFLICT`
* `FORBIDDEN_BY_POLICY`

---

## 18. Suggested repo structure

```text
apps/
  agri_os_api/
    src/
      api/
        commands/
        queries/
      application/
        farm/
        crop_task/
        lot_traceability/
        qc/
        order_ops/
      domain/
        identity/
        farm_core/
        crop_task/
        lot_traceability/
        qc_workflow/
        order_ops/
        policy_workflow/
      infrastructure/
        db/
        event_store/
        outbox/
        projections/
        auth/
        audit/
        object_storage/
      workers/
        scheduler/
        projection_worker/
        notification_worker/
      shared/
        types/
        errors/
        utils/
```

---

## 19. V1 implementation priority

Đây chính là cụm mà cậu đã xác định là pha đem lại hiệu quả vận hành rõ nhất: **đơn hàng, tồn/lô, QC-truy xuất, nhắc việc mùa vụ, cảnh báo đứt dữ liệu**.  

### Sprint 1

* canonical schema
* event store
* farmer/plot/crop cycle CRUD
* crop task workflow

### Sprint 2

* harvest lot creation
* attach evidence
* QC review + release/block

### Sprint 3

* order create/confirm/allocate
* pack/ship/deliver
* cancel request/cancel policy

### Sprint 4

* projections
* dashboards
* reminders
* audit log
* idempotency

---

## 20. Future AI integration contract

Sau này khi gắn Claude hoặc framework agent vào, nó **không được gọi DB trực tiếp**. Nó chỉ được gọi các command/query chuẩn.

Brain sau này chỉ có thể:

* gọi query để đọc state
* propose command
* command gateway + policy engine quyết định có chạy hay không

Tức là deterministic layer hôm nay phải được thiết kế như:

> “AI là một client tương lai, không phải là nơi giữ truth.”

---

Nếu cậu muốn, tin nhắn tiếp theo tớ sẽ viết luôn **OpenAPI contract + PostgreSQL DDL khung** cho 3 module đầu: `crop_task`, `lot_traceability`, `order_ops`.
