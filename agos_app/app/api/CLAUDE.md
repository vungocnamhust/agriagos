# FastAPI Backend Guide

Scope: applies to `agos_app/app/api/**` and the service layer those routes call.

## Route Conventions

- Mount public HTTP routes under `/api/v1/...` from `app/api/router.py`.
- Keep one route module per domain under `app/api/routes/`.
- Route handlers are thin adapters: parse params/body, call one service function, return a typed DTO.
- Use explicit `response_model` and status codes on every route.
- Use lifecycle verbs only for state transitions such as `/confirm`, `/allocate`, `/allocations/{allocation_id}/adjust`, `/allocations/{allocation_id}/release`, `/ship`, `/deliver`, and `/fail-delivery`.
- Do not import `store`, build events, or enforce business rules inside route handlers.

## Service-Layer Boundaries

- `app/services/*` owns orchestration, business checks, state mutations, and DTO mapping.
- Services may call `app.core.gateway`, `app.core.events`, `app.store`, and local helpers.
- Do not call peer domain service modules directly from another domain service.
- If a flow spans multiple aggregates or domains, introduce an explicit orchestration service instead of hiding cross-domain work in one domain service.
- `app/core/*` stays framework-agnostic and must not import FastAPI route modules.

## DTO vs Domain Separation

- `app/models/*` contains request and response DTOs only.
- `core/` and `store/` operate on plain primitives and records, not Pydantic DTO classes.
- Never return raw store records from routes; map them to response DTOs in services.
- Do not use third-party integration schemas as internal canonical types.
- Keep canonical field ownership aligned with the repo's domain model and event rules.

## Transaction Rules

- Treat each write service function as the transaction boundary.
- Follow this order for writes: validate request, check idempotency, load aggregate(s), assert transitions, mutate state, emit event, record idempotent result, return DTO.
- Avoid partial writes. If a mutation cannot complete, fail the command and leave canonical state unchanged.
- Keep multi-aggregate mutations centralized in one orchestration path so validation, mutation, and event emission remain atomic from the caller's perspective.
- Read handlers do not mutate state and do not open write transactions.

## Event Emission Rules

- Every successful state-changing command emits at least one past-tense domain event through `app.core.events.emit`.
- Emit events from the service layer, never from route handlers.
- Emit after the state mutation is accepted, with the canonical aggregate type, aggregate id, and business payload.
- Pass through actor and correlation metadata from `meta` whenever available.
- Do not emit business events for read-only queries, projections, or failed commands.

## Validation Strategy

- Use Pydantic models at the FastAPI boundary for shape and type validation.
- Use `app.core.gateway` for idempotency and allowed state-transition checks.
- Use services for existence checks, cross-field invariants, quantity checks, and domain-specific errors.
- Normalize external payloads at ingress boundaries before they touch canonical services.
- Prefer explicit `HTTPException` details that explain the violated rule or missing aggregate.

## Test Expectations

- Use `pytest` for route and service tests.
- For every new write flow, cover at least: success, invalid transition, missing aggregate/dependency, and idempotent replay.
- Route tests verify status codes, DTO wiring, and dependency boundaries.
- Service tests verify business rules, state transitions, idempotency, and emitted events.
- Add a regression test for every bug fix before or with the implementation.
- Swagger/UI manual checks are useful, but they do not replace automated tests.