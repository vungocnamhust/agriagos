---
name: spec-to-scaffold
description: >
  Given an approved OpenAPI spec or a confirmed domain use case spec, generates
  PostgreSQL DDL suggestions, Alembic migration notes, repository interfaces,
  and FastAPI route skeletons — all aligned to the project's event-sourced
  architecture and domain boundaries.
  Trigger when the user says "scaffold this spec", "generate the code skeleton
  for", "implement the DDL for", "create the repository for", "turn this spec
  into code", or after the usecase-to-openapi skill has produced a confirmed
  spec. Never generates implementation logic — only contracts and structure.
  Stops and asks if the spec is incomplete or if domain boundary placement is
  ambiguous.
---

# Spec → Scaffold

Convert a confirmed spec into implementation-ready scaffolding: DDL, migration
notes, repository interfaces, and FastAPI route skeletons.

This skill generates **structure, not logic**. Handlers return `TODO` stubs.
Repositories define interfaces, not implementations. DDL captures the read-model
schema; the event store is the source of truth.

---

## Prerequisites

The input spec must be one of:
- A confirmed OpenAPI YAML/JSON block (from the `usecase-to-openapi` skill or
  manually written).
- A confirmed domain entity description listing fields, types, constraints,
  and state transitions.

If the spec is a draft, not yet reviewed, or missing field types, stop and say:
"This spec needs review before scaffolding. Use the `usecase-to-openapi` skill
to confirm invariants first."

---

## Phase 1 — Read and Classify the Spec

Extract from the spec:

| Item | Where to find it |
|------|-----------------|
| Domain entity name(s) | `operationId`, `tags`, schema names |
| Fields + types + constraints | `properties`, `required`, `format`, `enum` |
| State machine | `enum` on status fields, or `x-state-machine` extension |
| Write operations | POST/PATCH/DELETE paths — these become commands |
| Read operations | GET paths — these become queries over projections |
| Events implied | Side effects section, postconditions, or `x-events` extension |
| Auth scope | `security`, `x-roles` |

Determine which **domain module** this belongs to:

| Domain | Module file | Pydantic models file |
|--------|------------|----------------------|
| Customers | `app/api/routes/customers.py` | `app/models/customers.py` |
| Orders | `app/api/routes/orders.py` | `app/models/orders.py` |
| Lots/Batches | `app/api/routes/lots.py` | `app/models/lots.py` |
| Farm/Plot | `app/api/routes/farm.py` | `app/models/farm.py` |
| Pre-orders | `app/api/routes/preorders.py` | `app/models/preorders.py` |
| Read models | `app/api/routes/views.py` | `app/models/views.py` |
| Events | `app/api/routes/events.py` | `app/models/common.py` |

If the entity crosses two domains (e.g. an `Allocation` that links `Order` and
`Lot`), stop and ask: "This entity spans the Order and Lot domains. Should it
live in `orders` (owned by Order aggregate) or `lots` (owned by Lot aggregate),
or does it need a new module?"

---

## Phase 2 — PostgreSQL DDL

Generate DDL for the **read model** (projection table), not the event store.

Rules:
- Table names: `snake_case`, plural (e.g. `crop_cycles`, `lot_batches`).
- Always include: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`,
  `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`,
  `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- Map Pydantic types → Postgres types:

  | Pydantic / Python | PostgreSQL |
  |-------------------|-----------|
  | `str` (short) | `VARCHAR(255)` |
  | `str` (long/text) | `TEXT` |
  | `str` with `format: uuid` | `UUID` |
  | `int` | `INTEGER` |
  | `float` / `Decimal` | `NUMERIC(precision, scale)` — ask scale if not specified |
  | `bool` | `BOOLEAN` |
  | `datetime` | `TIMESTAMPTZ` |
  | `date` | `DATE` |
  | `Enum` | `VARCHAR(50)` with `CHECK` constraint listing valid values |
  | `list[str]` / `list[UUID]` | `TEXT[]` / `UUID[]` |
  | nested object | separate table + FK, or `JSONB` — ask if not clear |

- Foreign keys: always add `REFERENCES <table>(id) ON DELETE RESTRICT` unless
  the spec says otherwise.
- State column: always add `CHECK` constraint with the valid enum values.
- Add indexes on: foreign keys, status/state columns, `created_at`.

**DDL output format:**

```sql
-- ================================================================
-- Read model: <entity_name>
-- Domain: <domain module>
-- Generated from: <spec operationId or entity name>
-- NOTE: This is the projection table. Source of truth is the event store.
-- ================================================================

CREATE TABLE <table_name> (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    -- <domain fields here>
    status          VARCHAR(50)     NOT NULL
                    CHECK (status IN (<enum values>)),
    -- foreign keys
    <fk_field>      UUID            NOT NULL
                    REFERENCES <parent_table>(id) ON DELETE RESTRICT,
    -- audit
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT now(),
    version         INTEGER         NOT NULL DEFAULT 1  -- optimistic lock
);

CREATE INDEX idx_<table>_status      ON <table_name>(status);
CREATE INDEX idx_<table>_<fk_field>  ON <table_name>(<fk_field>);
CREATE INDEX idx_<table>_created_at  ON <table_name>(created_at DESC);
```

---

## Phase 3 — Alembic Migration Notes

Do not generate the full Alembic migration file (that requires running
`alembic revision`). Instead, produce structured notes:

```
## Migration Notes

**Migration name suggestion:** add_<table_name>_table
**Type:** new table / alter table / add column / add index

**upgrade() operations (in order):**
1. op.create_table('<table_name>', ...)
2. op.create_index('idx_<table>_status', '<table_name>', ['status'])
3. op.create_index(...)

**downgrade() operations (reverse order):**
1. op.drop_index('idx_<table>_status')
2. op.drop_table('<table_name>')

**Data migration needed:** yes / no
  If yes: <describe what data must be backfilled and from where>

**Safe to run on live DB:** yes / no
  If no: <reason — e.g. locks large table, changes NOT NULL without default>

**Dependencies:** <list any migrations that must run first>
```

---

## Phase 4 — Repository Interface

Generate an abstract repository interface for the domain entity. This enforces
the Repository Pattern: application services depend on the interface, not the
storage implementation.

```python
# app/repositories/<domain>_repository.py
from abc import ABC, abstractmethod
from uuid import UUID
from typing import Optional

from app.models.<domain> import (
    <EntityName>,
    <EntityName>CreateRequest,
    <EntityName>UpdateRequest,
)


class <EntityName>Repository(ABC):
    """
    Abstract repository for <EntityName>.

    All state mutations must go through domain events; these methods
    reflect the read model and command intake only.
    """

    @abstractmethod
    async def get_by_id(self, entity_id: UUID) -> Optional[<EntityName>]:
        """Return the entity or None if not found."""
        ...

    @abstractmethod
    async def list(
        self,
        *,
        # add filter params derived from the spec's query params
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[<EntityName>]:
        """Return a page of entities matching the filters."""
        ...

    @abstractmethod
    async def save_command(self, command: <EntityName>CreateRequest) -> <EntityName>:
        """
        Persist the command intent as a domain event and return the
        projected read model after the event is applied.
        Raises DomainError if preconditions are not met.
        """
        ...

    # Add one method per state-transition command in the spec.
    # Example:
    # @abstractmethod
    # async def confirm(self, entity_id: UUID) -> <EntityName>: ...
    # @abstractmethod
    # async def cancel(self, entity_id: UUID, reason: str) -> <EntityName>: ...
```

One interface method per state-transition command found in the spec.
Do not add methods not implied by the spec.

---

## Phase 5 — FastAPI Route Skeleton

Generate a route file skeleton. All handlers return `TODO` stubs with the
correct response type annotation.

```python
# app/api/routes/<domain>.py
"""
<Domain> routes — <one-line description of this route group>

Write path: Command → Command Gateway → Application Service
            → Event Store → Projection Workers → Read Model
All mutations are event-sourced; handlers must not mutate DB directly.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from app.models.<domain> import (
    <CommandName>Request,
    <CommandName>Response,
)
from app.models.common import ErrorResponse

router = APIRouter(prefix="/<resource>", tags=["<domain>"])


# ------------------------------------------------------------------
# Commands (write path)
# ------------------------------------------------------------------

@router.post(
    "/<action>",
    response_model=<CommandName>Response,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Validation error"},
        409: {"model": ErrorResponse, "description": "State conflict"},
        422: {"model": ErrorResponse, "description": "Domain rule violation"},
    },
    summary="<one-line from spec>",
)
async def <action_verb>_<resource>(
    payload: <CommandName>Request,
    # current_user: CurrentUser = Depends(get_current_user),  # TODO: wire auth
) -> <CommandName>Response:
    # TODO: validate preconditions
    # TODO: route command to Command Gateway
    # TODO: return projected response
    raise HTTPException(status_code=501, detail="Not implemented")


# ------------------------------------------------------------------
# Queries (read path — projection views)
# ------------------------------------------------------------------

@router.get(
    "/{<resource>_id}",
    response_model=<EntityName>,
    responses={
        404: {"model": ErrorResponse, "description": "Not found"},
    },
    summary="Get <entity> by ID",
)
async def get_<resource>(
    <resource>_id: UUID,
) -> <EntityName>:
    # TODO: query read model via repository
    raise HTTPException(status_code=501, detail="Not implemented")
```

Add one handler per path/method pair in the spec.
Write-path handlers (POST/PATCH/DELETE) go under the Commands section.
Read-path handlers (GET) go under the Queries section.

---

## Phase 6 — Pydantic Models Stub

If new schemas are needed that don't yet exist in `app/models/`:

```python
# app/models/<domain>.py  (add to existing file or create new)
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field
# from pydantic import field_validator  # add if validation logic needed


class <CommandName>Request(BaseModel):
    """Request body for <operationId>."""
    # <field>: <type> = Field(..., description="<from spec>", example=<value>)
    model_config = {"extra": "forbid"}   # reject unknown fields


class <CommandName>Response(BaseModel):
    """Response for <operationId>."""
    id: UUID
    status: str
    # <other fields from spec response schema>
    created_at: datetime
    updated_at: datetime
```

---

## Output Order

Always present the output in this sequence so the implementer can work top-down:

1. **Domain placement confirmation** (which module, any cross-domain question)
2. **PostgreSQL DDL** (read model table + indexes)
3. **Migration notes** (upgrade/downgrade steps)
4. **Repository interface** (`app/repositories/<domain>_repository.py`)
5. **Pydantic models stub** (additions to `app/models/<domain>.py`)
6. **FastAPI route skeleton** (`app/api/routes/<domain>.py`)
7. **Checklist** (see below)

## Final Checklist

```
## Scaffold Checklist

- [ ] DDL reviewed and approved before running migration
- [ ] Migration notes converted to Alembic file (`alembic revision --autogenerate -m "..."`)
- [ ] Repository interface committed before any implementation
- [ ] Route file added to `app/api/router.py` with correct prefix
- [ ] Pydantic models added to `app/models/<domain>.py`
- [ ] All handlers currently raise 501 — implementation tracked separately
- [ ] No direct DB mutations in handlers (event-sourced writes only)
- [ ] Auth dependency wired once auth module exists
```

---

## Hard Stops

Halt and ask the user before continuing if:

- A field's type is ambiguous (e.g. `amount` — is this `INTEGER` grams,
  `NUMERIC(10,2)` kg, or `NUMERIC(15,4)` monetary?).
- A nested object's storage strategy is unclear (separate table vs JSONB).
- An entity spans two domain boundaries.
- The spec contains a state transition not covered by any repository method.
- A migration would add a `NOT NULL` column to a table that already has rows
  (requires a default or a two-step migration).
