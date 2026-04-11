# Source Of Truth Registry

This registry defines which checked-in documents are authoritative for each concern in Agri OS.

Use it when writing or updating:
- Copilot instructions
- Claude rules, skills, prompts, and session context
- architecture docs and ADRs
- route, DTO, migration, and integration guidance

Use `docs/changelog/v1/divergence-ledger.md` as the central register for intentional code-doc mismatches.

## Core Rule

Mutable product and architecture facts must come from the changelog documentation set, not from duplicated summaries in instruction files.

Instruction surfaces may summarize the workflow, but they must reference this registry for authority and must not restate changeable runtime facts unless the fact is a stable invariant.

If code and docs diverge intentionally, record that divergence explicitly instead of teaching the instruction surface the temporary code shape.

## Authority By Concern

| Concern | Authoritative Surface | Notes |
|---|---|---|
| Architecture baseline | `docs/changelog/v1/architecture/` | Working baseline for current deterministic-core decisions |
| Architecture decisions | `docs/changelog/v1/adrs/` | ADRs record why a decision exists; supersede instead of silently rewriting history |
| Public API contract | `docs/changelog/v1/openapi/agros-api-v1.0.yaml` | Route and DTO changes must keep this artifact in sync |
| Domain ownership and glossary | `docs/changelog/v1/architecture/03-domain-glossary.md`, `docs/changelog/v1/architecture/04-canonical-data-model.md` | Use canonical names and ownership from these docs |
| Event catalog and naming | `docs/changelog/v1/architecture/05-event-catalog.md`, `docs/changelog/v1/architecture/naming-conventions.md` | Runtime/event prose must match these docs |
| State transitions | `docs/changelog/v1/architecture/06-state-transitions.md` | State names and allowed transitions should be described here first |
| Permissions and role views | `docs/changelog/v1/architecture/07-permission-matrix.md` | Role-facing behavior must align here |
| Integration boundaries | `docs/changelog/v1/architecture/08-integration-contracts.md` | External-system guidance must not outrank this contract |
| AI and agent boundaries | `docs/changelog/v1/architecture/09-ai-agent-boundaries.md` | AI remains advisory unless a newer ADR says otherwise |
| Migration and rollout assumptions | `docs/changelog/v1/architecture/10-assumptions-and-migration-path.md` | Schema evolution and rollout guidance must stay aligned here |
| Architecture diagrams | `docs/changelog/v1/diagram/` | Visual flows must agree with the architecture baseline and ADRs |

## Repo-Root Docs And Their Role

These files remain required review surfaces, but they are derived summaries or companion references unless this registry says otherwise:

| File | Role |
|---|---|
| `system_v1.md` | High-level system vision and layer narrative; update when changelog architecture docs make it stale |
| `determistic_layer_spec_v1.md` | Deterministic-core module summary derived from the architecture baseline |
| `event_desc.md` | Event narrative companion; keep aligned with the owning changelog event/state docs |
| `deterministic_core_diagram.md` | Repo-root diagram companion; keep aligned with `docs/changelog/v1/diagram/` |
| `CLAUDE.md` and `AGENTS.md` | Developer-facing index and workflow summary; not primary authority for mutable product facts |

## Secondary And Derived Surfaces

These files are important, but they are not the first authority for mutable product facts:

- `CLAUDE.md`
- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.github/instructions/*.instructions.md`
- `.github/prompts/*.prompt.md`
- `.github/skills/*/SKILL.md`
- `.claude/rules/*.md`
- `.claude/contexts/*.md`

They should point back to the authoritative surfaces above instead of carrying their own copy of runtime facts.

## Implementation Reality Checks

Code is used to validate that the documented architecture is still true, not to replace the registry above.

Use code primarily for these checks:
- confirm whether the implementation matches the documented contract
- identify undocumented drift that now requires a docs patch
- gather local detail needed to update the authoritative docs

Do not promote a code snapshot into instructions as a new source of truth without updating the authoritative docs in the same change.

## Rules For Instruction Authors

When editing any instruction, prompt, rule, skill, or session context:

1. Name the concern you are governing.
2. Reference the authoritative doc from this registry.
3. Keep the instruction focused on workflow and enforcement, not on mutable product facts.
4. If a mutable fact must be mentioned, also point to the authority doc that owns it.
5. If the fact is intentionally out of sync with code, add or update the explicit divergence note instead of copying the code behavior into the instruction.