## Summary

- What changed:
- Why:

## Agent Lane Used

| Task shape | Default lane |
|---|---|
| Small local fix | `explore-plan-act` -> `Implementation Reviewer` |
| API contract change | `impact-analysis` -> `explore-plan-act` -> `Contract Guardian` -> `Implementation Reviewer` -> `docs-sync` |
| Write-path bug or new write behavior | `explore-plan-act` -> `tdd-guide` when needed -> `Implementation Reviewer` |
| Authz or security change | `impact-analysis` -> `explore-plan-act` -> `security-reviewer` -> `Implementation Reviewer` |
| PostgreSQL or migration work | `impact-analysis` -> `explore-plan-act` -> `database-reviewer` -> `Implementation Reviewer` -> `docs-sync` |
| Integration work | `impact-analysis` -> `explore-plan-act` -> `Integration Mapper` -> `Implementation Reviewer` |

Reference:
- `.github/agent-selection-cheatsheet.md`
- `.github/agent-invocation-policy.md`

## Validation

- Commands or tests run:
- What was not validated:

## Contract And Docs

- [ ] No public contract changed
- [ ] `Contract Guardian` review completed when route/DTO/schema/OpenAPI changed
- [ ] `docs-sync` completed when docs, diagrams, ADRs, or divergence notes changed