---
name: "Explore Plan Act"
description: "Inspect relevant files, summarize findings, propose a minimal plan, and only then implement. Use for fixes, refactors, or new code in Agri OS."
argument-hint: "Task goal and target files or symbols"
agent: "agent"
---

Use the Agri OS deterministic-core workflow.

1. Explore first: inspect the owning route, service, DTO, store, tests, and nearby docs.
2. Summarize current behavior, affected files, blast radius, and testing reality.
3. Propose a minimal ordered plan with risks and out-of-scope items.
4. Only after the plan is clear, implement the smallest viable change.
5. Validate with the narrowest available check.

When relevant, align with [CLAUDE.md](../../CLAUDE.md), [API guidance](../../agos_app/app/api/CLAUDE.md), and [docs guidance](../../docs/architecture/CLAUDE.md).
