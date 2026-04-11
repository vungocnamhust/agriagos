# Agri OS Copilot Instructions

Agri OS is a deterministic-core FastAPI repository for agricultural supply chain operations. Treat `docs/changelog/v1/architecture/00-source-of-truth-registry.md` as the authority map for mutable architecture and contract facts. Use the registry to find the owning changelog doc, ADR, or OpenAPI artifact before relying on summaries in repo-level instruction files.

## Work Model

- Prefer small, local changes over broad refactors.
- Keep routes thin, services in control of business logic, and event emission in the service layer.
- Preserve the current deterministic-core design: AI and integration surfaces are advisory or translational, not canonical write-path owners.
- When instructions here are incomplete, consult the nearest architecture or rule file before searching broadly.
- Use prompt files for user-invoked task templates, skills for multi-step reusable workflows, and custom agents for narrow review or mapping roles.

## Bootstrap And Run

- Main app lives under `agos_app/`.
- Install dependencies from `agos_app/requirements.txt`.
- Start the API from `agos_app/` with `uvicorn app.main:app --reload`.
- Current runtime dependencies are minimal: FastAPI, Uvicorn, and Pydantic.

## Validation Reality

- There is no confirmed lint pipeline configured in this repo yet.
- There is no confirmed automated test suite configured in this repo yet.
- After edits, run the narrowest available validation for the files you touched.
- If no focused executable validation exists, inspect the diff carefully and call out the gap.
- If you edit route, DTO, migration, or architecture files, also verify contract and documentation drift.

## Pull Request Expectations

- Keep diffs narrow and easy to review.
- Update paired artifacts together: routes with DTOs, contracts, and docs; migrations with data-model docs; architecture changes with ADRs or diagrams when required.
- State clearly what was validated and what could not be validated.
- Prefer backward-compatible API changes unless a new versioned contract is introduced.

## Documentation Discipline

- Do not duplicate architecture prose from `CLAUDE.md` into new Copilot files.
- Keep `.github/` guidance workflow-focused. For mutable facts such as domain ownership, state names, event names, permissions, and API contract shape, reference the owning doc from `docs/changelog/v1/architecture/00-source-of-truth-registry.md` instead of restating the fact locally.
- If code changes affect events, state transitions, domain ownership, or architectural boundaries, update the relevant docs in the same change.
- Keep OpenAPI or contract artifacts aligned when route or DTO behavior changes.
- When a short summary is enough, point back to the authoritative architecture files instead of creating a second canon in `.github/`.

## Never Do

- Do not move business logic into `agos_app/app/api/routes/`.
- Do not import integration schemas into `agos_app/app/core/` or `agos_app/app/store/`.
- Do not treat vendor IDs as canonical internal IDs.
- Do not silently change public field names, event names, or ownership boundaries.
- Do not rewrite large documentation sections when a minimal correction is enough.