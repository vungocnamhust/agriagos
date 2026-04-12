# Coding Guardrails — Agri OS Phase 1

Tài liệu này trả lời câu hỏi thực tế khi vibe coding:
**"Cái này có thể hardcode tạm không, hay phải đúng ngay từ đầu?"**

---

## PHẦN A — BẮT BUỘC ĐÚNG NGAY (không được shortcut)

### A1. State machine transitions phải cover toàn bộ states trong enums

`gateway.py` là nguồn sự thật cho state transitions. Mọi state trong enum phải có entry
trong state machine tương ứng — hoặc có explicit comment giải thích tại sao chưa có.

**Không được có state trong enum mà gateway không biết đến và không có comment lý giải.**

Hiện tại đã fix: `LOT_TRANSITIONS` và `PREORDER_TRANSITIONS` đã có comment cho Phase 2 states.

### A2. Event envelope structure phải stable

Một khi event đã được emit và stored, **không được đổi tên field** trong envelope.

Locked fields (từ `common.py` và `core/events.py`):
```
eventId, eventName, eventType, aggregateType, aggregateId,
occurredAt, actorType, actorId, correlationId, source, payload
```

Có thể thêm field mới (additive) như `eventVersion`, `causationId`, `idempotencyKey`.
Không được xóa hoặc rename field cũ.

### A3. Idempotency key phải check trên mọi write command

Mọi POST handler có side effect phải check idempotency trước khi execute:
```python
key = payload.meta.idempotencyKey if payload.meta else None
if cached := check_idempotency(key):
    return SomeResponse(**cached)
```
Đây là correctness concern — không phải optimization.

Nếu write command đã emit event, event đó phải lưu được `idempotencyKey` để replay/debug không cần join mù sang bảng idempotency.

Mọi write command quan trọng cũng phải ghi audit decision:
- `allowed` khi state write + event append thành công
- `denied` hoặc `failed` khi business rule hay state transition chặn flow

Audit decision phải mang ít nhất `correlation_id`, `actor_id`, `actor_role`, và metadata đủ để lần lại event hoặc command đã gây ra decision đó.

Trên PostgreSQL path, canonical state write, domain event append, audit decision append, và idempotency snapshot phải đi trong cùng một transaction boundary.

### A4. HTTP response codes phải nhất quán

| Tình huống | Code |
|-----------|------|
| Resource được tạo mới (POST /customers) | `201 Created` |
| Action thành công (POST .../confirm) | `200 OK` |
| Business rule violation / state machine reject | `422 Unprocessable Entity` |
| Resource không tồn tại | `404 Not Found` |
| Approval / permission guard đã được policy hóa | `403 Forbidden` |
| Auth chưa có (Phase 1) | Bỏ qua — không return `401` tạm |

Không dùng `400 Bad Request` cho business rule violations — dùng `422` với `code` rõ ràng.

### A5. Human-readable codes phải theo format ADR-010

Từ ngày baseline được chốt, không được ship feature mới với format cũ `CUST-{uuid[:8]}`.
Dùng `core/codegen.py` — không tự generate inline trong service.

### A6. Preorder deliveredQty chỉ có 1 code path (postgres atomic)

Chỉ dùng `store.preorders.increment_delivered_qty_atomic()` khi deliver order.
Không được update preorder record trực tiếp trong `orders.py`.

### A7. Correlation ID phải được propagate từ request boundary

Nếu client không gửi `meta.correlationId`, route layer phải lấy `X-Correlation-ID`
từ middleware và inject vào payload meta trước khi gọi service.

Không để service phải đọc trực tiếp `Request` object.

Xem: [Feature 5e trong plan](../../../.claude/plans/cheeky-finding-hinton.md)

---

## PHẦN B — CÓ THỂ HARDCODE TẠM (Phase 1 OK)

### B1. PostgreSQL là primary store

`postgres_sync.py` (và các store submodules sau khi split) là path chính thức.
`store/memory.py` chỉ dùng cho local dev không có DB hoặc unit test.

Flag `postgres_write_path_enabled` mặc định `True` trong production.

### B2. Tenant ID là nullable placeholder

`tenant_id = "default"` trong mọi record. Không filter theo tenant trong queries Phase 1.
Không cần middleware inject tenant context.

### B3. RBAC chưa enforce ở route level

Chưa cần JWT. Nhưng `actor_id` và `actor_role` phải được ghi vào events
(dùng placeholder `"system"` nếu chưa có auth).

### B4. allocationPolicy parameter

`AllocateOrderRequest.allocationPolicy` hiện chỉ accept `"manual"`.
Auto-allocation logic chưa implement. OK để giữ parameter với comment:
```python
# allocationPolicy: "manual" only in Phase 1; auto-allocation deferred to Phase 2
```

### B5. Notification/email

Không cần gửi notification thực. Stub với logging:
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Would send notification: %s to %s", event_type, actor_id)
```

---

## PHẦN C — WARNINGS (phải fix trước khi production/multi-user)

### C1. Race condition trong lot allocation (in-memory path)

Khi `postgres_write_path_enabled=False`, `allocate_order()` mutate lot trực tiếp.
Concurrent requests có thể double-allocate cùng một lot.

**Fix:** Luôn dùng postgres atomic transaction path (`allocate_order_atomic()`).

### C2. Idempotency cache không có TTL

`_idempotency_cache` trong `memory.py` tăng unbounded.

**Fix Phase 1.5:** LRU cache hoặc expire sau 24h. Sử dụng PostgreSQL-backed idempotency table.

### C3. Phone uniqueness check không atomic

`create_customer()` kiểm tra phone uniqueness trong memory trước khi insert.
Concurrent requests có thể bypass check nếu cả hai arrive trước khi insert hoàn thành.

**Fix:** Unique constraint ở database level và handle `UniqueViolation` exception.

### C4. PreorderStatus draft/confirmed không có transitions

Enum có `draft` và `confirmed` nhưng service tạo preorder thẳng với `status="active"`.
Cần implement draft → confirmed → active flow hoặc xóa bớt states không dùng.

**Quyết định:** Document gap ở đây; fix khi implement Preorder workflow đầy đủ.

---

## Enum ↔ Gateway Sync Status (Phase 1)

| Enum | States trong enum | States có transitions | States chưa có transitions | Lý do |
|------|-------------------|-----------------------|---------------------------|-------|
| `LotStatus` | draft, harvested, qc_pending, released, blocked, depleted, closed | harvested, qc_pending, released, blocked | draft, depleted, closed | Phase 1 có release/unblock lane tối thiểu; depleted/closed vẫn để Phase 2 |
| `OrderStatus` | draft, confirmed, allocated, partially_allocated, packed, partially_packed, shipped, delivered, partially_delivered, cancel_requested, cancelled, failed | draft, confirmed, allocated, partially_allocated, packed, partially_packed, cancel_requested, shipped, delivered, partially_delivered, cancelled | failed | Partial packing and partial delivery are now active in the Phase 1 fulfillment flow; `failed` remains deferred |
| `PreorderStatus` | draft, confirmed, active, completed, cancelled | active, completed, cancelled | draft, confirmed | Phase 1.5 (full preorder lifecycle chưa implement) |

---

## Checklist trước khi merge

- [ ] Mọi POST handler có side effect: check idempotency
- [ ] Mọi state change: gọi `events.emit()` trước khi return response
- [ ] Event name: dotted lowercase (xem naming-conventions.md)
- [ ] Human code mới: dùng `core/codegen.py`, không inline UUID substring
- [ ] State transition mới: cập nhật cả enum và gateway cùng lúc
- [ ] Preorder qty: chỉ update qua atomic postgres path
