# Agri OS Agent Invocation Policy

This policy defines which agent or skill to use for each task shape in Agri OS.
The goal is to keep feature delivery fast without losing contract, boundary, or
documentation discipline.

Quick references:

- One-screen chooser: `.github/agent-selection-cheatsheet.md`
- Global agent classification: `.github/global-agent-inventory.md`

## Default Rules

- Prefer repo-local workflow skills and repo-local review agents over global generic agents when both exist.
- Do not stack agents by habit. Pick the smallest pipeline that covers the risk of the task.
- Default to one pre-implementation lane and one post-implementation lane.
- Escalate to additional specialist agents only when the changed surface justifies it.
- For small local fixes, do not invoke `planner` or broad architecture agents.

## Preferred Agents And Skills

### Default keepers

- `explore-plan-act`: default implementation workflow for most feature and bugfix work
- `impact-analysis`: use before changes with medium or high blast radius
- `Contract Guardian`: default contract review for route, DTO, schema, migration, and OpenAPI drift
- `Implementation Reviewer`: default final-pass review for behavior, boundaries, tests, and docs drift
- `docs-sync`: use whenever behavior, state flow, contracts, diagrams, or architecture docs may move

### Conditional specialists

- `tdd-guide`: use for new behavior, write-path bug fixes, or when the touched slice lacks focused regression coverage
- `security-reviewer`: use for authz, input validation, external API calls, file handling, secrets, or sensitive data flows
- `database-reviewer`: use for Alembic, PostgreSQL views, constraints, indexes, SQL-heavy store work, or concurrency-sensitive writes
- `Integration Mapper`: use for external ID mapping, vendor payload normalization, anti-corruption layers, retries, and idempotency at integration boundaries
- `integration-audit`: use when reviewing or designing a full integration flow instead of one adapter function
- `planner`: use only for multi-phase features, architectural changes, or refactors spanning several domains
- `domain-architect`: use when bounded-context ownership, aggregate boundaries, or domain-event shape is being changed
- `code-explorer`: use when the owning flow is unclear and local file reads are not enough

### De-prioritized defaults

- Prefer `Implementation Reviewer` over `code-reviewer` for normal Agri OS changes
- Prefer repo-local `Contract Guardian` over the global `contract-guardian`
- Prefer targeted specialists over `python-reviewer` unless the issue is Python-specific quality outside repo rules
- Do not use `build-error-resolver` as a default lane for this repo; reserve it for narrow compile or type failures

## Task Pipelines

### 1. Small local fix

Use when one service, route, model, or store file changes and the blast radius is obvious.

- Pre-implementation: `explore-plan-act`
- Post-implementation: `Implementation Reviewer`
- Add `Contract Guardian` only if route, DTO, schema, or docs-visible behavior changed

### 2. Standard feature in an existing domain

Use when adding or extending behavior in one domain without changing architecture.

- Pre-implementation: `explore-plan-act`
- Add before editing: `impact-analysis` if the change touches routes, DTOs, events, tests, docs, or multiple files across layers
- Post-implementation: `Implementation Reviewer`
- Add after implementation: `Contract Guardian` for API or schema-visible changes
- Add after implementation: `docs-sync` if docs, OpenAPI, diagrams, or divergence notes may need updates

### 3. New or changed API contract

Use when touching FastAPI routes, DTOs, response models, path semantics, error shapes, or OpenAPI surfaces.

- Pre-implementation: `impact-analysis`
- Implementation lane: `explore-plan-act`
- Post-implementation review: `Contract Guardian`
- Final review: `Implementation Reviewer`
- Documentation lane: `docs-sync`

### 4. Write-path bug fix or new write behavior

Use when changing service-layer invariants, idempotency, state transitions, event emission, or audit behavior.

- Pre-implementation: `explore-plan-act`
- Add before editing: `impact-analysis` if more than one aggregate, event, or boundary is touched
- Validation support: `tdd-guide`
- Final review: `Implementation Reviewer`
- Add `Contract Guardian` if any public request or response contract moved
- Add `docs-sync` if event names, state flow, or documented workflow changed

### 5. Authz, security, or trust-boundary changes

Use when changing role checks, bypass behavior, request metadata handling, validation, secrets, or external-call trust.

- Pre-implementation: `impact-analysis`
- Implementation lane: `explore-plan-act`
- Security review: `security-reviewer`
- Final review: `Implementation Reviewer`
- Add `Contract Guardian` if API-visible denial behavior or request contract changed
- Add `docs-sync` if permission docs or divergence notes changed

### 6. PostgreSQL, migration, or SQL-heavy work

Use when changing Alembic revisions, store SQL, views, constraints, or index strategy.

- Pre-implementation: `impact-analysis`
- Implementation lane: `explore-plan-act`
- Specialist review: `database-reviewer`
- Add `Contract Guardian` if DB shape affects API DTOs or committed contract artifacts
- Final review: `Implementation Reviewer`
- Add `docs-sync` if canonical data model, migration docs, or diagrams changed

### 7. Integration or anti-corruption work

Use when touching adapters, vendor payloads, external IDs, sync loops, or integration DTOs.

- Pre-implementation: `impact-analysis`
- Implementation lane: `explore-plan-act`
- Mapping review: `Integration Mapper`
- Flow review: `integration-audit` for larger sync or retry workflows
- Add `security-reviewer` when the integration crosses trust boundaries or handles secrets
- Final review: `Implementation Reviewer`

### 8. Architecture or domain-boundary change

Use when changing bounded contexts, aggregate ownership, event contracts, or multi-domain workflow structure.

- Planning lane: `planner`
- Optional review before editing: `domain-architect`
- Implementation lane: `explore-plan-act`
- Contract review: `Contract Guardian`
- Final review: `Implementation Reviewer`
- Documentation lane: `docs-sync`

### 9. Docs-only or workflow-guidance change

Use when changing repository guidance, README-level workflow docs, ADR pointers, or execution policy without changing runtime behavior.

- Pre-edit check: local read of the owning guidance surface
- Add `docs-sync` only if the edited docs cross-reference mutable architecture facts
- No generic review agent by default unless the doc changes workflow policy or contract expectations

## Explicit Anti-Patterns

- Do not invoke `planner`, `tdd-guide`, `security-reviewer`, `database-reviewer`, `Contract Guardian`, and `Implementation Reviewer` all on the same small fix.
- Do not use generic global reviewers when an Agri OS-specific repo-local review agent already covers the lane.
- Do not skip `Contract Guardian` after route or DTO changes just because tests pass.
- Do not skip `docs-sync` when events, state transitions, OpenAPI, or architecture guidance moved.
- Do not use architecture agents to compensate for missing local exploration.

## Operating Limits

- Small fix: at most 2 agent lanes
- Standard feature: usually 3 agent lanes
- High-risk feature: usually 4 agent lanes
- Anything above 4 lanes needs a concrete reason in the task notes or PR summary

## Recommended Default Sequences

- Local fix: `explore-plan-act` -> implement -> `Implementation Reviewer`
- API feature: `impact-analysis` -> `explore-plan-act` -> implement -> `Contract Guardian` -> `Implementation Reviewer` -> `docs-sync`
- Write-path bug: `explore-plan-act` -> `tdd-guide` when needed -> implement -> `Implementation Reviewer`
- Migration/API change: `impact-analysis` -> `explore-plan-act` -> implement -> `database-reviewer` -> `Contract Guardian` -> `Implementation Reviewer` -> `docs-sync`
- Integration work: `impact-analysis` -> `explore-plan-act` -> implement -> `Integration Mapper` -> `Implementation Reviewer`