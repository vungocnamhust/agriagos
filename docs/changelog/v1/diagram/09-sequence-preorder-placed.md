# Sequence Diagram — PreorderPlaced

Sơ đồ này mô tả luồng end-to-end khi khách hàng đặt trước sản phẩm.

Mục tiêu:
- tạo hoặc resolve đúng khách hàng
- ghi nhận preorder vào ERP/CRM theo đúng domain ownership
- ghi event chuẩn vào Agri OS Core
- cập nhật read models cho sales/ops/customer

```mermaid
sequenceDiagram
    autonumber
    participant C as Customer
    participant CH as Channel / Form / Sales UI
    participant IN as Agri OS Ingress
    participant ID as Identity Resolver
    participant OR as Orchestrator
    participant POL as Policy Engine
    participant ERP as ERP (Order / Preorder)
    participant CRM as CRM
    participant EVT as Event Store
    participant PR as Projection Worker
    participant RV as Read Models / Views
    participant AU as Audit Log

    C->>CH: Đặt trước sản phẩm
    CH->>IN: Submit preorder request

    IN->>ID: Resolve customer identity
    alt Customer đã tồn tại
        ID-->>IN: customer_id found
    else Customer chưa tồn tại
        ID->>CRM: Create / upsert customer profile
        CRM-->>ID: customer_id
        ID->>EVT: Append CustomerCreated
        EVT->>AU: Audit CustomerCreated
        ID-->>IN: customer_id
    end

    IN->>OR: Normalized PreorderPlaced request
    OR->>POL: Validate preorder policy
    alt Policy fail
        POL-->>OR: deny
        OR->>AU: Audit denied preorder
        OR-->>CH: Reject / explain reason
    else Policy pass
        POL-->>OR: allow
        OR->>ERP: Create preorder / sales order draft
        ERP-->>OR: preorder_id / order_id
        OR->>CRM: Append customer activity / preorder note
        CRM-->>OR: ok
        OR->>EVT: Append PreorderPlaced
        EVT->>AU: Audit PreorderPlaced
        EVT->>PR: Publish outbox event
        PR->>RV: Update customer_360_lite_view
        PR->>RV: Update preorder_board_view
        PR->>RV: Update demand_forecast_view
        OR-->>CH: Success + preorder confirmation
        CH-->>C: Xác nhận đặt trước
    end
```
