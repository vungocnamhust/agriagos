---
path: agos_app/app/**
---

# Domain Boundary Rules

These rules apply to all code under `agos_app/app/`. They enforce the layered
architecture defined in `system_v1.md` and `determistic_layer_spec_v1.md`.

## Layer Map

```
api/routes/      ← HTTP boundary: parse request, call service, return response
services/        ← Application services: orchestrate domain logic, emit events
core/            ← Domain primitives: gateway, event factory, state machines
models/          ← Pydantic DTOs: schemas shared within this app only
store/           ← Infrastructure: in-memory or DB-backed persistence
```

---

## Rule 1 — No Direct Cross-Domain Imports

Each domain (`orders`, `lots`, `farm`, `customers`, `preorders`) is a bounded
context. A service in one domain must **not** import directly from another
domain's service module.

**Violation:**
```python
# services/orders.py
from app.services.lots import release_lot  # ❌ direct cross-domain service call
```

**Correct — coordinate through an application service or emit an event:**
```python
# services/orders.py
from app.core import events

events.emit("order.allocated", "Order", order_id, {"lotId": lot_id})  # ✅
```

If synchronous cross-domain coordination is unavoidable in Phase 1, introduce
an explicit orchestration function in `services/` that owns the saga, and name
it clearly (e.g., `services/allocation.py`). Never bury cross-domain calls
inside a single-domain service file.

---

## Rule 2 — No Business Logic in Controllers

Files under `api/routes/` are HTTP adapters only. They must not contain:

- Conditional branching on domain state
- Direct calls to `store/`
- Domain event construction or emission
- State machine lookups

**Violation:**
```python
# api/routes/orders.py
@router.post("/{order_id}/confirm")
def confirm_order(order_id: str):
    record = store.get_order(order_id)      # ❌ bypasses service layer
    if record["status"] != "pending":       # ❌ domain rule in controller
        raise HTTPException(400, "...")
    record["status"] = "confirmed"          # ❌ mutation without event
    store.update_order(order_id, record)
    return record
```

**Correct:**
```python
# api/routes/orders.py
@router.post("/{order_id}/confirm", response_model=OrderResponse)
def confirm_order(order_id: str) -> OrderResponse:
    return svc.confirm_order(order_id)      # ✅ delegate entirely to service
```

A controller function body should contain at most:
1. Request parsing / path param extraction
2. One service call
3. Response return

---

## Rule 3 — No External App Schemas Inside Core Domain

`core/` and `store/` must not import from `models/` (Pydantic DTOs). These
layers deal in plain `dict[str, Any]`. DTOs belong to the application surface
(routes + services); the domain kernel stays schema-independent.

**Violation:**
```python
# core/gateway.py
from app.models.orders import CreateOrderRequest  # ❌ DTO leaking into core
```

**Correct:**
```python
# core/gateway.py
def check_idempotency(idempotency_key: str) -> bool:  # ✅ plain primitives only
    ...
```

`models/integrations.py` schemas are for third-party wire formats only. They
must never be used inside `core/` or `services/` as canonical domain types —
map them at the ingress boundary (a dedicated normalizer or the route handler).

---

## Rule 4 — Every Cross-Domain Interaction via Service or Event

Any action that causes a state change in more than one domain aggregate must
flow through one of two paths:

### Path A — Application service orchestration (synchronous saga)
```python
# services/allocation.py  ← owns the saga
def allocate_order_to_lot(order_id: str, lot_id: str, qty: float) -> None:
    gateway.assert_order_transition(order_id, "allocate")
    gateway.assert_lot_transition(lot_id, "reserve")
    # ... update both, then emit events for each aggregate
    events.emit("order.allocated", "Order", order_id, {...})
    events.emit("lot.reserved",    "Lot",   lot_id,   {...})
```

### Path B — Event-driven (asynchronous, preferred for loose coupling)
```python
# services/orders.py
events.emit("order.confirmed", "Order", order_id, payload)
# A separate projection worker or listener reacts to this event
# and updates the Lot or Customer read model independently.
```

Direct in-process calls from `services/orders.py` into `services/lots.py` (or
any other peer service) are **prohibited**.

---

## Rule 5 — Import Direction (strictly top-down)

```
api/routes  →  services  →  core  →  store
                         ↘  models
```

- `api/routes` may import from `services` and `models`
- `services` may import from `core`, `models`, and `store`
- `core` may import from `store` only — never from `services` or `api`
- `store` imports nothing from this app
- `models` imports nothing from `services`, `core`, or `store`

Any import that points upward in this chain is a layering violation.

---

## Checklist Before Committing

- [ ] No `services/foo.py` imports from `services/bar.py` directly
- [ ] No domain logic (conditionals on status, state machine lookups) in `api/routes/`
- [ ] No Pydantic model imports inside `core/` or `store/`
- [ ] No `models/integrations.py` types used as internal domain types
- [ ] Cross-domain changes produce events via `core.events.emit()`
- [ ] Import direction flows strictly top-down through the layer map
