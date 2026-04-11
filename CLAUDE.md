# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Agri OS** — an operating system for agricultural supply chain management. The current phase (Phase 1) is a deterministic core API: source of truth before any AI/agent layer is added.

## Development Commands

```bash
# Install dependencies
cd agos_app
pip install -r requirements.txt

# Run the API server
uvicorn app.main:app --reload

# API is available at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

Ruff is used for linting (`PYENV_VERSION=agos_3.10.14 ruff check agos_app/`). No test framework is configured yet. PostgreSQL migration scaffolding lives under `agos_app/alembic/`. The service layer defaults to in-memory store; the postgres write path is controlled by `store/_db.py::is_enabled()`.

## Architecture

### Layer Model

The system has 6 layers (documented in `system_v1.md`):

1. **Input Channels** — Internal UI, CRM, Zalo/Facebook chat, admin dashboard
2. **Ingress & Normalization** — Schema standardization before processing
3. **Agri OS Core (Deterministic)** — This repo; the single source of truth
4. **Output** — QR/traceability, dashboards, packing lists, financial reports
5. **AI/Agent Layer** — Future orchestration (deliberately not built in Phase 1)
6. **Integrations** — Third-party systems

### Write Path

```
Command → Command Gateway (validate, RBAC, idempotency check)
        → Application Service (domain logic)
        → Policy/Workflow Engine (state machine transitions)
        → Event Store (append-only domain event)
        → Projection Workers (update read models)
        → Audit Log
```

No direct DB mutations — all state changes are recorded as domain events first.

### Read Path

Events → Projection Workers → Role-specific Read Models (BFF views)

### Code Layout

```
agos_app/
├── app/
│   ├── main.py           # FastAPI entrypoint, CORS, router mount
│   ├── api/
│   │   ├── router.py     # Aggregates 8 route groups under /api/v1/
│   │   └── routes/       # One file per domain (customers, orders, lots, farm, preorders, views, events, health)
│   ├── models/           # Pydantic v2 schemas (DTOs, not ORM models)
│   │   ├── common.py     # Shared: Meta, ErrorResponse, DomainEvent (includes tenantId placeholder)
│   │   └── *.py          # Per-domain schemas
│   ├── core/
│   │   ├── codegen.py    # Centralized human-readable code generation (KH-, DT-, ORD-, LOT- formats)
│   │   ├── gateway.py    # Command Gateway: idempotency, state machine transitions
│   │   └── events.py     # Domain event factory (dotted-lowercase eventName + PascalCase eventType)
│   ├── services/         # Application services — one file per domain
│   ├── store/
│   │   ├── _db.py        # DB connection + is_enabled() flag
│   │   ├── customers.py  # Customer store operations
│   │   ├── lots.py       # Lot store operations
│   │   ├── orders.py     # Order store operations (atomic cancel/allocate)
│   │   ├── preorders.py  # Preorder store + increment_delivered_qty_atomic (SSoT for delivered qty)
│   │   ├── postgres_sync.py  # Backward-compat re-export shim (do not add logic here)
│   │   └── memory.py     # In-memory fallback for local dev / unit tests
│   └── db/session.py     # SQLAlchemy engine/session wiring for PostgreSQL
├── alembic/              # Executable schema revisions for Phase 1 PostgreSQL
```

### Domain Entities

Canonical implementation names: `CustomerProfile`, `Preorder`, `SalesOrder`, `SalesOrderLine`, `ProductSKU`, `LotBatch`, `Plot`, `CropCycle`, `Farmer`, `CropTask`.

Vietnamese architecture docs sometimes use shorter business names such as `Customer`, `Order`, and `Lot`. For the mapping between business labels and implementation names, see `docs/changelog/v1/architecture/04-canonical-data-model.md`.

### API Surface

All endpoints are under `/api/v1/`. The route groups are:

- `/health` — liveness check
- `/customers` — customer CRUD and preferences
- `/preorders` — pre-order management
- `/orders` — full order lifecycle (create → confirm → allocate → pack → ship → deliver / cancel)
- `/lots` — lot/batch management (harvest → release / block)
- `/farm` — farm and plot operations
- `/views` — read model projections (role-based BFF views)
- `/events` — domain event stream queries

## Key Design Principles

- **Deterministic core first, AI second** — the core must be reliable and event-sourced before any AI orchestration is layered on top.
- **Event-first writes** — state changes happen via domain events appended to an event store, never direct DB updates.
- **One truth, many views** — a single canonical data model; each consumer role sees a different projection.
- **Idempotency** — the Command Gateway must deduplicate commands before processing.

## Design Documentation

Core narrative docs live in two layers:

| Location | Purpose |
|------|---------|
| `system_v1.md` | 6-layer system vision |
| `determistic_layer_spec_v1.md` | Module specs for the deterministic core |
| `event_desc.md` | Domain event definitions and rationale |
| `minimal_requirement.md` | MVP data model requirements |
| `deterministic_core_diagram.md` | Mermaid diagrams for all core flows |
| `vibe_coding.md` | AI agent workflow and coding philosophy |
| `docs/changelog/v1/README.md` | index for the current architecture baseline |
| `docs/changelog/v1/architecture/` | phase-1 architecture set: vision, workflows, canonical data model, integration contracts, AI boundaries, migration path, and baseline sign-off |
| `docs/changelog/v1/architecture/naming-conventions.md` | frozen naming rules: entities, events, states, endpoints, DTOs, commands, modules |
| `docs/changelog/v1/architecture/coding-guardrails.md` | what must be correct from day 1 vs what can be stubbed in Phase 1 |
| `docs/changelog/v1/adrs/` | 6 ADRs (ADR-001 to ADR-006) covering core architectural decisions |
| `docs/changelog/v1/openapi/agros-api-v1.0.yaml` | committed OpenAPI baseline (27 endpoints) — update in same commit as any API change |

When repo-root docs and `docs/changelog/v1/architecture/` overlap, treat the `docs/changelog/v1/architecture/` set as the working baseline for current deterministic-core decisions.

**`docs/architecture/` is an empty placeholder — all actual docs are under `docs/changelog/v1/architecture/`.**

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **agriagos** (1654 symbols, 2388 relationships, 76 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## When Debugging

1. `gitnexus_query({query: "<error or symptom>"})` — find execution flows related to the issue
2. `gitnexus_context({name: "<suspect function>"})` — see all callers, callees, and process participation
3. `READ gitnexus://repo/agriagos/process/{processName}` — trace the full execution flow step by step
4. For regressions: `gitnexus_detect_changes({scope: "compare", base_ref: "main"})` — see what your branch changed

## When Refactoring

- **Renaming**: MUST use `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` first. Review the preview — graph edits are safe, text_search edits need manual review. Then run with `dry_run: false`.
- **Extracting/Splitting**: MUST run `gitnexus_context({name: "target"})` to see all incoming/outgoing refs, then `gitnexus_impact({target: "target", direction: "upstream"})` to find all external callers before moving code.
- After any refactor: run `gitnexus_detect_changes({scope: "all"})` to verify only expected files changed.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Tools Quick Reference

| Tool | When to use | Command |
|------|-------------|---------|
| `query` | Find code by concept | `gitnexus_query({query: "auth validation"})` |
| `context` | 360-degree view of one symbol | `gitnexus_context({name: "validateUser"})` |
| `impact` | Blast radius before editing | `gitnexus_impact({target: "X", direction: "upstream"})` |
| `detect_changes` | Pre-commit scope check | `gitnexus_detect_changes({scope: "staged"})` |
| `rename` | Safe multi-file rename | `gitnexus_rename({symbol_name: "old", new_name: "new", dry_run: true})` |
| `cypher` | Custom graph queries | `gitnexus_cypher({query: "MATCH ..."})` |

## Impact Risk Levels

| Depth | Meaning | Action |
|-------|---------|--------|
| d=1 | WILL BREAK — direct callers/importers | MUST update these |
| d=2 | LIKELY AFFECTED — indirect deps | Should test |
| d=3 | MAY NEED TESTING — transitive | Test if critical path |

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/agriagos/context` | Codebase overview, check index freshness |
| `gitnexus://repo/agriagos/clusters` | All functional areas |
| `gitnexus://repo/agriagos/processes` | All execution flows |
| `gitnexus://repo/agriagos/process/{name}` | Step-by-step execution trace |

## Self-Check Before Finishing

Before completing any code modification task, verify:
1. `gitnexus_impact` was run for all modified symbols
2. No HIGH/CRITICAL risk warnings were ignored
3. `gitnexus_detect_changes()` confirms changes match expected scope
4. All d=1 (WILL BREAK) dependents were updated

## Keeping the Index Fresh

After committing code changes, the GitNexus index becomes stale. Re-run analyze to update it:

```bash
npx gitnexus analyze
```

If the index previously included embeddings, preserve them by adding `--embeddings`:

```bash
npx gitnexus analyze --embeddings
```

To check whether embeddings exist, inspect `.gitnexus/meta.json` — the `stats.embeddings` field shows the count (0 means no embeddings). **Running analyze without `--embeddings` will delete any previously generated embeddings.**

> Claude Code users: A PostToolUse hook handles this automatically after `git commit` and `git merge`.

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
