---
name: "Docs Sync"
description: "Compare a code change against architecture docs, diagrams, ADRs, README, and API docs, then propose the minimum doc patch set needed to stay accurate."
argument-hint: "Describe the change or provide changed files"
agent: "agent"
---

Audit documentation drift for the described change.

Start by resolving the owning authority doc through `docs/changelog/v1/architecture/00-source-of-truth-registry.md`. Treat repo-level summaries as secondary references only.

Check at least:
- `docs/changelog/v1/architecture/00-source-of-truth-registry.md`
- `CLAUDE.md`
- `system_v1.md`
- `determistic_layer_spec_v1.md`
- `event_desc.md`
- `deterministic_core_diagram.md`
- `docs/changelog/v1/architecture/`
- `docs/changelog/v1/diagram/`
- `docs/changelog/v1/adrs/`

Return only the minimum patch set needed to restore accuracy.
