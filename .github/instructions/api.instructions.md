---
description: "Use when editing FastAPI routes, services, or canonical DTOs in Agri OS. Enforces route-service-domain separation, contract-first API changes, event emission rules, and validation expectations."
applyTo: "agos_app/app/api/**/*.py,agos_app/app/services/**/*.py,agos_app/app/models/**/*.py"
---

# API Instructions

- Treat `.claude/rules/api-contract-first.md`, `.claude/rules/domain-boundaries.md`, `.claude/rules/events.md`, and `.claude/rules/canonical-model.md` as enforcement rules for this surface. Resolve mutable contract and architecture facts through `docs/changelog/v1/architecture/00-source-of-truth-registry.md` before relying on repo summaries or current code shape.
- Keep route handlers thin: parse request, call one service path, return typed DTOs.
- Keep business rules, state transitions, and event emission in `agos_app/app/services/` or an explicit orchestration service.
- Update route signatures and DTOs together before or with behavior changes.
- Do not import `store/` from routes or leak Pydantic DTOs into `core/` or `store/`.
- Preserve backward compatibility by default for published or integrated surfaces. During early scaffolding, document intentional contract reshaping explicitly instead of assuming compatibility.
- Emit past-tense domain events through `app.core.events.emit()` only after a successful state change.
- For write-path changes, validate idempotency, invalid transitions, and missing aggregate scenarios.
- When API behavior changes, review `docs/changelog/v1/openapi/` and architecture docs for drift in the same task.
