# Naming Conventions — Agri OS v1 Baseline

Tài liệu này freeze toàn bộ quy ước đặt tên cho Phase 1.
Mọi code, doc, và event mới phải tuân thủ các quy ước dưới đây.

---

## 1. Entity Names (Aggregate Roots)

PascalCase singular. Đây là canonical label dùng trong event `aggregateType`, docs, và code.

| Canonical Name | Không dùng |
|----------------|------------|
| `CustomerProfile` | Customer, KhachHang, CustProfile |
| `SalesOrder` | Order, DonHang, Ord |
| `SalesOrderLine` | OrderLine, Line |
| `Preorder` | PreOrder, DatTruoc |
| `LotBatch` | Lot, Batch, LotBatch |
| `Allocation` | Alloc, OrderLotMapping |
| `ProductSKU` | SKU, Product, HangHoa |
| `Plot` | Farm, Garden, Vuon |
| `CropCycle` | Cycle, Season, MuaVu |
| `CropTask` | Task, NhiemVu |
| `DomainEvent` | Event, Log |

**Aggregate type label trong event envelope:** Dùng short canonical label (không phải class name đầy đủ):

| Class | aggregateType trong event |
|-------|--------------------------|
| `Organization` | `"Organization"` |
| `CustomerProfile` | `"Customer"` |
| `SalesOrder` | `"Order"` |
| `LotBatch` | `"Lot"` |
| `Preorder` | `"Preorder"` |
| `CropCycle` | `"CropCycle"` |
| `CropTask` | `"CropTask"` |
| `Plot` | `"Plot"` |

---

## 2. Event Names

Hai style — cùng semantic, khác format tùy ngữ cảnh:

| Style | Format | Dùng ở đâu | Ví dụ |
|-------|--------|------------|-------|
| **Runtime** | `dotted.lowercase` | `emit()` argument, query filter, logs | `"order.confirmed"` |
| **Class/Doc** | `PascalCase past-tense` | Docs, ADRs, diagrams, `eventType` field | `"OrderConfirmed"` |

### Conversion rule

`"order.cancel_requested"` ↔ `"OrderCancelRequested"` — split by `.` và `_`, capitalize each part.

Được tự động tính bởi `core/events.py::_to_event_type()`.

### Event catalog (Phase 1)

| Runtime name | eventType | aggregateType |
|---|---|---|
| `customer.created` | `CustomerCreated` | `Customer` |
| `customer.preference_updated` | `CustomerPreferenceUpdated` | `Customer` |
| `preorder.placed` | `PreorderPlaced` | `Preorder` |
| `preorder.adjusted` | `PreorderAdjusted` | `Preorder` |
| `lot.harvest.created` | `LotHarvestCreated` | `Lot` |
| `lot.processed.created` | `LotProcessedCreated` | `Lot` |
| `lot.adjusted` | `LotAdjusted` | `Lot` |
| `lot.evidence.added` | `LotEvidenceAdded` | `Lot` |
| `lot.qc.reviewed` | `LotQcReviewed` | `Lot` |
| `lot.released` | `LotReleased` | `Lot` |
| `lot.blocked` | `LotBlocked` | `Lot` |
| `lot.unblocked` | `LotUnblocked` | `Lot` |
| `order.created` | `OrderCreated` | `Order` |
| `order.confirmed` | `OrderConfirmed` | `Order` |
| `order.allocated` | `OrderAllocated` | `Order` |
| `order.packed` | `OrderPacked` | `Order` |
| `order.shipped` | `OrderShipped` | `Order` |
| `order.delivered` | `OrderDelivered` | `Order` |
| `order.cancel_requested` | `OrderCancelRequested` | `Order` |
| `order.cancelled` | `OrderCancelled` | `Order` |

---

## 3. State Enum Values

`snake_case` lowercase. Không dùng camelCase hay UPPER_SNAKE.

```python
# Đúng
class OrderStatus(str, Enum):
    draft = "draft"
    cancel_requested = "cancel_requested"

# Sai
class OrderStatus(str, Enum):
    Draft = "Draft"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    cancelRequested = "cancelRequested"
```

---

## 4. HTTP Endpoint Paths

`kebab-case`. Tất cả paths trong `/api/v1/` phải dùng kebab-case.

```
# Đúng
/api/v1/orders/{order_id}/request-cancel
/api/v1/farm/crop-cycles
/api/v1/views/customer-360/{customer_id}

# Sai
/api/v1/orders/{order_id}/requestCancel
/api/v1/farm/cropCycles
/api/v1/views/customer360/{customer_id}
```

Path params dùng `snake_case` (`{order_id}`, `{customer_id}`, `{lot_id}`).

---

## 5. DTO Names (Pydantic Models)

`PascalCase` với explicit role suffix.

| Pattern | Ví dụ |
|---------|-------|
| `Create{Entity}Request` | `CreateOrderRequest`, `CreateCustomerRequest` |
| `{Entity}Response` | `OrderResponse`, `LotResponse` |
| `{Action}{Entity}Request` | `AllocateOrderRequest`, `ReleaseLotRequest` |
| `{Entity}Detail` | `OrderDetail`, `LotDetail` |
| `{Entity}Summary` | `CustomerSummary`, `PlotSummary` |

Không dùng: `Data`, `Payload`, `Item`, `Object`, `Record` làm suffix chung.

---

## 6. File/Module Names

`snake_case`. Các files trong `services/`, `models/`, `store/`, `core/`, `api/routes/`.

```
services/orders.py      ✅
services/OrderService.py ❌
models/sales_order.py   ✅ (hoặc orders.py theo domain)
models/SalesOrder.py    ❌
```

---

## 7. Command Names

`PascalCase` imperative verb phrase. Dùng trong docs, ADRs, và future command objects.

```
CreateOrder, ConfirmOrder, AllocateOrderLine
ReleaseLot, BlockLot, UnblockLot
RegisterCustomer, MergeCustomer
PlanCropCycle, CompleteCropTask
```

---

## 8. Bounded Context / Module Names

Lowercase, no abbreviations, no generic words.

```
identity, farm_core, crop_task, lot_traceability
qc_workflow, order_ops, policy_workflow
eventing_audit, projections
```

Không dùng: `core`, `common`, `utils`, `helpers` ở domain level.

---

## 9. Human-Readable ID Codes

Xem [ADR-010](../adrs/ADR-010-id-strategy.md) và `core/codegen.py`.

| Entity | Format | Ví dụ |
|--------|--------|-------|
| Organization | `ORG-YYYYMM-NNNN` | `ORG-202604-0001` |
| Customer | `KH-YYYYMM-NNNN` | `KH-202604-0001` |
| Preorder | `DT-YYYYMM-NNNN` | `DT-202604-0001` |
| Order | `ORD-YYYYMM-NNNN` | `ORD-202604-0001` |
| Lot | `LOT-{SKU}-YYYYMM-NNN` | `LOT-DAU-202604-001` |
| Plot | `VU-NNN` | `VU-001` |
| CropCycle | `VU-NNN-YYYY{A\|B}` | `VU-001-2026A` |

---

## Checklist khi thêm event mới

- [ ] `event_name` argument trong `emit()` phải là dotted.lowercase
- [ ] `aggregateType` phải dùng short canonical label (xem bảng Section 1)
- [ ] `eventType` sẽ tự động được derive — không cần pass manually
- [ ] Thêm vào event catalog ở Section 2 của doc này
