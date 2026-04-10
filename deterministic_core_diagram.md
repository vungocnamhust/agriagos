Được, tớ vẽ cho cậu bộ **Mermaid code chi tiết của phần deterministic core** theo đúng kiến trúc mình vừa chốt.
Tớ chia thành 6 sơ đồ để dễ dùng lại trong docs kỹ thuật.

Các sơ đồ này bám đúng các nguyên tắc cậu đã khóa: **canonical data model**, **event bus + schema chuẩn**, **workflow/policy cứng**, **one truth, many views**, và triển khai trước các luồng **crop task, lot/QC/truy xuất, order/allocation/cancel, reminders/data-gap**.

---

## 1) Sơ đồ tổng thể deterministic core

```mermaid
flowchart TB
    subgraph INPUT["Inputs"]
        UI["Internal UI / Admin App / Farmer App"]
        WEBHOOK["Webhook / External Systems"]
        API["Public/Internal API"]
    end

    subgraph CORE["Deterministic Core"]
        CG["Command Gateway
        - validate schema
        - authz / RBAC
        - idempotency
        - correlation id"]
        
        APP["Application Services
        - farm_core
        - crop_task
        - lot_traceability
        - qc_workflow
        - order_ops"]
        
        POL["Policy + Workflow Engine
        - transition rules
        - approval rules
        - guard conditions
        - escalation rules"]
        
        EVT["Event Store
        - domain events
        - append-only log"]
        
        STATE["Canonical State Tables
        - farmers
        - plots
        - crop_cycles
        - crop_tasks
        - lots
        - qc_reviews
        - orders
        - allocations
        - customers"]
        
        OUTBOX["Outbox Events"]
        AUDIT["Audit Log"]
    end

    subgraph READ["Projection / Read Side"]
        PROJ["Projection Workers"]
        RM1["Farmer Task View"]
        RM2["QC Board View"]
        RM3["Order Board View"]
        RM4["Traceability View"]
        RM5["Ops Metrics View"]
    end

    subgraph JOBS["Background Jobs"]
        SCH["Scheduler
        - overdue check
        - missing evidence check
        - stuck order check"]
        NOTI["Notification / Reminder Worker"]
    end

    UI --> CG
    WEBHOOK --> CG
    API --> CG

    CG --> APP
    APP --> POL
    POL -->|allowed| EVT
    POL -->|deny / escalate| AUDIT

    EVT --> STATE
    EVT --> OUTBOX
    EVT --> AUDIT

    OUTBOX --> PROJ
    PROJ --> RM1
    PROJ --> RM2
    PROJ --> RM3
    PROJ --> RM4
    PROJ --> RM5

    SCH --> CG
    OUTBOX --> NOTI
```

---

## 2) Generic write flow: command → policy → event → state → projection

```mermaid
sequenceDiagram
    autonumber
    participant U as User/System
    participant CG as Command Gateway
    participant APP as Application Service
    participant POL as Policy Engine
    participant EVT as Event Store
    participant ST as Canonical State
    participant OB as Outbox
    participant PR as Projection Worker
    participant RV as Read Models
    participant AU as Audit Log

    U->>CG: Submit command
    Note over CG: Validate schema<br/>Check authz<br/>Check idempotency
    CG->>APP: Normalized command
    APP->>POL: Evaluate command against current state
    POL-->>APP: allow / deny / escalate

    alt denied or escalated
        APP->>AU: Write audit record
        APP-->>CG: Error / escalation response
        CG-->>U: Denied or needs approval
    else allowed
        APP->>EVT: Append domain event(s)
        EVT->>ST: Apply state mutation
        EVT->>OB: Publish outbox event
        EVT->>AU: Write audit record
        OB->>PR: Consume event
        PR->>RV: Update read models
        CG-->>U: Success response
    end
```

---

## 3) Crop Task logic flow

```mermaid
flowchart TB
    START["PlanCropTask command"] --> VALIDATE["Validate:
    - crop_cycle exists
    - task_type valid
    - due_date valid"]

    VALIDATE --> POLICY1{"Policy check"}
    POLICY1 -->|fail| ERR1["Reject command
    INVALID_TASK_PLAN"]
    POLICY1 -->|pass| EVT1["Event: CropTaskPlanned"]

    EVT1 --> STATE1["Create CropTask
    status = planned"]

    STATE1 --> ASSIGN["AssignCropTask command"]
    ASSIGN --> POLICY2{"Assignee valid?"}
    POLICY2 -->|no| ERR2["Reject
    INVALID_ASSIGNEE"]
    POLICY2 -->|yes| EVT2["Event: CropTaskAssigned"]
    EVT2 --> STATE2["status = assigned"]

    STATE2 --> WORK["Worker starts task"]
    WORK --> EVT3["Event: CropTaskStarted"]
    EVT3 --> STATE3["status = in_progress"]

    STATE3 --> COMPLETE["CompleteCropTask command"]
    COMPLETE --> POLICY3{"Evidence required?"}

    POLICY3 -->|no| EVT4["Event: CropTaskCompleted"]
    POLICY3 -->|yes, missing| ERR3["Reject
    MISSING_TASK_EVIDENCE"]
    POLICY3 -->|yes, present| EVT4

    EVT4 --> STATE4["status = completed"]

    STATE4 --> VERIFY["VerifyCropTask command"]
    VERIFY --> POLICY4{"Verifier role allowed?"}
    POLICY4 -->|no| ERR4["Reject
    FORBIDDEN"]
    POLICY4 -->|yes| EVT5["Event: CropTaskVerified"]
    EVT5 --> STATE5["status = verified"]

    STATE2 --> CRON["Scheduler tick"]
    STATE3 --> CRON
    CRON --> POLICY5{"due_date passed and not completed?"}
    POLICY5 -->|yes| EVT6["Event: CropTaskOverdue"]
    POLICY5 -->|no| END1["No change"]
    EVT6 --> STATE6["status = overdue"]
    STATE6 --> REM1["Create reminder / alert"]
```

### State machine riêng cho Crop Task

```mermaid
stateDiagram-v2
    [*] --> planned
    planned --> assigned: AssignCropTask
    planned --> cancelled: CancelCropTask

    assigned --> in_progress: StartTask
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

## 4) Lot + Traceability + QC logic flow

```mermaid
flowchart TB
    H1["CreateHarvestLot command"] --> V1["Validate:
    - crop_cycle exists
    - quantity > 0
    - lot code unique"]

    V1 --> P1{"Policy check"}
    P1 -->|fail| E1["Reject command"]
    P1 -->|pass| EV1["Event: HarvestedLotCreated"]

    EV1 --> S1["Lot created
    status = created"]

    S1 --> EVID["AttachLotEvidence command"]
    EVID --> V2["Validate evidence type / file / metadata"]
    V2 --> EV2["Event: LotEvidenceAttached"]
    EV2 --> S2["Evidence linked to lot"]

    S2 --> SUBMIT["SubmitLotForQC command"]
    SUBMIT --> P2{"Minimum evidence set satisfied?"}
    P2 -->|no| EV3["Event: LotQCRequestedMoreEvidence"]
    P2 -->|yes| EV4["Event: LotSubmittedForQC"]

    EV3 --> S3["status = waiting_evidence"]
    S3 --> ALERT1["Notify farmer / ops: missing evidence"]

    EV4 --> S4["status = qc_review"]

    S4 --> REVIEW["QC reviewer checks lot"]
    REVIEW --> P3{"QC result"}
    P3 -->|pass| EV5["Event: LotPassedQC"]
    P3 -->|fail| EV6["Event: LotFailedQC"]
    P3 -->|need more evidence| EV7["Event: LotQCRequestedMoreEvidence"]

    EV5 --> RELEASE["ReleaseLot command"]
    RELEASE --> P4{"All release guards satisfied?"}
    P4 -->|no| ERR1["Reject release"]
    P4 -->|yes| EV8["Event: LotReleased"]
    EV8 --> S5["status = released"]

    EV6 --> BLOCK["Event: LotBlocked"]
    BLOCK --> S6["status = blocked"]

    EV7 --> S7["status = waiting_evidence"]
    S7 --> ALERT2["Notify missing evidence"]

    S5 --> ALLOC["Lot available for order allocation"]
```

### State machine riêng cho Lot/QC

```mermaid
stateDiagram-v2
    [*] --> created
    created --> in_progress: Begin lot work
    in_progress --> waiting_evidence: Evidence incomplete
    in_progress --> qc_review: SubmitLotForQC

    waiting_evidence --> qc_review: SubmitLotForQC
    qc_review --> released: PassQC + ReleaseLot
    qc_review --> blocked: FailQC
    qc_review --> waiting_evidence: NeedMoreEvidence

    blocked --> waiting_evidence: Add more evidence
    released --> consumed: Allocated and fully used
    consumed --> archived: Archive
    archived --> [*]
```

---

## 5) Order + Allocation + Cancel logic flow

```mermaid
flowchart TB
    O1["CreateOrder command"] --> V1["Validate:
    - customer exists or resolve identity
    - order lines valid
    - SKU valid"]

    V1 --> EV1["Event: OrderPlaced"]
    EV1 --> S1["Order created
    status = draft"]

    S1 --> CONF["ConfirmOrder command"]
    CONF --> P1{"Order valid to confirm?"}
    P1 -->|no| ERR1["Reject confirm"]
    P1 -->|yes| EV2["Event: OrderConfirmed"]
    EV2 --> S2["status = confirmed"]

    S2 --> ALLOC["AllocateOrderLine command"]
    ALLOC --> P2{"Lot released and qty sufficient?"}
    P2 -->|no| ERR2["Reject allocation
    LOT_NOT_RELEASED / INSUFFICIENT_QTY"]
    P2 -->|yes| EV3["Event: OrderAllocated"]
    EV3 --> S3["status = allocated"]

    S3 --> PACK["PackOrder command"]
    PACK --> P3{"All lines allocated?"}
    P3 -->|no| ERR3["Reject pack"]
    P3 -->|yes| EV4["Event: OrderPacked"]
    EV4 --> S4["status = packed"]

    S4 --> SHIP["ShipOrder command"]
    SHIP --> P4{"Packed and shipping data valid?"}
    P4 -->|no| ERR4["Reject ship"]
    P4 -->|yes| EV5["Event: OrderShipped"]
    EV5 --> S5["status = shipped"]

    S5 --> DELI["DeliverOrder command"]
    DELI --> EV6["Event: OrderDelivered"]
    EV6 --> S6["status = delivered"]

    S2 --> CANREQ["RequestCancelOrder command"]
    S3 --> CANREQ
    S4 --> CANREQ

    CANREQ --> EV7["Event: OrderCancelRequested"]
    EV7 --> S7["status = cancel_requested"]

    S7 --> PCAN{"Cancel policy"}
    PCAN -->|confirmed / allocated| EV8["Event: OrderCancelled"]
    PCAN -->|packed requires approval| AP1["Human approval queue"]
    PCAN -->|shipped or delivered| ERR5["Reject cancel
    open complaint/refund later"]

    AP1 -->|approved| EV8
    AP1 -->|rejected| S8["Return to previous state"]

    EV8 --> S9["status = cancelled"]
```

### State machine riêng cho Order

```mermaid
stateDiagram-v2
    [*] --> draft
    draft --> confirmed: ConfirmOrder
    confirmed --> allocated: AllocateOrderLine
    allocated --> packed: PackOrder
    packed --> shipped: ShipOrder
    shipped --> delivered: DeliverOrder

    confirmed --> cancel_requested: RequestCancelOrder
    allocated --> cancel_requested: RequestCancelOrder
    packed --> cancel_requested: RequestCancelOrder

    cancel_requested --> cancelled: CancelOrder
    cancel_requested --> confirmed: Reject cancel
    cancel_requested --> allocated: Reject cancel
    cancel_requested --> packed: Reject cancel

    delivered --> [*]
    cancelled --> [*]
```

---

## 6) Scheduler / alerts / projections flow

```mermaid
flowchart TB
    subgraph SCHED["Scheduler"]
        T1["Check overdue crop tasks"]
        T2["Check lots missing evidence"]
        T3["Check stuck orders"]
        T4["Check low available released lots"]
    end

    subgraph CMD["System Commands"]
        C1["MarkTaskOverdue"]
        C2["DetectMissingEvidence"]
        C3["DetectOrderStuck"]
        C4["DetectLowReleasedInventory"]
    end

    subgraph CORE["Core Processing"]
        POL["Policy / Workflow Engine"]
        EVT["Domain Events"]
        OUT["Outbox"]
    end

    subgraph PROJ["Projection / Notification"]
        PR1["Update Farmer Task View"]
        PR2["Update QC Board"]
        PR3["Update Order Board"]
        PR4["Update Ops Metrics"]
        N1["Send Reminder to farmer"]
        N2["Send Alert to QC / Ops"]
        N3["Send Alert to sales / CSKH"]
    end

    T1 --> C1
    T2 --> C2
    T3 --> C3
    T4 --> C4

    C1 --> POL
    C2 --> POL
    C3 --> POL
    C4 --> POL

    POL --> EVT
    EVT --> OUT

    OUT --> PR1
    OUT --> PR2
    OUT --> PR3
    OUT --> PR4

    OUT --> N1
    OUT --> N2
    OUT --> N3
```

---

## 7) SSoT + Read Models flow

```mermaid
flowchart LR
    subgraph SSoT["Single Source of Truth"]
        F["Farmers / Plots / Crop Cycles"]
        L["Lots / Evidences / QC Reviews"]
        O["Orders / Allocations"]
        E["Domain Events / Audit Log"]
    end

    subgraph PROJECTION["Projection Engine"]
        P1["Farmer Task Projection"]
        P2["QC Board Projection"]
        P3["Order Board Projection"]
        P4["Traceability Projection"]
        P5["Ops Metrics Projection"]
    end

    subgraph VIEWS["Role-specific Views"]
        V1["Farmer View"]
        V2["QC View"]
        V3["Sales / Ops View"]
        V4["Customer Traceability View"]
        V5["Management Dashboard"]
    end

    F --> P1
    F --> P5
    L --> P2
    L --> P4
    L --> P5
    O --> P3
    O --> P5
    E --> P1
    E --> P2
    E --> P3
    E --> P4
    E --> P5

    P1 --> V1
    P2 --> V2
    P3 --> V3
    P4 --> V4
    P5 --> V5
```

---

## 8) Chỗ để gắn AI sau này, nhưng không phá core

```mermaid
flowchart LR
    subgraph AI["Future AI Layer"]
        BRAIN["Claude / Other Brain"]
        ADP["Brain Adapter"]
    end

    subgraph CORE["Deterministic Core"]
        QUERY["Read APIs / Read Models"]
        CMD["Typed Commands"]
        POL["Policy Engine"]
        EVT["Event Store + Canonical State"]
    end

    BRAIN --> ADP
    ADP --> QUERY
    ADP --> CMD
    CMD --> POL
    POL -->|allowed| EVT
    POL -->|denied / escalate| ADP
```

Ý nghĩa của sơ đồ này là:
**AI chỉ được đọc state và đề xuất/gọi command. Core vẫn là nơi quyết định thật.**

---

Nếu cậu muốn, tin nhắn tiếp theo tớ sẽ vẽ tiếp bộ **Mermaid cho từng module riêng** theo style còn chi tiết hơn nữa:

* `identity`
* `farm_core`
* `crop_task`
* `lot_traceability`
* `qc_workflow`
* `order_ops`
* `eventing_audit`
* `projections`
