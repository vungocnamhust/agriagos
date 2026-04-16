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
| DL-20260416-02 | permission/domain | `agos_app/app/services/project_contributions.py`, `agos_app/app/api/routes/project_scopes.py` | `docs/changelog/v1/architecture/07-permission-matrix.md` | Runtime project contribution write lane is still limited to `founder` / `super_admin` / `admin`, while the ProjectScope baseline policy already describes the broader target domain-owner lane for future rollout. | The current epic is separating authority layers and hardening contribution verification first; widening contribution writes before the authority model and grant rollout would blur context and authority semantics. | open | Resolved when project contribution write roles expand deliberately to the approved domain-owner lane, or when the baseline policy is revised to keep the narrower scope. |
| DL-20260416-01 | architecture/domain | `agos_app/app/**`, `agos_app/alembic/**` | `docs/changelog/v1/adrs/ADR-013-projectscope-is-the-soft-value-stream-scope.md`, `docs/changelog/v1/architecture/03-domain-glossary.md`, `docs/changelog/v1/architecture/04-canonical-data-model.md`, `docs/changelog/v1/architecture/05-event-catalog.md`, `docs/changelog/v1/architecture/06-state-transitions.md`, `docs/changelog/v1/architecture/07-permission-matrix.md`, `docs/changelog/v1/architecture/10-assumptions-and-migration-path.md`, `docs/changelog/v1/diagram/03-canonical-data-model-erd.md`, `docs/changelog/v1/diagram/04-event-storming-event-map.md`, `docs/changelog/v1/diagram/08-role-based-view-permission-diagram.md` | Runtime now includes the first economics lane (`CostRecord` from confirmed contributions) and the first ProjectScope reporting slice (`/api/v1/views/project-contribution-summary`), matching the rollout condition the docs previously marked as pending. | The docs and runtime were intentionally staged so contribution facts could land before economics/reporting. That staging gap is now closed. | resolved | Resolved by shipping the first cost-record lane and contribution summary reporting slice, then syncing the owning docs. |
| DL-20260415-01 | architecture/domain | `agos_app/app/**`, `agos_app/alembic/**` | `docs/changelog/v1/adrs/ADR-012-organization-is-legal-operating-owner-tenant-remains-deployment-boundary.md`, `docs/changelog/v1/architecture/03-domain-glossary.md`, `docs/changelog/v1/architecture/04-canonical-data-model.md`, `docs/changelog/v1/architecture/08-integration-contracts.md`, `docs/changelog/v1/architecture/10-assumptions-and-migration-path.md` | Runtime hiện đã có standalone `organizations` schema, CRUD, state actions, event emission, additive `organization_id` propagation cho canonical farm/commercial records, current Phase 1 read-model surfaces, và `external_mappings` schema baseline. Divergence còn lại là integration sync jobs và adapter-facing flows chưa rollout hết; runtime service/API/store cho external mapping registration và lookup vẫn đang defer. | PR-1 khóa decision trước, các slice tiếp theo đang rollout dần thay vì mutate toàn bộ Phase 1 schema trong một bước. | open | Resolved when remaining integration sync/adapters `organization_id` rollout slices land và external mapping runtime lane xuất hiện, hoặc khi architecture decision bị supersede. |

## Resolved Entries

| ID | Concern | Code Surface | Doc Surface | Divergence | Why | Status | Exit Condition |
|---|---|---|---|---|---|---|---|
| DL-20260412-02 | permission/api | `agos_app/app/services/orders.py`, `agos_app/app/models/orders.py`, `agos_app/app/api/routes/orders.py` | `docs/changelog/v1/architecture/07-permission-matrix.md`, `docs/changelog/v1/openapi/agros-api-v1.0.yaml` | Packed-or-later order cancel had been role-gated without enforcing approval evidence such as `approvalRef`, even though the docs classified that path as approval-required. | PR5 initially landed the shared order authz rollout before the approval/escalation contract was wired into `order.cancel`. | resolved | Resolved by enforcing `approvalRef` for packed-or-later cancel, escalating with `reason_code=approval_required` when missing, and syncing the owning docs. |
| DL-20260412-01 | api/permission | `agos_app/app/api/routes/audit.py`, `agos_app/app/api/router.py` | `docs/changelog/v1/architecture/07-permission-matrix.md`, `docs/changelog/v1/diagram/08-role-based-view-permission-diagram.md` | `GET /api/v1/audit` existed as a public read-only route before role-based gateway/auth enforcement was implemented. | Phase 1 needed operator/debug readback before the shared read-auth seam landed. | resolved | Resolved by routing audit queries through shared read authz with explicit Founder / Super Admin / Admin / Accountant access. |
| DL-20260411-03 | event/api/domain | `agos_app/app/models/lots.py`, `agos_app/app/services/lots.py`, `agos_app/app/api/routes/lots.py` | `docs/changelog/v1/openapi/agros-api-v1.0.yaml`, `docs/changelog/v1/architecture/naming-conventions.md`, `docs/changelog/v1/diagram/04-event-storming-event-map.md`, `CLAUDE.md` | `processing_batch` had temporarily shared the harvested-lot create contract and emitted `lot.harvest.created`. | Harvested Lot Core shipped before the dedicated processed-lot command and route were introduced. | resolved | Resolved by adding `CreateProcessedLotRequest`, `POST /api/v1/lots/processed`, and `lot.processed.created`, then syncing the owning docs. |
