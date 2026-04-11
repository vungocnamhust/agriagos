---
name: docs-sync
description: "Check whether code changes require updates to architecture docs, diagrams, ADRs, README, or API docs, then prepare the smallest valid doc patch set."
argument-hint: "Describe the code change or changed files"
---

# Docs Sync

Use this skill after behavior, contract, or architecture changes.

## Procedure
1. Resolve the owning authority doc through `docs/changelog/v1/architecture/00-source-of-truth-registry.md` before trusting repo-level summaries or code comments.
2. Classify what changed: route, DTO, event, state machine, schema, or architecture.
3. Audit only the documents those changes can invalidate.
4. Prepare the minimum patch set needed to restore accuracy.
5. Flag when the change should be recorded as an ADR.

## Agri OS Surfaces To Review
- `docs/changelog/v1/architecture/00-source-of-truth-registry.md`
- `CLAUDE.md`
- `system_v1.md`
- `determistic_layer_spec_v1.md`
- `event_desc.md`
- `deterministic_core_diagram.md`
- `docs/changelog/v1/architecture/`
- `docs/changelog/v1/diagram/`
- `docs/changelog/v1/adrs/`
