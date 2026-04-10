---
name: impact-map
description: >
  Before implementing any change, systematically scan the codebase to identify
  every affected area — entities, routes, events, migrations, tests, docs, and
  integrations — then produce a structured impact map with risk levels.
  Trigger this skill whenever the user says "I want to change X", "add a field
  to Y", "rename Z", "deprecate this endpoint", "refactor the order flow", or
  any time a change is described before code is touched. The impact map must
  be presented and acknowledged before any editing begins. Use this even for
  changes that seem small — the most dangerous regressions come from changes
  that looked safe.
---

# Impact Map

Produce a complete impact map before touching any code. The goal is to surface
every place in the system that will break, behave differently, or need updating
as a consequence of the proposed change — so nothing is discovered after the
fact.

---

## Step 1 — Understand the Change

Read the user's description carefully. Extract:

- **Target**: the specific symbol, field, model, endpoint, event, or module
  being changed.
- **Nature of change**: add / remove / rename / modify behavior / change
  contract / deprecate.
- **Stated scope**: what the user explicitly included or excluded.

If the target is ambiguous (e.g. "the order model"), ask one clarifying
question before scanning. Don't ask more than one.

---

## Step 2 — Scan for Impact

Search systematically across all eight dimensions below. For each dimension,
grep for the target symbol, its variants (plural forms, snake_case,
PascalCase), and any related identifiers.

### 2.1 Domain Entities
- Pydantic models or dataclasses that embed the target field or reference the
  target type.
- Derived computed fields or validators that depend on the value.
- Parent/child relationships (e.g. `Lot` references `CropCycle`).

### 2.2 API Routes
- Endpoints that accept or return the target type or field.
- Path parameters or query params that name the target.
- Response schemas (especially BFF views) that project the target.

### 2.3 Domain Events
- Events that carry the target field in their payload.
- Event handlers or projection workers that read the field.
- Aggregate root methods that emit events containing the target.

### 2.4 Migrations
- Existing migration files that touch the table or column being changed.
- Whether a new migration will be needed (schema change, rename, new column).
- Seeding scripts or fixtures that hard-code the affected value.

### 2.5 Tests
- Unit tests that assert on the exact field name, value, or behavior.
- Integration tests that exercise the affected endpoint.
- Fixture factories that construct the affected model.
- Snapshot or contract tests that would capture a schema change.

### 2.6 Documentation
- Docstrings on the target class or function.
- Swagger/OpenAPI descriptions (`description=` in `Field()`).
- Markdown docs or design docs that name the target.
- Changelog entries that describe the current contract.

### 2.7 Integrations
- External systems that consume the affected endpoint or event (Zalo,
  Facebook, CRM, ERP connectors, webhook targets).
- Third-party SDKs or clients that serialize/deserialize the target type.
- Any published API contract (versioned endpoints, partner-facing schemas).

### 2.8 Configuration & Infrastructure
- Environment variables or feature flags gated on the target.
- CORS, auth, or rate-limit rules scoped to the affected route.
- Cron jobs or background workers that reference the affected module.

---

## Step 3 — Assign Risk Levels

For each impacted item, assign one of three risk levels:

| Risk | Meaning |
|------|---------|
| **HIGH** | Breaking change — callers will fail at runtime or tests will fail. Requires coordinated update. |
| **MEDIUM** | Behavior changes silently or data becomes inconsistent. Will not immediately crash but will cause bugs. |
| **LOW** | Cosmetic, additive, or internal-only. Unlikely to break anything; safe to change independently. |

A change is HIGH risk if any of these is true:
- It alters a published API contract (endpoint path, field name, event schema).
- It removes or renames something imported by another module.
- It changes a constraint (nullable → non-null, type widening → narrowing).
- It modifies an event that drives a projection worker.

---

## Step 4 — Output the Impact Map

Present the map before any editing. Format:

```
## Impact Map — <target symbol or description>

**Change:** <one-line description of what is being changed and how>

### Affected Areas

#### Entities
| File | Symbol | Impact | Risk |
|------|--------|--------|------|
| path/to/model.py | ClassName.field_name | <why affected> | HIGH / MEDIUM / LOW |

#### Routes
| File | Method + Path | Impact | Risk |
|------|--------------|--------|------|

#### Events
| File | EventName | Impact | Risk |
|------|-----------|--------|------|

#### Migrations
| Status | Detail |
|--------|--------|
| Required | <describe the migration needed> |
| Existing affected | path/to/migration.py |

#### Tests
| File | Test Name | Impact | Risk |
|------|-----------|--------|------|

#### Documentation
| File | Location | Impact | Risk |
|------|----------|--------|------|

#### Integrations
| System | Contract point | Impact | Risk |
|--------|---------------|--------|------|

#### Configuration / Infrastructure
| File / Setting | Impact | Risk |
|---------------|--------|------|

---

### Risk Summary
- HIGH:   <count> items → <list file:symbol pairs>
- MEDIUM: <count> items → <list>
- LOW:    <count> items

### Recommended edit order
<Ordered list: which files to change first to minimize breakage, typically
 models → events → routes → tests → docs>

### Items requiring coordination before edit
<Anything that involves an external system, a published contract, or
 requires a migration — flag these for explicit user sign-off>
```

---

## Step 5 — Gate

After presenting the map:

1. If there are **HIGH risk items involving external integrations or published
   contracts**, explicitly state: "This change affects a published contract.
   External consumers may break. Confirm you want to proceed."
2. Otherwise, ask: "Does this impact map look complete? Any areas to add or
   remove?"
3. Wait for the user to confirm before editing anything.

If the user says the map is missing something, update it and re-present before
proceeding.

---

## Stop Conditions

Halt and return to this skill if, during implementation:

- A file that was marked LOW risk turns out to reference the target symbol in
  an unexpected way.
- A new import or dependency is discovered that wasn't in the impact map.
- A test failure reveals an undocumented consumer of the changed symbol.

In each case: update the impact map, re-present the affected row with the
corrected risk level, and continue only after user acknowledgment.
