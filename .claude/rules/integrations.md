---
paths:
  - "agos_app/app/models/integrations.py"
  - "integrations/**"
---

# Integration Rules

These rules apply whenever Agri OS reads from or writes to an external system.
In the current Phase 1 repo, the active integration surface is primarily
`agos_app/app/models/integrations.py`; future adapters may live under
`integrations/`.

The goal is to keep vendor-specific schemas out of the deterministic core.

## Rule 1 - Translate at the Boundary

Never pass external payloads directly into `services/`, `core/`, or `store/`.

- Parse vendor payloads in a dedicated translator or adapter.
- Validate required fields and domain invariants before mapping into internal DTOs.
- Convert external naming and enum styles into Agri OS canonical names before any
  service call.

**Do this in this repo:**
- Keep wire-format schemas in [agos_app/app/models/integrations.py](/Users/nam/Workspace/projects/running/agriagos/agos_app/app/models/integrations.py).
- Map them to domain requests or plain dictionaries before calling services.

**Do not do this:**
```python
# Bad: service receives vendor payload shape directly
svc.create_order(payload_from_erp)
```

**Do this instead:**
```python
# Good: boundary maps vendor payload into internal request shape first
order_request = map_erp_order_to_create_order_request(payload_from_erp)
svc.create_order(order_request)
```

## Rule 2 - Isolate External IDs

External IDs are never canonical IDs inside Agri OS.

- Do not use vendor IDs as primary keys for core entities.
- Resolve external IDs to internal IDs at the adapter boundary.
- Store cross-system identity in explicit mapping records, consistent with
  `ExternalMappingRecord`.

For this repo, the canonical pattern is already represented in
[agos_app/app/models/integrations.py](/Users/nam/Workspace/projects/running/agriagos/agos_app/app/models/integrations.py) via `ExternalMappingRecord`.

## Rule 3 - Keep Dependency Direction One-Way

Integration code may depend on app DTOs and services. Core business code must not
depend on integration adapters.

- `integrations/**` may import `app.models`, `app.services`, and boundary helpers.
- `app.core` and `app.store` must not import from integration modules.
- Do not add vendor conditionals inside domain services.

If vendor-specific behavior is needed, branch in the adapter and keep the service
API vendor-neutral.

## Rule 4 - Treat Remote Calls as Unreliable

Every external call must assume timeouts, retries, duplicates, and partial failure.

- Make inbound webhook handling idempotent.
- Make outbound write operations replay-safe.
- Retry only transient failures such as `429`, `502`, and `503`.
- Use jittered exponential backoff when retrying.
- Fail with explicit state or logging; do not silently swallow remote errors.

Because this repo is still Phase 1 and has no queue or circuit-breaker
infrastructure yet, do not invent hidden background retry loops inside route
handlers. If retry or async delivery is required, document the missing runtime
dependency and keep the initial implementation explicit and bounded.

## Rule 5 - Preserve Core Ownership

An integration may mirror or sync core data, but it must not redefine ownership.

- `CustomerProfile`, `Preorder`, `ProductSKU`, `LotBatch`, `SalesOrder`, and other
  canonical entities remain owned by Agri OS rules and docs.
- External schemas are translation inputs or outputs, not alternate truth.
- If a vendor model conflicts with the canonical model, the translator absorbs the
  mismatch.

## Checklist Before Closing Integration Work

- [ ] Vendor payloads are translated before entering `services/`
- [ ] External IDs are isolated from canonical IDs
- [ ] No integration module is imported by `app.core` or `app.store`
- [ ] Retry behavior is explicit and idempotent
- [ ] New integration fields align with `ExternalMappingRecord` or another explicit mapping type
