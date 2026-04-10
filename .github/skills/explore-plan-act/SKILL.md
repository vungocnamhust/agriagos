---
name: explore-plan-act
description: "Explore relevant files, plan the smallest change, then act. Use for implementing, fixing, refactoring, or updating behavior in Agri OS before editing code."
argument-hint: "Task goal and target files or symbols"
---

# Explore Plan Act

Use this skill when a change touches code or documented behavior.

## Procedure
1. Explore the owning route, service, DTO, store, tests, and nearby docs.
2. Summarize current behavior, affected files, blast radius, and testing reality.
3. Write a minimal implementation plan with ordered steps, risks, and out-of-scope items.
4. Implement only after the plan is stable.
5. Validate with the narrowest available check and report any gaps.

If no tests exist for the touched slice, say so explicitly and use the cheapest meaningful validation available.

## Agri OS Constraints
- Keep routes thin and services authoritative.
- Preserve contract-first behavior for API changes.
- Check docs and contract drift if behavior moves across boundaries.
