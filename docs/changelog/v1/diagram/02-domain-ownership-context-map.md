# 02. Domain Ownership / Context Map

## Mục đích
Sơ đồ này chốt rõ hệ nào là **source of truth** cho từng domain và Agri OS Core giữ phần liên thông nào.

> **Phân biệt Phase:**
> - Sơ đồ này mô tả **kiến trúc integration target** (khi LiteFarm, ERP, CRM đã kết nối).
> - **Phase 1 thực tế:** Agri OS Core quản lý trực tiếp CustomerProfile, Preorder, SalesOrder, Plot, CropCycle — không phụ thuộc vào ERP/CRM/LiteFarm làm source of truth.
> - Khi integration được activate (Phase 2+), ownership mới shift về đúng hệ sở hữu như diagram mô tả.
> - ADR-009: Core luôn giữ plot/crop **summary**; LiteFarm giữ deep field data (chi tiết canh tác, sensory data).

## Mermaid
```mermaid
flowchart LR
    subgraph LiteFarmCtx["LiteFarm Context"]
        LF1["Plot"]
        LF2["Crop Cycle"]
        LF3["Field Task / Growth Stage"]
        LF4["Basic Farm Facts"]
    end

    subgraph ERPCtx["ERP Context"]
        ERP1["Product / SKU"]
        ERP2["Sales Order / Preorder"]
        ERP3["Inventory / Stock Movement"]
        ERP4["Invoice / Payment Facts"]
    end

    subgraph CRMCtx["CRM Context"]
        CRM1["Customer Profile"]
        CRM2["Segments / Tags"]
        CRM3["Lifecycle / Interaction"]
        CRM4["Campaign / Follow-up Facts"]
    end

    subgraph CoreCtx["Agri OS Core Context"]
        C1["Identity Map / Unified IDs"]
        C2["Cross-domain Event Log"]
        C3["Policy / Workflow Rules"]
        C4["Role-based Read Models"]
        C5["Permissions / Audit"]
        C6["Traceability Bundle / Released Lot View"]
    end

    LF1 --> C1
    LF2 --> C2
    LF3 --> C2
    LF4 --> C4

    ERP1 --> C4
    ERP2 --> C2
    ERP3 --> C2
    ERP4 --> C5

    CRM1 --> C1
    CRM2 --> C4
    CRM3 --> C2
    CRM4 --> C4

    C1 --> C4
    C2 --> C4
    C3 --> C4
    C5 --> C4
    C6 --> C4

    note1["Ownership Rules\n- LiteFarm owns farm truth\n- ERP owns transaction truth\n- CRM owns customer interaction truth\n- Agri OS Core owns cross-domain truth"]
    C3 --- note1
```
