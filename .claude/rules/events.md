# Event Rules

These rules govern event naming, payload shape, and where events are emitted in
Agri OS.

They must match the current Phase 1 implementation in
[agos_app/app/core/events.py](/Users/nam/Workspace/projects/running/agriagos/agos_app/app/core/events.py): a local domain-event factory backed by the in-memory store. Do not write rules or code that assume Kafka, RabbitMQ, or an outbox already exists unless you are adding that infrastructure explicitly.

## Rule 1 - Events Describe Facts, Not Intent

An event names something that already happened.

- Use past-tense names.
- Do not use command names as event names.
- Prefer dotted, lowercase names in runtime payloads to match the current
  `emit()` API.

**Good runtime names:**
- `order.created`
- `order.confirmed`
- `lot.released`
- `customer.registered`

**Bad runtime names:**
- `create_order`
- `confirmOrder`
- `order.confirm`

If you need a prose or class-style label in docs, keep it semantically aligned:
`OrderCreated`, `OrderConfirmed`, `LotReleased`.

## Rule 2 - Emit from Services or Orchestrators Only

Routes receive HTTP requests. Services decide business state changes. Events are
emitted only at the layer that owns the state transition.

- `api/routes/` must not construct domain events directly.
- `services/` or a dedicated orchestration module may call `app.core.events.emit()`.
- `store/` must not invent events after a write.

This is consistent with the current route pattern in
[agos_app/app/api/routes/orders.py](/Users/nam/Workspace/projects/running/agriagos/agos_app/app/api/routes/orders.py), where routes delegate to services.

## Rule 3 - Payloads Stay Small and Stable

Event payloads should be easy to append, inspect, and project.

- Include IDs, status changes, timestamps, and the minimum business facts needed
  downstream.
- Do not embed entire Pydantic models or vendor payloads.
- Prefer primitives and flat objects over nested structures when possible.
- Preserve backward compatibility for any payload already consumed elsewhere.

The current `emit()` function stores camelCase envelope keys such as `eventId`,
`eventName`, `aggregateType`, `aggregateId`, and `payload`. New event-writing code
must preserve that envelope unless the event store contract is intentionally changed.

## Rule 4 - Distinguish Current Domain Events from Future Integration Events

In this repo today, only internal domain events are implemented directly.

### Current Phase 1 behavior
- Use `app.core.events.emit()` to append a domain event to the in-memory store.
- Treat the appended event as the write-side audit fact for projections and reads.

### Future behavior
- Integration events may later be published to external systems.
- When that happens, publish them from an explicit adapter or outbox-style layer,
  not directly from route handlers.

Until that infrastructure exists, do not add pseudo-broker code, queue jargon, or
fake publish calls that no runtime component consumes.

## Rule 5 - Make Event Handling Idempotent

Even in Phase 1, duplicate execution is possible through retries or repeated API
calls.

- Before emitting, check whether the state transition is still valid.
- Consumers or projections must tolerate duplicate events.
- Reprocessing the same event should not create a second business effect.

Examples:
- If an order is already `confirmed`, do not emit a second `order.confirmed` as if
  it were a new transition.
- If a lot is already `released`, do not decrement or re-release inventory again.

## Rule 6 - Tie Events to Canonical Aggregates

Every emitted event must clearly identify the aggregate that changed.

- Use the canonical aggregate names already present in the repo and docs:
  `CustomerProfile`, `Preorder`, `ProductSKU`, `LotBatch`, `SalesOrder`,
  `CropCycle`, `CropTask`, `Plot`, `Farmer`.
- Do not emit vague aggregate labels such as `Data`, `Record`, or `Item`.
- If the runtime envelope uses a shorter aggregate label such as `Order` or `Lot`,
  keep it consistent across all events for that aggregate.

## Checklist Before Closing Event Work

- [ ] Event name is past tense and matches the current dotted runtime style
- [ ] Event is emitted from a service or orchestration layer, not a route
- [ ] Payload contains only stable, necessary facts
- [ ] Envelope stays compatible with `app.core.events.emit()`
- [ ] Event handling remains idempotent
