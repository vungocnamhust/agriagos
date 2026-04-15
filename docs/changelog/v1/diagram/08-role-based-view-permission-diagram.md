# 08. Role-based View / Permission Diagram

## Mục đích
Sơ đồ này thể hiện nguyên tắc **one truth, many views**: cùng một dữ liệu gốc, mỗi role nhìn khác nhau và được thực hiện command khác nhau.

> **Phase 1 API endpoints** (role-facing read surfaces + debug readback):
>
> | Endpoint | Conceptual View |
> |---|---|
> | `GET /api/v1/views/customer-360/{customer_id}` | Customer 360 Lite View |
> | `GET /api/v1/views/available-lots` | Available Lot Board — released lots chưa được allocate hết |
> | `GET /api/v1/views/pending-fulfillment` | Pending Fulfillment Board |
> | `GET /api/v1/views/farm` | Farm View — plots + active crop cycles |
> | `GET /api/v1/views/farm-summary-board` | Farm Summary Board |
> | `GET /api/v1/events` | Scoped Event Stream — short-term read lane cho operator / analyst use cases |
> | `GET /api/v1/audit` | Audit Query Surface — operator/debug readback, không phải role-facing business view |
>
> Các view còn lại (Farmer Task View, QC Board, Traceability, Management Metrics) là Phase 2.
>
> `GET /api/v1/events` là short-term scoped read lane; role enforcement chi tiết vẫn là phần rollout PR sau.
>
> `GET /api/v1/audit` là read-only query surface cho operator/debug ở Phase 1; current enforced readers là Founder / Super Admin, Admin, và Accountant. Các role khác bị deny và ghi audit `audit.query`.
>
> Raw customer reads ở Phase 1 cũng đi lane hẹp: `GET /api/v1/customers`, `GET /api/v1/customers/{customer_id}`, `GET /api/v1/customers/duplicate-candidates`, và `GET /api/v1/customers/{customer_id}/duplicate-candidates` hiện chỉ cho Founder / Super Admin / Admin / Sales / CSKH. Ops, Accountant, Viewer, và raw agent reads phải dùng customer-facing view/tool surface khác hoặc bị deny trên raw lane.
>
> Raw lot reads ở Phase 1 không mở rộng như read models: `GET /api/v1/lots/{lot_id}`, `GET /api/v1/lots/{lot_id}/evidence`, và `GET /api/v1/lots/{lot_id}/qc-reviews` hiện chỉ cho Founder / Super Admin / Admin / Ops / Farm Manager / QC Reviewer. Lot create, adjust, release, block, unblock dùng service-layer write authz; evidence add và QC review giữ lane riêng cho QC.
>
> Standalone Organization CRUD đã có ở Phase 1 runtime qua `/api/v1/organizations`. Founder / Super Admin và Admin là nhóm mutate/read raw chính; customer vẫn là shared ecosystem identity chứ không thành owned view của từng organization.

## Mermaid
```mermaid
flowchart LR
    subgraph Roles["Roles"]
        Founder["Founder / Super Admin"]
        Admin["Admin"]
        Ops["Ops / Kho / Dong goi"]
        FarmMgr["Farm Manager"]
        QC["QC Reviewer"]
        Sales["Sales"]
        CSKH["CSKH"]
        Accountant["Accountant"]
        Viewer["Viewer / Analyst"]
        Agent["Agent / Automation"]
    end

    subgraph Canonical["Canonical Core"]
        C1["Identity + Customer"]
        C2["Plot + Crop Cycle Summary"]
        C3["Lot + Evidence + QC Review"]
        C4["Order + Allocation + Inventory"]
        C5["Event Log + Audit"]
    end

    subgraph Views["Read Models / Views"]
        V0["Organization Profile View [Phase 1 ✅]"]
        V1["Customer 360 Lite View"]
        V2["Available Lots Board"]
        V3["Pending Fulfillment Board"]
        V4["Farm View / Farm Summary Board"]
        V5["Scoped Event Stream"]
        V6["Audit Query Surface"]
        V7["Project Scope Directory [Phase 2 🔜]"]
        V8["Project Economics / Contribution Views [Phase 2 🔜]"]
    end

    subgraph Commands["Allowed Commands"]
        CMD0["Organization Management Commands [Phase 1 ✅]"]
        CMD1["Farm Summary / Harvest Commands"]
        CMD2["Lot Evidence / QC Commands"]
        CMD3["Order Commands"]
        CMD4["Customer / Preference / Follow-up Commands"]
        CMD5["Admin / Override Commands"]
        CMD6["Project Scope Management Commands [Phase 2 🔜]"]
        CMD7["Project Assignment / Contribution / Economics Commands [Phase 2 🔜]"]
    end

    C1 --> V1
    C3 --> V2
    C4 --> V3
    C2 --> V4
    C5 --> V5
    C5 --> V6
    C5 --> V7
    C5 --> V8

    Founder --> V1
    Founder --> V0
    Founder --> V2
    Founder --> V3
    Founder --> V4
    Founder --> V5
    Founder --> V6
    Founder --> V7
    Founder --> V8
    Founder --> CMD0
    Founder --> CMD5
    Founder --> CMD6
    Founder --> CMD7

    QC --> V2
    QC --> CMD2

    Sales --> V1
    Sales --> V3
    Sales --> CMD4

    CSKH --> V1
    CSKH --> V3
    CSKH --> CMD4

    FarmMgr --> V2
    FarmMgr --> V4
    FarmMgr --> CMD1
    FarmMgr --> CMD2

    Ops --> V2
    Ops --> V3
    Ops --> V4
    Ops --> CMD2
    Ops --> CMD3

    Admin --> V2
    Admin --> V3
    Admin --> V0
    Admin --> V1
    Admin --> V4
    Admin --> V5
    Admin --> V6
    Admin --> V7
    Admin --> V8
    Admin --> CMD0
    Admin --> CMD5
    Admin --> CMD6
    Admin --> CMD7

    Accountant --> V3
    Accountant --> V5
    Accountant --> V6
    Accountant --> V8

    Viewer --> V2
    Viewer --> V3
    Viewer --> V4
    Viewer --> V5
    Viewer --> V8

    Agent -.-> V1
    Agent -.-> V2
    Agent -.-> V3
    Agent -.-> V4
    Agent -.-> V5
    Agent -.-> V7
    Agent -.-> CMD3
    Agent -.-> CMD4
    Agent -.-> CMD7
```

## Phase 1 notes

- `qc_reviewer` là top-level business role riêng cho QC lane, không phải delegated capability của `ops` hay `farm_manager`.
- `viewer / analyst` short-term đi qua `/api/v1/views/*` và scoped `/api/v1/events`; không dùng raw operational reads theo mặc định.
- `agent / automation` vẫn advisory-first. Sơ đồ cho thấy nó có thể đọc hoặc tạo draft trong scope được cấp, nhưng không có bypass lane nào đang enable ở Phase 1.
- `Organization Profile View [Phase 1 ✅]` và `Organization Management Commands [Phase 1 ✅]` hiện tương ứng với standalone `/api/v1/organizations` read/write lane. Association sang farm-side, commercial-side, và org-scoped RBAC vẫn là phase sau.
- `Project Scope Directory [Phase 2 🔜]`, `Project Economics / Contribution Views [Phase 2 🔜]`, và các command nodes liên quan chỉ là docs-first baseline cho epic ProjectScope. Chúng chưa khẳng định runtime route hoặc authz đã tồn tại ở Phase 1.
