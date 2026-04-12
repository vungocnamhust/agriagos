# Divergence Ledger

Use this ledger when code intentionally diverges from the current documentation baseline.

This file is the central register for code-doc mismatches in Agri OS v1.

Do not keep divergence tracking only in local TODOs, comments, prompts, or instruction files.

## Entry Format

| ID | Concern | Code Surface | Doc Surface | Divergence | Why | Status | Exit Condition |
|---|---|---|---|---|---|---|---|
| DL-YYYYMMDD-01 | `<event/state/api/domain>` | `path/to/code.py` | `path/to/doc.md` | short description of what differs | why the divergence exists | `open` / `resolved` / `accepted` | condition, linked task, or date |

## Rules

1. Add an entry in the same change that introduces the divergence.
2. Update the status when the divergence is resolved or explicitly accepted.
3. Keep entries short and factual.
4. If the divergence affects a public contract or architecture baseline, also add a local note in the owning doc that points back to the ledger entry.
5. Do not use this file as a substitute for docs updates that should already move in the same change.

## Active Entries

| ID | Concern | Code Surface | Doc Surface | Divergence | Why | Status | Exit Condition |
|---|---|---|---|---|---|---|---|
| DL-20260412-01 | api/permission | `agos_app/app/api/routes/audit.py`, `agos_app/app/api/router.py` | `docs/changelog/v1/architecture/07-permission-matrix.md`, `docs/changelog/v1/diagram/08-role-based-view-permission-diagram.md` | `GET /api/v1/audit` exists as a public read-only route before role-based gateway/auth enforcement is implemented. | Phase 1 needs operator/debug readback now, while permission enforcement is still an acknowledged later-hardening lane. | open | Resolve when audit-read access is enforced at the route/gateway boundary according to the permission baseline. |

## Resolved Entries

| ID | Concern | Code Surface | Doc Surface | Divergence | Why | Status | Exit Condition |
|---|---|---|---|---|---|---|---|
| DL-20260411-03 | event/api/domain | `agos_app/app/models/lots.py`, `agos_app/app/services/lots.py`, `agos_app/app/api/routes/lots.py` | `docs/changelog/v1/openapi/agros-api-v1.0.yaml`, `docs/changelog/v1/architecture/naming-conventions.md`, `docs/changelog/v1/diagram/04-event-storming-event-map.md`, `CLAUDE.md` | `processing_batch` had temporarily shared the harvested-lot create contract and emitted `lot.harvest.created`. | Harvested Lot Core shipped before the dedicated processed-lot command and route were introduced. | resolved | Resolved by adding `CreateProcessedLotRequest`, `POST /api/v1/lots/processed`, and `lot.processed.created`, then syncing the owning docs. |
