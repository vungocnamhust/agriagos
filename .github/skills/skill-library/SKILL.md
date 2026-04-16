---
name: skill-library
description: "Route occasional Agri OS tasks to the right library-only agent or specialist lane. Use when the task needs architecture review, code cleanup, performance analysis, comment review, reliability audit, Python-specific review, or a library/framework docs lookup that is not part of the default delivery pipeline."
argument-hint: "Describe the task and why the default pipeline is not enough"
---

# Skill Library Router

Use this skill when the task does not fit the default Agri OS delivery lane but still needs a specialist from the `library` bucket.

Default rule:

- Stay on the repo-local pipeline first.
- Reach for this router only when the task clearly needs a library-only specialist.
- Do not use this router for agents already in the repo-local default path.

## Daily vs Library

- `daily`: repo-local workflow skills and repo-local review agents already preferred by `.github/agent-invocation-policy.md`
- `library`: useful specialists that should stay available, but not load into the normal delivery decision path by default

## When To Use This Router

Use this skill for one of these task shapes:

- broad architecture tradeoff or system-design review
- large feature blueprint or implementation sketch beyond the normal plan
- code cleanup or simplification pass after behavior is already stable
- performance investigation or optimization task
- Python-specific quality review outside repo-local boundary or contract concerns
- comment accuracy or comment rot audit
- silent-failure or reliability audit
- external framework or library docs lookup

## Routing Table

| Need | Route to |
|---|---|
| Big-picture architecture tradeoff | `architect` |
| Large feature blueprint | `code-architect` |
| Generic code cleanup after implementation | `code-simplifier` or `refactor-cleaner` |
| Performance bottleneck or slow query/app path | `performance-optimizer` |
| Python-specific review beyond repo-local review | `python-reviewer` |
| Comment audit | `comment-analyzer` |
| Reliability or swallowed-error audit | `silent-failure-hunter` |
| Type or model-shape critique | `type-design-analyzer` |
| Framework or vendor docs lookup | `docs-lookup` |

## Do Not Route Here

Do not use this router for:

- `Contract Guardian`
- `Implementation Reviewer`
- `Integration Mapper`
- `explore-plan-act`
- `impact-analysis`
- `docs-sync`
- `tdd-guide`
- `security-reviewer`
- `database-reviewer`

Those are already covered by the default Agri OS policy and should stay outside the library router.

## How To Invoke

Give two things:

1. the task shape
2. why the default pipeline is not enough

Example inputs:

- `Need a cleanup pass after a stable feature landed; looking for dead code and simplification opportunities.`
- `Need docs lookup for current FastAPI response-model behavior before changing a route contract.`
- `Need a reliability audit for silent failures around retries and exception handling.`

## Operating Guardrails

- Pick one library lane first; do not stack several library agents unless the first pass reveals a concrete second need.
- When the task moves back into normal delivery, return to `.github/agent-invocation-policy.md`.
- Treat `.github/global-agent-inventory.md` as the source of truth for what is `keep`, `library`, and `ignore`.