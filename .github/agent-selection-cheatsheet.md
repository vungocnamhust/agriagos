# Agri OS Agent Quick Pick

Use this one-screen table when choosing the agent lane for a task.
For full rationale and edge cases, see `.github/agent-invocation-policy.md`.

| Task shape | Start with | End with | Add only when needed |
|---|---|---|---|
| Small local fix | `explore-plan-act` | `Implementation Reviewer` | `Contract Guardian` if route/DTO/schema/docs-visible behavior changed |
| Standard feature | `explore-plan-act` | `Implementation Reviewer` | `impact-analysis` for multi-surface blast radius; `Contract Guardian` + `docs-sync` for API/docs drift |
| API contract change | `impact-analysis` | `Contract Guardian` -> `Implementation Reviewer` | `docs-sync` |
| Write-path bug or new write behavior | `explore-plan-act` | `Implementation Reviewer` | `impact-analysis` for multi-aggregate/event changes; `tdd-guide`; `Contract Guardian`; `docs-sync` |
| Authz or security change | `impact-analysis` | `security-reviewer` -> `Implementation Reviewer` | `Contract Guardian`; `docs-sync` |
| PostgreSQL, migration, SQL-heavy work | `impact-analysis` | `database-reviewer` -> `Implementation Reviewer` | `Contract Guardian`; `docs-sync` |
| Integration or anti-corruption work | `impact-analysis` | `Integration Mapper` -> `Implementation Reviewer` | `integration-audit`; `security-reviewer` |
| Architecture or domain-boundary change | `planner` | `Contract Guardian` -> `Implementation Reviewer` | `domain-architect`; `docs-sync` |
| Docs-only or workflow-guidance change | local read of owning guidance | no default reviewer | `docs-sync` only if mutable architecture facts are involved |

## Hard Limits

- Small fix: max 2 agent lanes
- Standard feature: usually 3 lanes
- High-risk feature: usually 4 lanes
- More than 4 lanes needs an explicit reason in the PR or task notes

## Anti-Patterns

- Do not stack `planner`, `tdd-guide`, `security-reviewer`, `database-reviewer`, `Contract Guardian`, and `Implementation Reviewer` on the same small fix.
- Do not use generic global reviewers when the repo-local agent already covers the lane.
- Do not skip `Contract Guardian` after route or DTO changes just because tests pass.
- Do not skip `docs-sync` when events, OpenAPI, or architecture guidance moved.