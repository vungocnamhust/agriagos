---
name: explore-plan-act
description: >
  Enforces a disciplined Explore → Plan → Act workflow before touching any code.
  Use this skill whenever the task involves modifying, refactoring, fixing, or
  adding code — especially when the change spans multiple files, involves domain
  logic, or when the scope is unclear. Trigger phrases: "implement", "fix",
  "refactor", "add feature", "change how X works", "update the logic for".
  Do not skip the exploration or planning phases even if the task seems simple —
  rushing to edit is the most common source of regressions.
---

# Explore → Plan → Act

This skill enforces a three-phase workflow: understand first, plan second, code
third. The goal is to prevent blind edits that break things the author didn't
know were connected.

---

## Phase 1 — Explore

Before writing a single line of code, build a clear picture of the territory.

**What to do:**
- Read every file directly related to the task (models, services, routes,
  tests, config).
- Search for all call sites, imports, and usages of the symbol being changed.
- Check for existing tests — they reveal intended behavior better than comments.
- Scan for related domain events, schemas, or contracts that the change might
  affect.
- Note any TODOs, stubs, or `# placeholder` markers in the vicinity.

**End condition for Phase 1:**  
You can answer these questions without looking at any file again:
1. What does the current code do?
2. What files will definitely change?
3. What files might be affected but aren't changing?
4. Are there tests? Do they cover the area being changed?

**Exploration summary (required output before moving on):**

```
## Exploration Summary
- Files read: <list>
- Key symbols: <functions / classes / events relevant to the task>
- Current behavior: <1–3 sentences>
- Potential blast radius: <files / modules that could break>
- Test coverage: <exists / partial / none — and what they cover>
- Open questions: <anything still unclear>
```

If open questions remain, resolve them (read more files, grep for usages) before
continuing. Do not proceed to Phase 2 with unresolved unknowns.

---

## Phase 2 — Plan

Translate the exploration findings into a concrete, ordered list of changes.

**What to do:**
- State the approach in one sentence.
- List every file that will be edited, in the order you will edit them.
- For each file, describe the change at the function/class level — not line
  level, but specific enough that someone else could implement it.
- Identify any risks or tradeoffs.
- Flag changes that require a migration, schema update, or event contract change.

**End condition for Phase 2:**  
The plan is specific enough that you could hand it to another engineer and they
would produce the same implementation.

**Plan output (required before editing any file):**

```
## Implementation Plan

**Approach:** <one sentence>

**Steps:**
1. `path/to/file.py` — <what changes and why>
2. `path/to/other.py` — <what changes and why>
...

**Risks:**
- <risk or tradeoff, if any>

**Out of scope:**
- <explicitly what is NOT being changed, to prevent scope creep>
```

Present this plan to the user and wait for acknowledgment before proceeding.
If the user says "looks good", "go ahead", or similar — proceed.
If the user asks questions or suggests changes — update the plan first.

---

## Phase 3 — Act

Only now, edit code. Follow the plan. Do not expand scope during this phase.

**Rules:**
- Edit files in the order specified in the plan.
- If you discover something unexpected mid-edit that invalidates the plan,
  stop, explain what you found, and return to Phase 2 to revise the plan.
- Do not add features, refactor unrelated code, or fix unrelated bugs while
  implementing — record them as follow-up items instead.
- After all edits, verify: do the changes match the plan exactly?

**Stop conditions — halt and ask the user if:**
- A file you need to edit doesn't exist or has a completely different structure
  than expected.
- An assumption from Phase 1 turns out to be wrong mid-implementation.
- The change requires touching a file that was listed as "out of scope".
- A test is failing for a reason unrelated to the current task.

---

## Final Output Format

After completing all edits, produce a concise summary:

```
## Changes Made

**Files edited:**
- `path/to/file.py` — <one-line description of change>

**Behavior change:**
<Before: what it did>
<After: what it does now>

**Tests:**
- [ ] Existing tests still pass
- [ ] New tests added (if behavior changed)
- [ ] No tests exist — recommend adding: <what to test>

**Follow-up items (out of scope for this task):**
- <anything noticed but deliberately not changed>
```

---

## Quick Reference

| Phase | Gate to exit |
|-------|-------------|
| Explore | Exploration Summary written, no open questions |
| Plan | Plan shown to user, user has acknowledged |
| Act | All edits match plan; stop conditions not triggered |
