---
name: adr
description: >
  Writes Architecture Decision Records (ADRs) with context, decision,
  trade-offs, alternatives considered, and migration impact.
  Trigger when the user says "write an ADR for", "document this decision",
  "record the architecture decision about", "we decided to use X instead of Y",
  or when a significant technical choice is being finalized.
  ADRs must be concise (under 400 words body), architecture-focused, and
  immutable once written — supersede rather than edit.
---

# Architecture Decision Records

An ADR captures *why* a decision was made, not just *what* was decided.
Future readers need to understand the constraints and forces at play at the
time — so they can judge whether those constraints still hold before reversing
the decision.

Keep it short. If a section needs more than 3–4 sentences, you're writing a
design doc, not an ADR.

---

## Before Writing

Ask the user for anything missing:

1. **What is the decision?** One sentence: "We will use X for Y."
2. **What forced this decision now?** (deadline, discovered constraint,
   blocked work, explicit requirement)
3. **What alternatives were seriously considered?** (at least two, or note
   that none existed)
4. **Is this reversible?** If yes, what would trigger revisiting it?
5. **Does this affect existing code, data, or contracts?** Migration needed?

If the user can't answer 1–3, the decision isn't ready to record. Say:
"This decision needs more clarity before it can be recorded. What specifically
are we committing to?"

---

## ADR File Naming

Save to `docs/adr/` (create if absent).
Filename: `ADR-<NNN>-<kebab-case-title>.md`

To get the next number:
- Count existing files in `docs/adr/` matching `ADR-*.md`.
- Increment by 1, zero-padded to 3 digits.

---

## ADR Template

```markdown
# ADR-<NNN>: <Title — one concise phrase>

**Date:** <YYYY-MM-DD>
**Status:** Proposed | Accepted | Superseded by ADR-<NNN>
**Deciders:** <who was in the room / async thread>

---

## Context

<2–4 sentences. The forces, constraints, and problem that made this decision
necessary. Be specific: what was breaking, blocked, or missing? Avoid
restating the decision here.>

## Decision

<1–3 sentences. State the choice plainly. Start with "We will…" or
"This system will…". Include the scope (which module, layer, or service).>

## Trade-offs

**Gains:**
- <concrete benefit — performance, simplicity, consistency, velocity>
- <another gain if real>

**Costs:**
- <concrete cost — complexity added, flexibility lost, migration effort>
- <another cost if real>

Do not list imaginary gains or hypothetical costs. Only what is actually
expected given the current context.

## Alternatives Considered

| Alternative | Why Rejected |
|-------------|-------------|
| <option A> | <one-line reason — too complex, wrong abstraction, cost, etc.> |
| <option B> | <one-line reason> |

If only one alternative existed or no viable alternatives were found, state
that explicitly rather than inventing options.

## Migration Impact

**Scope:** <None | Low | Medium | High>

<If None: "No existing code, data, or contracts are affected.">

<If Low–High: describe what must change>
- Code: <files or modules that must be updated>
- Data: <schema changes, backfills, or data transformations needed>
- Contracts: <API or event schema changes visible to consumers>
- Deployment: <sequencing requirements, feature flags, rollout notes>

## Revisit Conditions

<When should this decision be revisited? Be specific: a volume threshold,
a new integration requirement, a framework version, a team size change.
If the decision is effectively irreversible, say so and explain why.>
```

---

## After Writing

1. If **Status: Proposed** — note that it becomes **Accepted** once
   the relevant team members confirm.
2. If this supersedes an older ADR — update the older file's status line to
   `Superseded by ADR-<NNN>` and add a link. Do not edit the older ADR's
   body.
3. Add a one-line entry to `docs/adr/README.md` (create if absent):
   `| ADR-<NNN> | <Title> | <YYYY-MM-DD> | Accepted |`

---

## Scope Guard

ADRs record architectural decisions: choice of technology, data model strategy,
API versioning policy, event schema contracts, domain boundary placement,
infrastructure topology, security model.

ADRs do **not** record: implementation details, coding conventions, sprint
decisions, bug fixes, or operational runbooks. If the user asks to write an ADR
for something in that category, suggest the appropriate document type instead.
