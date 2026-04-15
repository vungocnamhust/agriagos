# 03. Canonical Data Model / ERD

## Mục đích
ERD này mô tả các thực thể canonical mà Agri OS Core cần giữ để liên thông các hệ.

> **Phạm vi Phase:**
> - `[Phase 1 ✅]` = entity đang được dùng trong `agos_app/app/models/` và services
> - `[Phase 2 🔜]` = đã thiết kế nhưng chưa active trong Phase 1 code
>
> **Các entity Phase 2** vẫn được giữ trong ERD để team biết trước cấu trúc, không phải remove hay re-design.

## Entity Phase Legend

| Entity | Phase | Ghi chú |
|---|---|---|
| ORGANIZATION | Phase 2 🔜 | Architecture baseline locked in PR-1; runtime rollout starts after standalone schema/API slice |
| CUSTOMER_PROFILE | Phase 1 ✅ | |
| PREORDER | Phase 1 ✅ | Bị thiếu trong ERD cũ — đã thêm |
| PRODUCT_SKU | Phase 1 ✅ | Bị thiếu trong ERD cũ — đã thêm |
| SALES_ORDER | Phase 1 ✅ | |
| SALES_ORDER_LINE | Phase 1 ✅ | |
| ALLOCATION | Phase 1 ✅ | |
| LOT_BATCH | Phase 1 ✅ | Field names đã fix theo code |
| EXTERNAL_MAPPING_RECORD | Phase 1 ✅ | Đổi tên từ CHANNEL_IDENTITY (ExternalMappingRecord trong integrations.py) |
| DOMAIN_EVENT | Phase 1 ✅ | |
| FARMER_PROFILE | Phase 1 ✅ | (read-only in Phase 1) |
| PLOT | Phase 1 ✅ | (read-only in Phase 1) |
| CROP_CYCLE | Phase 1 ✅ | (read-only in Phase 1) |
| CROP_TASK | Phase 2 🔜 | Task management chưa active |
| LOT_EVIDENCE | Phase 2 🔜 | Evidence flow chưa implement |
| QC_REVIEW | Phase 2 🔜 | QC workflow chưa implement |
| TRACEABILITY_BUNDLE | Phase 2 🔜 | Public QR traceability |
| AUDIT_LOG | Phase 2 🔜 | Sẽ replace/extend DOMAIN_EVENT |
| IDENTITY | Phase 2 🔜 | Unified identity layer — Phase 1 dùng customer_id/farmer_id trực tiếp |

## Mermaid

```mermaid
erDiagram
    %% ── Phase 1 entities ────────────────────────────────────────────────────

    %% Organization là docs-first baseline ở PR-1.
    %% Runtime chưa implement trong Phase 1 code hiện tại, nhưng rollout order đã được khóa:
    %% Organization -> Plot/CropCycle/Lot -> Preorder/SalesOrder.
    %% Customer-organization affinity, nếu cần, là read-model lane được duyệt riêng và
    %% không xuất hiện như canonical ownership edge trong ERD baseline này.

    ORGANIZATION ||--o{ PLOT : operates
    ORGANIZATION ||--o{ CROP_CYCLE : scopes
    ORGANIZATION ||--o{ LOT_BATCH : owns_flow
    ORGANIZATION ||--o{ PREORDER : sells_under
    ORGANIZATION ||--o{ SALES_ORDER : sells_under

    CUSTOMER_PROFILE ||--o{ SALES_ORDER : places
    CUSTOMER_PROFILE ||--o{ PREORDER : commits

    ORGANIZATION {
        string organization_id PK
        string organization_code
        string name
        string organization_type
        string status
        string region
        string locality_summary
    }

    PREORDER {
        string preorder_id PK
        string preorder_code
        string customer_id FK
        string product_sku_id FK
        decimal committed_qty
        decimal allocated_qty
        decimal delivered_qty
        decimal remaining_qty
        decimal cancelled_qty
        string status
        string start_date
    }

    PRODUCT_SKU {
        string sku_code PK
        string name
        string unit
        string status
    }

    PRODUCT_SKU ||--o{ LOT_BATCH : sourced_from
    PRODUCT_SKU ||--o{ SALES_ORDER_LINE : ordered_as
    PRODUCT_SKU ||--o{ PREORDER : committed_for

    FARMER_PROFILE ||--o{ PLOT : owns
    PLOT ||--o{ CROP_CYCLE : contains
    CROP_CYCLE ||--o{ LOT_BATCH : produces

    LOT_BATCH ||--o{ ALLOCATION : allocated_to
    LOT_BATCH ||--o{ LOT_EVIDENCE : has
    LOT_BATCH ||--o{ QC_REVIEW : reviewed_by
    LOT_BATCH ||--o{ TRACEABILITY_BUNDLE : published_as

    SALES_ORDER ||--|{ SALES_ORDER_LINE : contains
    SALES_ORDER_LINE ||--o{ ALLOCATION : fulfilled_by

    SALES_ORDER ||--o{ DOMAIN_EVENT : emits
    LOT_BATCH ||--o{ DOMAIN_EVENT : emits
    CUSTOMER_PROFILE ||--o{ DOMAIN_EVENT : actor_for

    CUSTOMER_PROFILE {
        string customer_id PK
        string customer_code
        string full_name
        string phone
        string status
        string channel_source
        string segment
    }

    FARMER_PROFILE {
        string farmer_id PK
        string farmer_code
        string full_name
        string phone
        string status
    }

    PLOT {
        string plot_id PK
        string farmer_id FK
        string plot_code
        string location_text
        decimal area_value
        string area_unit
        string status
    }

    CROP_CYCLE {
        string crop_cycle_id PK
        string plot_id FK
        string crop_name
        string variety
        string status
        string expected_harvest_from
        string expected_harvest_to
    }

    CROP_TASK {
        string crop_task_id PK
        string crop_cycle_id FK
        string task_type
        string status
        datetime due_at
    }

    LOT_BATCH {
        string lot_id PK
        string lot_code
        string product_sku_id FK
        string crop_cycle_id FK
        string lot_type
        string source_type
        string source_ref_id
        decimal actual_qty
        decimal released_qty
        decimal available_qty
        decimal reserved_qty
        string unit
        string harvest_or_production_date
        string status
    }

    LOT_EVIDENCE {
        string evidence_id PK
        string lot_id FK
        string evidence_type
        string object_key
        datetime captured_at
        string status
    }

    QC_REVIEW {
        string qc_review_id PK
        string lot_id FK
        string result
        string reviewer_id
        datetime reviewed_at
        string notes
    }

    SALES_ORDER {
        string order_id PK
        string order_code
        string customer_id FK
        string channel
        string status
        string payment_status
        string delivery_date_expected
        string shipping_address
    }

    SALES_ORDER_LINE {
        string order_line_id PK
        string order_id FK
        string sku_code FK
        decimal ordered_qty
        decimal allocated_qty
        decimal packed_qty
        decimal delivered_qty
        string unit
        string status
    }

    ALLOCATION {
        string allocation_id PK
        string order_line_id FK
        string lot_id FK
        decimal allocated_qty
        string status
    }

    TRACEABILITY_BUNDLE {
        string traceability_bundle_id PK
        string lot_id FK
        string public_status
        string qr_code
    }

    EXTERNAL_MAPPING_RECORD {
        string mapping_id PK
        string external_system
        string external_object_type
        string external_object_id
        string internal_object_type
        string internal_object_id
        string sync_status
        datetime last_synced_at
    }

    DOMAIN_EVENT {
        string event_id PK
        string event_name
        string event_type
        string aggregate_type
        string aggregate_id
        string actor_type
        string actor_id
        datetime occurred_at
        string correlation_id
        string source
    }

    AUDIT_LOG {
        string audit_id PK
        string actor_id FK
        string action_name
        string target_type
        string target_id
        string decision
    }

    %% ── Phase 2: IDENTITY unified layer ─────────────────────────────────────
    %% Phase 1 dùng customer_id / farmer_id trực tiếp.
    %% Phase 2 sẽ introduce unified IDENTITY → CUSTOMER_PROFILE / FARMER_PROFILE mapping.
    %% Uncommenting block below khi Phase 2 starts:
    %%
    %% IDENTITY ||--o{ CUSTOMER_PROFILE : may_map_to
    %% IDENTITY ||--o{ FARMER_PROFILE : may_map_to
    %% IDENTITY ||--o{ EXTERNAL_MAPPING_RECORD : mapped_via
    %% IDENTITY {
    %%   string identity_id PK
    %%   string identity_type
    %%   string display_name
    %%   string status
    %% }
```
