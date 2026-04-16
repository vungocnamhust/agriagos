# Global Agent Inventory For Agri OS

This inventory classifies global agents into `keep`, `library`, or `ignore`
for this repository.

## Stack Evidence

- Python-only runtime: `FastAPI`, `Pydantic`, `SQLAlchemy`, `Alembic`, `psycopg` in `agos_app/requirements.txt`
- Test stack: `pytest` and `httpx` in `agos_app/requirements-dev.txt`
- Repo-local workflow depends heavily on service-layer idempotency, domain events, DTO contracts, OpenAPI sync, and docs sync under `agos_app/app/`, `agos_app/tests/`, and `docs/changelog/v1/`
- Repo-local custom agents already exist for contract, implementation, and integration lanes under `.github/agents/`

## Keep

These are worth keeping in the working set because they match the repo stack or fill a real gap not covered by a repo-local agent.

| Agent | Why keep |
|---|---|
| `planner` | Useful for multi-phase features and multi-domain refactors in a docs-heavy deterministic-core repo |
| `tdd-guide` | Matches the repo's pytest-heavy write-path and regression workflow |
| `security-reviewer` | Needed for authz, request boundary, external call, and trust-boundary work |
| `database-reviewer` | Needed for Alembic, PostgreSQL views, constraints, and SQL-heavy store slices |
| `domain-architect` | Useful when aggregate ownership, event flow, or bounded contexts move |
| `code-explorer` | Useful when tracing a non-obvious cross-layer flow before changing it |
| `docs-lookup` | Useful for current vendor/library docs when repo work depends on external framework behavior |

## Library

These are occasionally useful, but they should not be in the default decision path for Agri OS work.

| Agent | Why library |
|---|---|
| `architect` | Too broad for normal slice work; use only for bigger system decisions |
| `code-architect` | Useful for large feature blueprints, not routine FastAPI/service changes |
| `code-reviewer` | Superseded by repo-local `Implementation Reviewer` for most work |
| `code-simplifier` | Helpful after noisy refactors, not for default delivery flow |
| `comment-analyzer` | Useful only when comment accuracy is the task |
| `doc-updater` | Repo already has local docs workflow and docs-sync surfaces |
| `performance-optimizer` | Use only when there is an actual performance problem |
| `python-reviewer` | Useful as a Python-specific second opinion, but repo-local review is more valuable by default |
| `refactor-cleaner` | Useful for cleanup passes, not feature delivery |
| `silent-failure-hunter` | Useful for reliability audits, not default execution |
| `type-design-analyzer` | Useful for model/API design reviews, not default slice work |

## Ignore

These should be ignored by default in this repo because they are off-stack, duplicated by repo-local agents, or mismatched to the current workflow.

| Agent | Why ignore |
|---|---|
| `build-error-resolver` | TS/build oriented; not a default fit for this Python repo |
| `contract-guardian` | Superseded by repo-local `Contract Guardian` |
| `implementation-reviewer` | Superseded by repo-local `Implementation Reviewer` |
| `integration-mapper` | Superseded by repo-local `Integration Mapper` |
| `conversation-analyzer` | Not part of product delivery in this repo |
| `e2e-runner` | Browser-heavy E2E lane is not part of the current FastAPI-only repo workflow |
| `flutter-reviewer` | Off-stack |
| `gan-evaluator` | Off-workflow |
| `gan-generator` | Off-workflow |
| `gan-planner` | Off-workflow |
| `harness-optimizer` | Harness-focused, not repo delivery-focused |
| `healthcare-reviewer` | Wrong domain |
| `loop-operator` | Not part of the current repo workflow |
| `opensource-forker` | Not relevant to normal repo work |
| `opensource-packager` | Not relevant to normal repo work |
| `opensource-sanitizer` | Not relevant to normal repo work |
| `typescript-reviewer` | Off-stack |

## Operating Rule

- Default to repo-local agents first.
- Pull from `Keep` when the task genuinely matches the lane.
- Reach into `Library` only with a concrete reason.
- When a library lane is needed, route through `.github/skills/skill-library/SKILL.md` instead of picking directly from the full global list.
- Treat `Ignore` as unavailable unless the task explicitly changes scope.