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
| DL-20260416-01 | architecture/domain | `agos_app/app/**`, `agos_app/alembic/**` | `docs/changelog/v1/adrs/ADR-013-projectscope-is-the-soft-value-stream-scope.md`, `docs/changelog/v1/architecture/03-domain-glossary.md`, `docs/changelog/v1/architecture/04-canonical-data-model.md`, `docs/changelog/v1/architecture/05-event-catalog.md`, `docs/changelog/v1/architecture/06-state-transitions.md`, `docs/changelog/v1/architecture/07-permission-matrix.md`, `docs/changelog/v1/architecture/10-assumptions-and-migration-path.md`, `docs/changelog/v1/diagram/03-canonical-data-model-erd.md`, `docs/changelog/v1/diagram/04-event-storming-event-map.md`, `docs/changelog/v1/diagram/08-role-based-view-permission-diagram.md` | Runtime hiện đã có standalone `ProjectScope` schema/API slice và assignment lane đầu tiên cho `plot/crop_cycle/lot/preorder/order`. Divergence còn lại là contribution ledger, shared-resource/economics records, reporting views, và confidence-driven backfill chưa rollout. | PR-1 và PR-2 ship aggregate cùng assignment baseline trước để khóa write-path attribution surface; các slices economics/reporting tiếp theo vẫn đi theo staged rollout thay vì one-shot domain rewrite. | open | Resolved when contribution, economics, và ít nhất một reporting slice của `ProjectScope` land, hoặc khi ADR-013 bị supersede. |
| DL-20260415-01 | architecture/domain | `agos_app/app/**`, `agos_app/alembic/**` | `docs/changelog/v1/adrs/ADR-012-organization-is-legal-operating-owner-tenant-remains-deployment-boundary.md`, `docs/changelog/v1/architecture/03-domain-glossary.md`, `docs/changelog/v1/architecture/04-canonical-data-model.md`, `docs/changelog/v1/architecture/08-integration-contracts.md`, `docs/changelog/v1/architecture/10-assumptions-and-migration-path.md` | Runtime hiện đã có standalone `organizations` schema, CRUD, state actions, event emission, additive `organization_id` propagation cho canonical farm/commercial records, và current Phase 1 read-model surfaces; divergence còn lại là integration-facing surfaces chưa rollout hết. | PR-1 khóa decision trước, các slice tiếp theo đang rollout dần thay vì mutate toàn bộ Phase 1 schema trong một bước. | open | Resolved when remaining integration-facing `organization_id` rollout slices land, hoặc khi architecture decision bị supersede. |
| DL-20260412-02 | permission/api | `agos_app/app/services/orders.py`, `agos_app/app/models/orders.py`, `agos_app/app/api/routes/orders.py` | `docs/changelog/v1/architecture/07-permission-matrix.md`, `docs/changelog/v1/openapi/agros-api-v1.0.yaml` | Packed-or-later order cancel is currently role-gated but does not yet enforce approval evidence such as `approvalRef`, even though the docs still classify that path as approval-required. | PR5 focused on shared order authz rollout without introducing a second approval/escalation flow inside order cancel. | open | Resolved when packed-or-later cancel either enforces an explicit approval/escalation contract or the docs/OpenAPI are revised to remove approval semantics from that path. |

## Resolved Entries

| ID | Concern | Code Surface | Doc Surface | Divergence | Why | Status | Exit Condition |
|---|---|---|---|---|---|---|---|
| DL-20260412-01 | api/permission | `agos_app/app/api/routes/audit.py`, `agos_app/app/api/router.py` | `docs/changelog/v1/architecture/07-permission-matrix.md`, `docs/changelog/v1/diagram/08-role-based-view-permission-diagram.md` | `GET /api/v1/audit` existed as a public read-only route before role-based gateway/auth enforcement was implemented. | Phase 1 needed operator/debug readback before the shared read-auth seam landed. | resolved | Resolved by routing audit queries through shared read authz with explicit Founder / Super Admin / Admin / Accountant access. |
| DL-20260411-03 | event/api/domain | `agos_app/app/models/lots.py`, `agos_app/app/services/lots.py`, `agos_app/app/api/routes/lots.py` | `docs/changelog/v1/openapi/agros-api-v1.0.yaml`, `docs/changelog/v1/architecture/naming-conventions.md`, `docs/changelog/v1/diagram/04-event-storming-event-map.md`, `CLAUDE.md` | `processing_batch` had temporarily shared the harvested-lot create contract and emitted `lot.harvest.created`. | Harvested Lot Core shipped before the dedicated processed-lot command and route were introduced. | resolved | Resolved by adding `CreateProcessedLotRequest`, `POST /api/v1/lots/processed`, and `lot.processed.created`, then syncing the owning docs. |
