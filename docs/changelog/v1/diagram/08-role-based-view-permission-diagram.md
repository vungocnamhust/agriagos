# 08. Role-based View / Permission Diagram

## Mục đích
Sơ đồ này thể hiện nguyên tắc **one truth, many views**: cùng một dữ liệu gốc, mỗi role nhìn khác nhau và được thực hiện command khác nhau.

> **Phase 1 API endpoints** (thực tế trong `agos_app/app/api/routes/views.py`):
>
> | Endpoint | Conceptual View |
> |---|---|
> | `GET /views/customer-360/{id}` | Customer 360 Lite View (V4) |
> | `GET /views/available-lots` | Available Lot Board — released lots chưa được allocate hết |
> | `GET /views/pending-fulfillment` | Order Board View (V3) — confirmed/allocated/packed orders |
> | `GET /views/farm` | Farm View — plots + active crop cycles |
>
> Các view còn lại (Farmer Task View, QC Board, Traceability, Management Metrics) là Phase 2.

## Mermaid
```mermaid
flowchart LR
    subgraph Roles["Roles"]
        Admin["Admin"]
        OpsLead["Ops Lead"]
        FarmMgr["Farm Manager"]
        QC["QC Reviewer"]
        Sales["Sales / CSKH"]
        Farmer["Farmer User"]
        Customer["Customer"]
    end

    subgraph Canonical["Canonical Core"]
        C1["Identity + Customer + Farmer"]
        C2["Crop Cycle + Crop Task"]
        C3["Lot + Evidence + QC Review"]
        C4["Order + Allocation + Inventory View"]
        C5["Event Log + Audit"]
    end

    subgraph Views["Read Models / Views"]
        V1["Farmer Task View"]
        V2["QC Board View"]
        V3["Order Board View"]
        V4["Customer 360 Lite View"]
        V5["Traceability Public View"]
        V6["Management Metrics View"]
    end

    subgraph Commands["Allowed Commands"]
        CMD1["CropTask Commands"]
        CMD2["Lot Evidence / QC Commands"]
        CMD3["Order Commands"]
        CMD4["Customer / Tag / Follow-up Commands"]
        CMD5["Admin / Override Commands"]
    end

    C1 --> V4
    C2 --> V1
    C3 --> V2
    C4 --> V3
    C3 --> V5
    C1 --> V6
    C2 --> V6
    C3 --> V6
    C4 --> V6
    C5 --> V6

    Farmer --> V1
    Farmer --> CMD1

    QC --> V2
    QC --> CMD2

    Sales --> V3
    Sales --> V4
    Sales --> CMD3
    Sales --> CMD4

    FarmMgr --> V1
    FarmMgr --> V2
    FarmMgr --> CMD1
    FarmMgr --> CMD2

    OpsLead --> V2
    OpsLead --> V3
    OpsLead --> V6
    OpsLead --> CMD3
    OpsLead --> CMD5

    Admin --> V1
    Admin --> V2
    Admin --> V3
    Admin --> V4
    Admin --> V6
    Admin --> CMD5

    Customer --> V5
```
