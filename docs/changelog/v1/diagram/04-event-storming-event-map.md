# 04. Event Storming / Event Map

## Mục đích
Sơ đồ này mô tả các event mốc của chuỗi giá trị và các command/policy chính liên quan.

> **Phạm vi:**
> - `[Phase 1 ✅]` = event đang được emit trong `agos_app/app/services/`
> - `[Phase 2 🔜]` = event đã thiết kế nhưng chưa implement
>
> **Tên event:** dùng PascalCase (class style) trong diagram. Runtime style là dotted lowercase.
> Xem mapping đầy đủ tại `docs/changelog/v1/architecture/05-event-catalog.md`.

## Mermaid

```mermaid
flowchart LR
    subgraph CustomerDomain["Customer / Demand [Phase 1 ✅]"]
        C0["Command: CreateCustomer"] --> E0["Event: CustomerCreated\norder.created → CustomerCreated"]
        C2["Command: UpdatePreference"] --> E2["Event: CustomerPreferenceUpdated"]
    end

    subgraph PreorderDomain["Preorder / Commitment [Phase 1 ✅]"]
        P0["Command: PlacePreorder"] --> EP1["Event: PreorderPlaced\npreorder.placed → PreorderPlaced"]
        P1["Command: AdjustPreorder"] --> EP2["Event: PreorderAdjusted\npreorder.adjusted → PreorderAdjusted"]
        P2["Command: CancelPreorder"] --> EP3["Event: PreorderCancelled [Phase 2 🔜]"]
    end

    subgraph FarmDomain["Farm / Production [Phase 1 ✅ partial]"]
        F4["Command: CreateHarvestLot"] --> F5["Event: LotHarvestCreated\nlot.harvest.created → LotHarvestCreated"]
        F10["Command: CreateProcessedLot"] --> F11["Event: LotProcessedCreated\nlot.processed.created → LotProcessedCreated"]
        F8["Command: AdjustHarvestLot"] --> F9["Event: LotAdjusted\nlot.adjusted → LotAdjusted"]
        F6["Command: AttachLotEvidence"] --> F7["Event: LotEvidenceAdded\nlot.evidence.added → LotEvidenceAdded"]
        F0["Command: PlanCropTask [Phase 2 🔜]"] --> F1["Event: CropTaskPlanned [Phase 2 🔜]"]
        F2["Command: CompleteCropTask [Phase 2 🔜]"] --> F3["Event: CropTaskCompleted [Phase 2 🔜]"]
    end

    subgraph QCDomain["QC / Release [Phase 1 ✅ partial]"]
        Q0["Command: SubmitLotForQC"] --> Q1["Event: LotQcReviewed\nlot.qc.reviewed → LotQcReviewed"]
        Q2["Command: RequestMoreEvidence"] --> Q3["Event: LotQCRequestedMoreEvidence"]
    end

    subgraph LotReleaseDomain["Lot Release [Phase 1 ✅]"]
        RL4["Command: ReleaseLot"] --> RL5["Event: LotReleased\nlot.released → LotReleased"]
        RL6["Command: BlockLot"] --> RL7["Event: LotBlocked\nlot.blocked → LotBlocked"]
        RL8["Command: UnblockLot"] --> RL9["Event: LotUnblocked\nlot.unblocked → LotUnblocked"]
    end

    subgraph OrderDomain["Order / Fulfillment [Phase 1 ✅]"]
        O0["Command: CreateOrder"] --> O1["Event: OrderCreated\norder.created → OrderCreated"]
        O_C["Command: ConfirmOrder"] --> O_CE["Event: OrderConfirmed\norder.confirmed → OrderConfirmed"]
        O2["Command: AllocateOrderLine"] --> O3["Event: OrderAllocated\norder.allocated → OrderAllocated"]
        O4["Command: PackOrder"] --> O5["Event: OrderPacked\norder.packed → OrderPacked"]
        O6["Command: ShipOrder"] --> O7["Event: OrderShipped\norder.shipped → OrderShipped"]
        O8["Command: DeliverOrder"] --> O9["Event: OrderDelivered\norder.delivered → OrderDelivered"]
        O10["Command: RequestCancelOrder"] --> O11["Event: OrderCancelRequested\norder.cancel_requested → OrderCancelRequested"]
        O12["Command: CancelOrder"] --> O13["Event: OrderCancelled\norder.cancelled → OrderCancelled"]
    end

    EP1 --> F5
    F5 --> RL4
    F7 --> Q1
    Q1 --> RL4
    RL7 --> RL8
    RL8 --> Q1
    RL5 --> O2
    O1 --> O_C
    O_C --> O2
    O2 --> O5
    O5 --> O7
    O7 --> O9
    O9 --> E2

    P1["Policy: only released lot can allocate"] -.-> O2
    P2["Policy: packed order cancel needs approval [Phase 2 🔜]"] -.-> O13
    P3["Policy: minimum evidence before QC [Phase 2 🔜]"] -.-> Q1
```

## Event Name Reference (Phase 1)

| Command | Event (PascalCase) | Runtime name (dotted) |
|---|---|---|
| CreateCustomer | CustomerCreated | `customer.created` |
| UpdatePreference | CustomerPreferenceUpdated | `customer.preference_updated` |
| PlacePreorder | PreorderPlaced | `preorder.placed` |
| AdjustPreorder | PreorderAdjusted | `preorder.adjusted` |
| CreateHarvestLot | LotHarvestCreated | `lot.harvest.created` |
| CreateProcessedLot | LotProcessedCreated | `lot.processed.created` |
| AdjustHarvestLot | LotAdjusted | `lot.adjusted` |
| AttachLotEvidence | LotEvidenceAdded | `lot.evidence.added` |
| SubmitLotForQC | LotQcReviewed | `lot.qc.reviewed` |
| ReleaseLot | LotReleased | `lot.released` |
| BlockLot | LotBlocked | `lot.blocked` |
| UnblockLot | LotUnblocked | `lot.unblocked` |
| CreateOrder | OrderCreated | `order.created` |
| ConfirmOrder | OrderConfirmed | `order.confirmed` |
| AllocateOrderLine | OrderAllocated | `order.allocated` |
| PackOrder | OrderPacked | `order.packed` |
| ShipOrder | OrderShipped | `order.shipped` |
| DeliverOrder | OrderDelivered | `order.delivered` |
| RequestCancelOrder | OrderCancelRequested | `order.cancel_requested` |
| CancelOrder | OrderCancelled | `order.cancelled` |
