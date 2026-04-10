# API Contract-First Rules

These rules apply to HTTP APIs and DTOs in the current Agri OS FastAPI app.

The repo already exposes route groups under `/api/v1/*` in
[agos_app/app/api/router.py](/Users/nam/Workspace/projects/running/agriagos/agos_app/app/api/router.py). The contract must stay ahead of implementation, but the rule also needs to reflect current reality: the checked-in OpenAPI directory is empty, and FastAPI route signatures plus Pydantic DTOs currently define the live contract.

## Rule 1 - Define the Contract Before Behavior Changes

Before implementing a new endpoint or changing an existing one, first update the
contract surface that exists in this repo.

For this project, that means:
- define or update the request and response models in `agos_app/app/models/`
- define or update the FastAPI route signature in `agos_app/app/api/routes/`
- if a committed OpenAPI artifact exists for the affected surface, update it in the
  same change

If the change is substantial and no checked-in spec exists yet, add the contract
artifact under `docs/changelog/v1/openapi/` as part of the same task instead of
skipping the contract step.

## Rule 2 - Keep DTOs Explicit and Boundary-Only

DTOs are the API contract. They are not domain entities and they are not storage
records.

- Use clear names such as `CreateOrderRequest`, `OrderResponse`,
  `AllocateOrderRequest`, and `AllocationResponse`.
- Do not introduce generic DTO names such as `Data`, `Payload`, or `Item`.
- Do not expose raw store records or future ORM entities directly through routes.
- Keep contract models in `agos_app/app/models/`, consistent with the current app layout.

## Rule 3 - Preserve Backward Compatibility by Default

Assume existing clients depend on the current route and DTO shapes.

Without deliberate versioning, do not:
- remove response fields
- rename public fields
- change field types
- make an optional request field required
- repurpose an endpoint to mean something else

Prefer additive change:
- add optional request fields
- add new response fields
- add new endpoints or sub-actions under `/api/v1/`

If a breaking change is unavoidable, introduce a new versioned contract instead of
silently mutating the old one.

## Rule 4 - Routes, DTOs, and Docs Must Move Together

An API change is incomplete if only one of these moves:

- route signature
- request or response DTO
- generated FastAPI docs behavior
- committed API documentation under `docs/changelog/v1/openapi/`

Do not change a route handler and leave the models stale. Do not change a model and
forget the route. Do not update code and leave committed API docs knowingly wrong
without an explicit divergence note.

## Rule 5 - Match Current Project Structure

When adding or changing endpoints, stay inside the repo's existing API layout:

- route groups live in `agos_app/app/api/routes/`
- route mounting lives in `agos_app/app/api/router.py`
- contract DTOs live in `agos_app/app/models/`
- the active public prefix is `/api/v1/`

Do not introduce a second routing convention or alternate DTO package unless the
architecture decision is documented first.

## Rule 6 - Make Contract Reviews Easy

Every API-changing patch should let another engineer answer these questions quickly:

- what path changed
- what request shape changed
- what response shape changed
- whether the change is additive or breaking
- which docs or schema files were updated with it

If the diff does not make those answers obvious, the contract work is incomplete.

## Checklist Before Closing API Work

- [ ] Route signature and DTOs were updated before or with implementation logic
- [ ] Public field names remain explicit and stable
- [ ] Change is backward compatible, or a new version was introduced
- [ ] `docs/changelog/v1/openapi/` was updated when a committed spec exists or was needed
- [ ] Route group and `/api/v1/` conventions remain consistent
