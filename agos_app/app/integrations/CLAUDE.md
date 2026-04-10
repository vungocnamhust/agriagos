# Integration Adapter Guide

Scope: applies to `agos_app/app/integrations/**` and any translator code that moves data between Agri OS and external systems.

## Adapter-First Boundary

- Treat every integration module as an adapter around an external system, not as an extension of the core domain.
- Parse vendor payloads at the edge, then translate them before calling `app.services/*`.
- Never pass external request or response models directly into `services/`, `core/`, or `store/`.
- Keep vendor-specific field names, enums, and transport details inside the adapter.

## Anti-Corruption Layer

- Every inbound or outbound integration flow must map through an explicit anti-corruption layer.
- Keep wire-format schemas in `app.models.integrations` or adapter-local translator code.
- Translate vendor terms into Agri OS canonical names before invoking a service or returning core data to a remote system.
- If an external model cannot represent the canonical model exactly, absorb the mismatch in the translator rather than weakening the core DTOs.

## External Schema Isolation

- Do not import vendor SDK types or external payload schemas into `app.core`, `app.store`, or canonical domain DTO modules.
- Do not add vendor conditionals inside domain services.
- If two systems need different mappings for the same business action, branch in the adapter and keep the service API vendor-neutral.

## External ID Handling

- External IDs are integration references only; they are never canonical Agri OS IDs.
- Resolve external identifiers to internal aggregate IDs at the adapter boundary.
- Persist cross-system identity through explicit mapping records such as `ExternalMappingRecord`.
- Do not overload `customer_id`, `order_id`, `lot_id`, or other canonical identifiers with vendor IDs.

## Sync Logging And Auditability

- Log every sync attempt and every sync result, including inbound pulls, outbound pushes, retries, failures, and idempotent replays.
- Record enough context to reconstruct what happened: external system, object type, external ID, internal ID when known, operation, status, timestamp, and correlation or idempotency key.
- Do not silently swallow remote errors or dropped payloads.
- When a sync mutates canonical state, ensure the adapter preserves the link between the remote operation and the resulting domain event trail.

## Retry And Idempotency

- Document retry behavior per adapter: which operations may retry, which statuses are considered transient, and which errors fail fast.
- Prefer bounded retries with jittered exponential backoff for transient failures such as `429`, `502`, and `503`.
- Make inbound webhook and polling handlers idempotent before they call canonical services.
- Make outbound writes replay-safe by using stable idempotency keys or deduplication records where the remote API supports them.
- If an operation is not safely retryable, say so explicitly in adapter docs and code comments near the boundary.
- Do not hide background retry loops inside route handlers or core services.

## Dependency Direction

- `app/integrations/**` may depend on `app.models`, `app.services`, and boundary helpers.
- `app.core` and `app.store` must not depend on integration adapters.
- Keep dependency flow one-way: external system -> adapter -> canonical service -> core/store.

## Checklist Before Closing Integration Work

- [ ] External schemas stay outside canonical domain modules
- [ ] Translator or anti-corruption layer exists for each inbound and outbound flow
- [ ] External IDs are isolated through explicit mapping records
- [ ] Sync attempts and outcomes are logged with enough audit context
- [ ] Retry policy and idempotency behavior are documented and explicit