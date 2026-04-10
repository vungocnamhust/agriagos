# Sequence Diagram — HarvestedLotCreated to LotReleased

Sơ đồ này mô tả luồng end-to-end từ lúc tạo lô thu hoạch đến lúc lô được release để có thể allocate cho đơn hàng.

Mục tiêu:
- tạo lô gắn đúng crop cycle / plot
- bổ sung chứng cứ truy xuất
- đi qua QC workflow
- chỉ release khi đủ điều kiện

```mermaid
sequenceDiagram
    autonumber
    participant FM as Farm Manager / Farmer App
    participant IN as Agri OS Ingress
    participant FC as Farm Core
    participant LT as Lot Traceability Service
    participant POL as Policy Engine
    participant QC as QC Workflow
    participant OBJ as Object Storage / Evidence
    participant EVT as Event Store
    participant PR as Projection Worker
    participant RV as Read Models / Views
    participant AU as Audit Log

    FM->>IN: CreateHarvestLot
    IN->>FC: Validate crop_cycle / plot / season
    FC-->>IN: crop_cycle valid
    IN->>LT: Create harvest lot
    LT->>EVT: Append HarvestedLotCreated
    EVT->>AU: Audit HarvestedLotCreated
    EVT->>PR: Publish outbox event
    PR->>RV: Update lot_detail_view
    PR->>RV: Update qc_board_view

    FM->>IN: AttachLotEvidence (photo / note / measurement)
    IN->>OBJ: Store evidence file
    OBJ-->>IN: object_key
    IN->>LT: Attach evidence to lot
    LT->>EVT: Append LotEvidenceAttached
    EVT->>AU: Audit LotEvidenceAttached
    EVT->>PR: Publish outbox event
    PR->>RV: Update lot_detail_view
    PR->>RV: Update traceability_graph_view

    FM->>IN: SubmitLotForQC
    IN->>POL: Check minimum evidence set
    alt Missing evidence
        POL-->>IN: deny / needs_more_evidence
        IN->>EVT: Append LotQCRequestedMoreEvidence
        EVT->>AU: Audit requested more evidence
        EVT->>PR: Publish outbox event
        PR->>RV: Update qc_board_view (waiting_evidence)
        IN-->>FM: Yêu cầu bổ sung chứng cứ
    else Evidence complete
        POL-->>IN: allow
        IN->>QC: Open QC review
        QC->>EVT: Append LotSubmittedForQC
        EVT->>AU: Audit LotSubmittedForQC
        EVT->>PR: Publish outbox event
        PR->>RV: Update qc_board_view (qc_review)

        QC->>POL: Evaluate checklist + release guards
        alt QC fail
            POL-->>QC: fail
            QC->>EVT: Append LotFailedQC
            QC->>EVT: Append LotBlocked
            EVT->>AU: Audit LotBlocked
            EVT->>PR: Publish outbox event
            PR->>RV: Update blocked_lots_view
            QC-->>FM: Lot blocked
        else QC pass
            POL-->>QC: pass
            QC->>EVT: Append LotPassedQC
            QC->>EVT: Append LotReleased
            EVT->>AU: Audit LotReleased
            EVT->>PR: Publish outbox event
            PR->>RV: Update released_lots_view
            PR->>RV: Update available_inventory_view
            PR->>RV: Update public_traceability_view
            QC-->>FM: Lot released successfully
        end
    end
```
