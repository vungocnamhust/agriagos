---
name: explore-plan-act
description: "Explore relevant files, plan the smallest change, then act. Use for implementing, fixing, refactoring, or updating behavior in Agri OS before editing code."
argument-hint: "Task goal and target files or symbols"
---

# Explore Plan Act

Use this skill when a change touches code or documented behavior.

## Procedure
1. Resolve the owning authority doc through `docs/changelog/v1/architecture/00-source-of-truth-registry.md`.
2. Explore the owning route, service, DTO, store, tests, and nearby docs.
3. Summarize current behavior, affected files, blast radius, and testing reality.
4. Write a minimal implementation plan with ordered steps, risks, and out-of-scope items.
5. Implement only after the plan is stable.
6. Validate with the narrowest available check and report any gaps.

If no tests exist for the touched slice, say so explicitly and use the cheapest meaningful validation available.

## Agri OS Constraints
- Keep routes thin and services authoritative.
- Preserve contract-first behavior for API changes.
- Use repo-level summaries only after the owning changelog doc is known.
- Check docs and contract drift if behavior moves across boundaries.
