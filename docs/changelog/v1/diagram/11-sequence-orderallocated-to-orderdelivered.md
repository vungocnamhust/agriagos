# Sequence Diagram — OrderAllocated to OrderDelivered

Sơ đồ này mô tả luồng end-to-end từ lúc đơn đã sẵn sàng allocate lô đến lúc giao hàng thành công.

Mục tiêu:
- chỉ allocate từ lot đã released
- reserve đúng số lượng
- đóng gói, giao hàng, cập nhật delivery
- nuôi read models cho sales/ops/customer

```mermaid
sequenceDiagram
    autonumber
    participant SO as Sales Ops / Admin UI
    participant IN as Agri OS Ingress
    participant OO as Order Ops Service
    participant POL as Policy Engine
    participant ERP as ERP (Order / Inventory)
    participant SH as Shipping / Delivery Adapter
    participant EVT as Event Store
    participant PR as Projection Worker
    participant RV as Read Models / Views
    participant AU as Audit Log

    SO->>IN: AllocateOrderLine(order_id, lot_id, qty)
    IN->>POL: Check allocation guards
    alt Lot not released or qty insufficient
        POL-->>IN: deny
        IN->>AU: Audit allocation denied
        IN-->>SO: Reject allocation
    else Allocation valid
        POL-->>IN: allow
        IN->>ERP: Reserve released lot quantity
        ERP-->>IN: allocation_id
        IN->>OO: Persist allocation linkage
        OO->>EVT: Append OrderAllocated
        EVT->>AU: Audit OrderAllocated
        EVT->>PR: Publish outbox event
        PR->>RV: Update order_board_view
        PR->>RV: Update allocation_view
        PR->>RV: Update customer_order_trace_view
        IN-->>SO: Allocation success
    end

    SO->>IN: PackOrder(order_id)
    IN->>POL: Check all lines allocated
    alt Not all lines allocated
        POL-->>IN: deny
        IN->>AU: Audit pack denied
        IN-->>SO: Reject pack
    else Ready to pack
        POL-->>IN: allow
        IN->>ERP: Mark packed
        ERP-->>IN: packed_at
        IN->>EVT: Append OrderPacked
        EVT->>AU: Audit OrderPacked
        EVT->>PR: Publish outbox event
        PR->>RV: Update order_board_view
        PR->>RV: Update packing_queue_view
        IN-->>SO: Packed successfully
    end

    SO->>IN: ShipOrder(order_id)
    IN->>POL: Check packed + shipping data valid
    alt Shipping invalid
        POL-->>IN: deny
        IN->>AU: Audit ship denied
        IN-->>SO: Reject ship
    else Ready to ship
        POL-->>IN: allow
        IN->>SH: Create shipment / handoff carrier
        SH-->>IN: shipment_ref
        IN->>ERP: Mark shipped
        ERP-->>IN: shipped_at
        IN->>EVT: Append OrderShipped
        EVT->>AU: Audit OrderShipped
        EVT->>PR: Publish outbox event
        PR->>RV: Update shipment_view
        PR->>RV: Update order_board_view
        PR->>RV: Update customer_order_trace_view
        IN-->>SO: Shipment created
    end

    SH->>IN: Delivery confirmed webhook
    IN->>OO: Resolve shipment -> order
    OO-->>IN: order_id
    IN->>ERP: Mark delivered
    ERP-->>IN: delivered_at
    IN->>EVT: Append OrderDelivered
    EVT->>AU: Audit OrderDelivered
    EVT->>PR: Publish outbox event
    PR->>RV: Update order_board_view
    PR->>RV: Update customer_order_trace_view
    PR->>RV: Update customer_360_lite_view
    IN-->>SO: Delivery status updated
```
