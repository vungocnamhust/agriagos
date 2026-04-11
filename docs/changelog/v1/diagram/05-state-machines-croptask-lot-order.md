# 05. State Machines: CropTask, Lot, Order, Preorder

> **Đọc trước khi dùng diagram này:**
> - `[Phase 1 ✅]` = đã implement trong `agos_app/app/core/gateway.py`
> - `[Phase 2 🔜]` = có trong enum / architecture docs nhưng chưa enforce trong gateway
> - Tất cả transition được lấy trực tiếp từ `gateway.py::ORDER_TRANSITIONS`, `LOT_TRANSITIONS`, `PREORDER_TRANSITIONS`

---

## 5.1 CropTask State Machine `[Phase 2 🔜]`

> **Lưu ý Phase 1:** Farm module hiện là **read-only**. Gateway chưa enforce CropTask transitions.
> State machine này mô tả intent cho Phase 2 khi farm operations được activate.

```mermaid
stateDiagram-v2
    [*] --> planned
    planned --> assigned: AssignCropTask
    planned --> cancelled: CancelCropTask
    assigned --> in_progress: StartCropTask
    assigned --> overdue: Scheduler marks overdue
    assigned --> cancelled: CancelCropTask
    in_progress --> completed: CompleteCropTask
    in_progress --> overdue: Scheduler marks overdue
    overdue --> completed: CompleteCropTask
    completed --> verified: VerifyCropTask
    verified --> [*]
    cancelled --> [*]
```

---

## 5.2 Lot State Machine

### 5.2a Phase 1 — Implemented `[Phase 1 ✅]`

> Source: `gateway.py::LOT_TRANSITIONS`
> Lots được tạo trực tiếp ở trạng thái `harvested`. QC workflow đầy đủ bị defer sang Phase 2.

```mermaid
stateDiagram-v2
    [*] --> harvested: CreateHarvestedLot
    [*] --> qc_pending: CreateHarvestedLot(requiresQc)
    harvested --> released: ReleaseLot
    harvested --> blocked: BlockLot
    qc_pending --> released: ReleaseLot (passed QC required)
    qc_pending --> blocked: BlockLot
    released --> blocked: BlockLot
    blocked --> qc_pending: UnblockLot
    released --> [*]: note — depleted/closed set by Phase 2
    blocked --> [*]: note — terminal unless explicitly unblocked
```

### 5.2b Phase 2 — Planned `[Phase 2 🔜]`

> Full QC workflow với evidence và review. Chưa có trong gateway Phase 1.

```mermaid
stateDiagram-v2
    [*] --> created
    created --> waiting_evidence: Missing mandatory evidence
    created --> qc_review: SubmitLotForQC
    waiting_evidence --> qc_review: SubmitLotForQC
    qc_review --> released: PassQC + ReleaseLot
    qc_review --> blocked: FailQC
    qc_review --> waiting_evidence: NeedMoreEvidence
    blocked --> waiting_evidence: Add more evidence
    released --> depleted: Allocated and fully consumed
    depleted --> archived: ArchiveLot
    archived --> [*]
```

---

## 5.3 Order State Machine `[Phase 1 ✅]`

> Source: `gateway.py::ORDER_TRANSITIONS`
>
> **Điểm khác so với diagram cũ:**
> - `draft` có thể cancel trực tiếp → `cancelled` (đã có trong code)
> - `confirmed` có thể cancel trực tiếp → `cancelled` (không qua `cancel_requested`)
> - `RejectCancel` transition (cancel_requested → confirmed/allocated/packed) **chưa implement** [Phase 2 🔜]

```mermaid
stateDiagram-v2
    [*] --> draft

    draft --> confirmed: ConfirmOrder
    draft --> cancelled: CancelOrder

    confirmed --> allocated: AllocateOrderLine
    confirmed --> cancelled: CancelOrder

    allocated --> packed: PackOrder
    allocated --> cancel_requested: RequestCancelOrder

    packed --> shipped: ShipOrder
    packed --> cancel_requested: RequestCancelOrder

    cancel_requested --> cancelled: CancelOrder
    %% RejectCancel (cancel_requested → confirmed/allocated/packed) is Phase 2 🔜

    shipped --> delivered: DeliverOrder

    delivered --> [*]
    cancelled --> [*]
```

---

## 5.4 Preorder State Machine `[Phase 1 ✅ / Phase 1.5 🔜]`

> Source: `gateway.py::PREORDER_TRANSITIONS`
>
> **Phase 1:** Preorder được tạo trực tiếp ở trạng thái `active`. `adjust` giữ nguyên state.
> **Phase 1.5 (planned):** Full lifecycle `draft → confirmed → active → completed`.

### 5.4a Phase 1 — Implemented `[Phase 1 ✅]`

```mermaid
stateDiagram-v2
    [*] --> active: CreatePreorder

    active --> active: AdjustPreorder (committed_qty thay đổi)
    active --> cancelled: CancelPreorder

    active --> completed: note — set by system khi delivered_qty >= committed_qty

    completed --> [*]
    cancelled --> [*]
```

### 5.4b Phase 1.5 — Planned `[Phase 1.5 🔜]`

> Full preorder lifecycle với approval flow. `draft` và `confirmed` states tồn tại trong enum
> nhưng gateway chưa enforce.

```mermaid
stateDiagram-v2
    [*] --> draft: CreatePreorderDraft
    draft --> confirmed: ConfirmPreorder
    draft --> cancelled: CancelPreorder
    confirmed --> active: ActivatePreorder
    confirmed --> cancelled: CancelPreorder
    active --> active: AdjustPreorder
    active --> completed: System — delivered_qty >= committed_qty
    active --> cancelled: CancelPreorder
    completed --> [*]
    cancelled --> [*]
```
