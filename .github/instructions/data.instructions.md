---
description: "Use when editing DDL, migration-like files, canonical data model docs, or source-of-truth data shapes. Enforces safe schema evolution, naming consistency, explicit index choices, and no duplicated ownership."
applyTo: "docs/changelog/v1/ddl/**/*.sql,alembic/**/*.py,docs/changelog/v1/architecture/04-canonical-data-model.md,docs/changelog/v1/architecture/10-assumptions-and-migration-path.md"
---

# Data Instructions

- Treat `.claude/rules/canonical-model.md` as the detailed authority for ownership and source-of-truth boundaries.
- Treat canonical ownership as a hard boundary. Do not duplicate truth that already belongs to another aggregate.
- Keep schema changes explicit and easy to review: what changed, why, and what docs move with it.
- Prefer additive, low-risk schema evolution. If a change is not safely reversible, call that out.
- Add indexes intentionally, not by habit. Every new index should serve a concrete query or workflow.
- When data model semantics change, update the canonical model docs and migration-path docs in the same task.
