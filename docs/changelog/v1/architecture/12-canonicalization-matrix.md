# 12. Canonicalization Matrix

## Scope

This matrix tracks project-lane literals reviewed during the 2026-04 canonicalization sweep.

## Already canonicalized

| Category | Surface | Canonical form |
|---|---|---|
| Actor role vocabulary | authz, policy sets, project read/write guards | `ActorRole` enum + `app/core/policy_sets.py` |
| Project aggregate labels | project scope, assignment, contribution, cost, revenue services | `AggregateType` in `app/core/event_registry.py` |
| Project runtime event names | project scope, assignment, contribution, cost, revenue services | `*EventName` registries in `app/core/event_registry.py` |
| Contribution ledger status | DTOs, services, views | `ProjectContributionStatus` |
| Contribution subject type | contribution DTOs and service validation | `ProjectAssignmentTargetType` |
| Contribution verification status | contribution DTOs and store/service defaults | `ProjectContributionVerificationStatus` |
| Contribution verification source | contribution DTOs and store/service defaults | `ProjectContributionVerificationSource` |
| Revenue source order state | project revenue record service | `OrderStatus.delivered` |

## Should become enum next

| Literal family | Current observed values | Why deferred |
|---|---|---|
| `actorType` on `ProjectContributionEvent` | `person`, `partner` | Docs define actor identity conceptually but do not yet freeze the runtime vocabulary for the contribution lane |
| `contributionType` | `labor_day`, `cash_support` | Current runtime uses examples, not an authority-owned closed set |

## Should become registry constant next

| Literal family | Current surface | Why deferred |
|---|---|---|
| Audit action names | project services, audit normalization | Stable repeated strings, but not yet grouped by a dedicated authority-owned registry |
| Audit reason codes | project services, read authz, audit views | Repeated policy vocabulary that should move only after the action-name lane is grouped |

## Intentionally freeform for now

| Field | Reason |
|---|---|
| `role` on `ProjectContributionEvent` | Business role-in-project vocabulary is not yet authority-owned as a closed set |
| `source` on `ProjectContributionEvent` | Provenance lane is broader than the currently shipped project slice |
| `unit`, `currency`, `verificationNote`, `metadata` | Operational payload values remain data, not contract-owned vocabulary |

## Safe to leave literal

| Literal family | Reason |
|---|---|
| User-facing error messages | These are API messages, not canonical business vocabulary |
| SQL aliases in read-model queries | Query-local labels do not define domain vocabulary by themselves |