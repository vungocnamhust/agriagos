---
name: docs-sync
description: "Check whether code changes require updates to architecture docs, diagrams, ADRs, README, or API docs, then prepare the smallest valid doc patch set."
argument-hint: "Describe the code change or changed files"
---

# Docs Sync

Use this skill after behavior, contract, or architecture changes.

## Procedure
1. Classify what changed: route, DTO, event, state machine, schema, or architecture.
2. Audit only the documents those changes can invalidate.
3. Prepare the minimum patch set needed to restore accuracy.
4. Flag when the change should be recorded as an ADR.

## Agri OS Surfaces To Review
- `CLAUDE.md`
- `system_v1.md`
- `determistic_layer_spec_v1.md`
- `event_desc.md`
- `deterministic_core_diagram.md`
- `docs/changelog/v1/architecture/`
- `docs/changelog/v1/diagram/`
- `docs/changelog/v1/adrs/`
