# Current API And Events

## Nói ngắn gọn

API và event hiện có là phần dễ làm người đọc hiểu nhầm nhất, vì nhiều docs kiến trúc nói cả current lẫn target cùng lúc.

File này chỉ ghi phần đang có thật trong runtime hiện tại.

## 1. API groups hiện có

- `GET /health`
- `POST /api/v1/actors`
- `GET /api/v1/actors/{actor_id}`
- `POST /api/v1/affiliations`
- organization routes dưới `/api/v1/organizations`
- project scope và sub-resource routes dưới `/api/v1/projects`
- shared resource routes dưới `/api/v1/shared-resources`
- customer routes dưới `/api/v1/customers`
- preorder routes dưới `/api/v1/preorders`
- order và allocation related routes dưới `/api/v1/orders`
- lot, evidence, QC related routes dưới `/api/v1/lots`
- farm routes dưới `/api/v1/farm`
- read model routes dưới `/api/v1/views`
- event query route dưới `/api/v1/events`
- audit query route dưới `/api/v1/audit`

## 2. Runtime event naming

Theo `app/core/events.py`:
- `eventName` dùng dotted lowercase, ví dụ `order.confirmed`
- `eventType` được derive sang PascalCase, ví dụ `OrderConfirmed`

## 3. Các event nhóm chính đã có

### Customer

- `customer.created`
- `customer.updated`
- `customer.preference_updated`
- `customer.last_purchase_updated`

### Organization

- `organization.created`
- `organization.updated`
- `organization.activated`
- `organization.paused`
- `organization.closed`

### Project scope và lane liên quan

- `project_scope.created`
- `project_scope.updated`
- `project_scope.activated`
- `project_scope.paused`
- `project_scope.closed`
- `project_scope.archived`
- `project_assignment.created`
- `project_assignment.ended`
- `project_contribution.recorded`
- `project_contribution.confirmed`
- `project_contribution.rejected`
- `project_cost_record.recorded`
- `project_revenue_record.recorded`
- `financial_allocation.recorded`

### Shared resource

- `shared_resource.created`
- `shared_resource.allocated`
- `shared_resource.released`

### Actor authority baseline

- `actor_identity.created`
- `actor_affiliation.created`

### Preorder

- `preorder.placed`
- `preorder.confirmed`
- `preorder.activated`
- `preorder.adjusted`
- `preorder.cancelled`
- `preorder.quota_consumed`
- `preorder.completed`

### Order và allocation

- `order.created`
- `order.confirmed`
- `order.allocated`
- `order.partially_allocated`
- `order.packed`
- `order.partially_packed`
- `order.shipped`
- `order.delivered`
- `order.partially_delivered`
- `order.delivery_failed`
- `order.cancel_requested`
- `order.cancelled`
- `allocation.recorded`
- `allocation.adjusted`
- `allocation.released`
- `allocation.consumed`
- `allocation.cancelled`

### Lot

- `lot.harvest.created`
- `lot.processed.created`
- `lot.adjusted`
- `lot.evidence.added`
- `lot.qc.reviewed`
- `lot.released`
- `lot.blocked`
- `lot.unblocked`
- `lot.consumed`

## 4. Event này được dùng để làm gì

- audit chain
- truy vết thay đổi
- hỗ trợ read surfaces
- phục vụ debugging và điều tra nghiệp vụ

## 5. Điều chưa nên nói quá tay

Chưa nên viết rằng runtime hiện đã có:
- outbox integration engine đầy đủ
- projection workers mặc định
- full multi-tenant event isolation

Hiện tại event append có thật, nhưng nhiều phần tiêu thụ downstream vẫn đang là Phase 1 simplified runtime.