---
name: doc-sync
description: >
  After code changes are merged or finalized, checks whether architecture docs,
  Mermaid diagrams, ADRs, README, and API docs need updating, then produces the
  smallest valid documentation patch set — only the lines that are now wrong or
  missing.
  Trigger when the user says "update the docs", "sync docs after this change",
  "what docs need updating", "check if docs are still accurate", or at the end
  of any implementation session that touched domain logic, routes, models,
  events, or the DB schema. Run this before every commit that changes behavior
  visible outside a single function.
---

# Doc Sync

After implementation, verify that documentation still accurately describes the
system. Produce only the changes that are now incorrect or absent — do not
rewrite docs that are still accurate.

The goal is a minimal patch: no reformatting, no style improvements, no
preemptive additions. If a section is correct, leave it alone.

---

## Phase 1 — Identify What Changed

Read the diff (or ask the user to describe changes if no diff is available).

Classify each change by type:

| Change type | Docs likely affected |
|-------------|---------------------|
| New endpoint added | README API surface, OpenAPI/Swagger docstrings, `router.py` comments |
| Endpoint removed or renamed | Same as above + any ADR if architectural |
| New domain entity or field | `CLAUDE.md` entity list, `minimal_requirement.md`, relevant model docstrings |
| State machine change | `deterministic_core_diagram.md` Mermaid diagrams, `determistic_layer_spec_v1.md` |
| New domain event | `event_desc.md`, `deterministic_core_diagram.md` |
| Architecture layer change | `system_v1.md`, `CLAUDE.md` Architecture section |
| DB schema change | Migration notes, any DDL reference in docs |
| Auth / RBAC change | `CLAUDE.md`, relevant route docstrings |
| New module or file added | `CLAUDE.md` Code Layout section |
| Dependency added/removed | `CLAUDE.md` Development Commands, `requirements.txt` notes |

If no change type matches any doc, output: "No documentation update required."
and stop.

---

## Phase 2 — Audit Each Affected Document

For each affected document, read the current content and compare it against the
actual code. Note only the specific lines or sections that are now wrong.

### 2.1 CLAUDE.md

Check these sections:

- **Domain Entities** — does the list still match the 8 canonical types, or
  were any added/removed/renamed?
- **Code Layout** — does the directory tree reflect the actual file structure?
- **API Surface** — does the route group list match `app/api/router.py`?
- **Development Commands** — are install/run commands still valid?
- **Key Design Principles** — did any change contradict a stated principle?
  (If yes, this may warrant an ADR rather than a doc edit.)

### 2.2 system_v1.md

Check if the 6-layer model description still accurately reflects the
implemented architecture. Flag any layer whose responsibilities changed.

### 2.3 determistic_layer_spec_v1.md

Check if module specs for the deterministic core match the current
implementation. Focus on: Command Gateway behavior, Application Service
responsibilities, Policy/Workflow Engine state transitions.

### 2.4 event_desc.md

For each domain event in the file:
- Does the event name still exist in the codebase?
- Does the payload description match the current Pydantic model?
- Are there new events not yet described?

### 2.5 deterministic_core_diagram.md

Check each Mermaid diagram:
- State machine diagrams: do the states and transitions match the current
  `status` enums and transition logic?
- Flow diagrams: does the write path / read path still match the implementation?

To verify a state machine, grep for `status` enum values in the relevant model
and compare against the diagram nodes.

### 2.6 README (if present)

Check:
- Setup instructions (commands, env vars, ports)
- Feature list or capability description
- Any architecture overview section

### 2.7 API docs (OpenAPI / docstrings)

Check FastAPI route files for:
- `summary=` and `description=` on route decorators — do they still describe
  what the handler actually does (even if it's a stub)?
- `response_model=` — does it match the current Pydantic model?
- Error response codes listed in `responses={}` — are they complete?
- Pydantic `Field(description=...)` annotations — are they accurate?

---

## Phase 3 — Prepare the Patch Set

For each document that needs updating, produce only the changed lines with
minimal context (3 lines before/after).

Format each patch as:

```
## Doc patch: <filename>
**Section:** <heading or line range>
**Reason:** <one sentence — what changed in code that made this wrong>

<old content, clearly marked>
→
<new content>
```

Do not patch sections that are still accurate.
Do not add new sections unless the change introduces something entirely absent.
Do not improve prose, fix grammar, or reformat — only correct what is wrong.

**Ordering:** Apply patches in this sequence to avoid inconsistency:
1. `event_desc.md` (events are the source of truth for behavior)
2. `deterministic_core_diagram.md` (diagrams derive from events + state machines)
3. `determistic_layer_spec_v1.md` (spec derives from diagrams)
4. `system_v1.md` (layer model is most stable, changes least)
5. `CLAUDE.md` (developer guide, reflects everything above)
6. Route docstrings / Pydantic Field descriptions (inline, apply last)
7. `README.md` (user-facing, most stable)

---

## Phase 4 — ADR Trigger Check

After preparing the patch set, ask: does any change represent an architectural
decision that should be recorded?

Flag for ADR if the change:
- Introduces a new architectural pattern not previously used in the codebase
- Reverses or supersedes a principle stated in `CLAUDE.md`
- Changes the domain event contract in a way that affects consumers
- Adds or removes an architectural layer
- Chooses one technology over another for a structural concern

If flagged, say: "This change may warrant an ADR. Use the `adr` skill to
record it before closing this task."

Do not write the ADR automatically — only flag it.

---

## Output Summary

End with a compact list:

```
## Doc Sync Summary

Patches prepared: <n>
- <filename> — <one-line description of what changed>
- ...

No update needed:
- <filename> — still accurate

ADR warranted: yes / no
  <if yes: one-line description of the decision to record>
```

---

## Hard Stops

Stop and ask before patching if:

- A section in the docs contradicts the code but also contradicts a core design
  principle (e.g. a route is doing direct DB mutations despite the event-first
  principle). The code may be wrong, not the doc.
- An event in `event_desc.md` no longer exists in the code but was referenced
  in an external integration doc. Removing it silently could mislead partners.
- The patch would change the public API description in a way that breaks the
  OpenAPI contract version.
