# Documentation Sync Rules

These rules apply whenever a change affects architecture, domain boundaries,
events, state transitions, or any documented behavior that other engineers may
reason about from the docs. Documentation is part of the deliverable, not a
follow-up task.

Before deciding which doc to update, resolve the owning authority document
through `docs/changelog/v1/architecture/00-source-of-truth-registry.md`.
Repo-level summaries and local rule files are enforcement aids, not the first
authority for mutable architecture facts.

## 1. ADR Updates Are Mandatory for Architecture-Impacting Changes

Any change that alters an architectural decision must update the ADR record
before the task is considered complete.

**ADR-worthy changes include:**
- adding, removing, or collapsing an architectural layer
- changing a bounded context responsibility or source-of-truth owner
- introducing or replacing a core technical pattern
- changing domain event contracts consumed across boundaries
- changing write-path guarantees, workflow orchestration, or policy enforcement
- reversing or superseding a principle already recorded in `docs/changelog/v1/adrs/`

**Required action:**
- add a new ADR when the decision is new
- add a superseding ADR when an earlier ADR is no longer authoritative
- update any ADR index or cross-reference that points readers to the wrong decision

Do not leave an outdated ADR in place when the code now follows a different
architecture.

## 2. Refresh Diagrams When Domain Boundaries Change

If a change affects domain ownership, cross-domain coordination, aggregate
boundaries, event flow, or state transitions, refresh the diagrams in the same
change set.

**Trigger examples:**
- a field or responsibility moves from one canonical entity to another
- a synchronous service interaction becomes event-driven, or the reverse
- a new integration or anti-corruption layer changes context boundaries
- a state machine gains, removes, or renames a state or transition
- an order, lot, preorder, customer, or farm flow changes its event sequence

**Diagrams to review explicitly:**
- `deterministic_core_diagram.md`
- `docs/changelog/v1/diagram/`
- any Mermaid diagram embedded in architecture or glossary documents

Do not update prose only and leave boundary or flow diagrams stale.

## 3. Intentional Code-Doc Divergence Must Be Explicit

If code intentionally diverges from the current documentation, the divergence
must be called out explicitly in the same change.

Record every such divergence in `docs/changelog/v1/divergence-ledger.md`.
Local notes in doc sections or TODOs may add context, but the ledger is the
central index.

**A valid divergence note must state:**
- what is intentionally different in the code
- which document or diagram is temporarily inaccurate
- why the divergence exists
- whether it is temporary or permanent
- the condition, follow-up task, or date that will remove the divergence

Put this note in the most visible local place for the affected audience:
- the relevant doc section
- `docs/changelog/v1/divergence-ledger.md`
- a TODO with a linked tracking item when the docs cannot yet be updated fully

Silent drift is prohibited. If the docs are knowingly wrong, say so plainly.

## 4. Required Documentation Surface

When one of the triggers above applies, review at least these artifacts:

- `docs/changelog/v1/architecture/00-source-of-truth-registry.md`
- `docs/changelog/v1/divergence-ledger.md`
- `CLAUDE.md`
- `README.md` and module-level README files
- `system_v1.md`
- `determistic_layer_spec_v1.md`
- `event_desc.md`
- `deterministic_core_diagram.md`
- `docs/changelog/v1/architecture/`
- `docs/changelog/v1/diagram/`
- `docs/changelog/v1/adrs/`

If an artifact remains accurate, leave it unchanged. If it becomes inaccurate,
update it in the same branch.

## 5. Update Order

Apply documentation changes in this order to keep the repo internally
consistent:

1. ADRs that record the decision
2. architecture docs that define ownership and boundaries
3. diagrams that visualize the architecture and flows
4. event and state-machine references
5. developer-facing summaries such as `CLAUDE.md` and README files

If this order cannot be followed, add an explicit divergence note describing why.

## 6. Resolve Documentation Conflicts Manually

When a merge or rebase produces documentation conflicts, resolve them manually.
Do not accept `ours` or `theirs` blindly for ADRs, architecture docs, diagrams,
or changelog entries.

- preserve both edits when both still describe current code truthfully
- if one change supersedes the other, keep the superseding version and update
	the ADR or divergence note accordingly
- re-check document cross-references after conflict resolution
- re-check any affected diagrams so the visual flow still matches the merged docs

## Checklist Before Closing

- [ ] Architecture-impacting changes have a new or superseding ADR
- [ ] Domain-boundary or state-flow changes have refreshed diagrams
- [ ] Any intentional code-doc mismatch is documented explicitly
- [ ] Every intentional mismatch is recorded in `docs/changelog/v1/divergence-ledger.md`
- [ ] Core architecture docs were reviewed for drift
- [ ] No stale diagram or ADR remains that contradicts the implemented behavior