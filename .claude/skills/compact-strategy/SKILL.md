---
name: compact-strategy
description: >
  Decides when to run /compact, when to hold off, and what focus text to pass.
  Optimized for architecture work, multi-file debugging, and long research sessions.
  Trigger when the user says "should I compact?", "is it time to compact?",
  "compact the context", "we're running long", or when you notice the conversation
  has grown across multiple distinct phases of work. Also self-trigger when you
  detect you are near context pressure (repeated re-reading of the same files,
  summaries getting imprecise, or responses becoming longer to compensate).
---

# /compact Strategy

Context compression is a lossy operation. The goal is to compact *before* important
state is crowded out, not *after* it's already gone. But compacting too early discards
live reasoning threads that haven't resolved yet.

This skill gives you a decision framework and ready-made focus text for the three
session types where context management matters most.

---

## When to Compact — Decision Tree

```
Is the current task fully complete or naturally paused?
  YES → safe to compact now, see focus templates below
  NO  → are you mid-debugger-loop, mid-trace, or mid-reasoning?
          YES → do NOT compact; finish the current reasoning unit first
          NO  → check context pressure signals below
```

### Compact Now — Green Signals

Run `/compact` when **two or more** of these are true:

- You are transitioning between a completed phase and a new one (e.g., exploration
  → implementation, or debugging one module → debugging another).
- The conversation has passed through 3+ distinct sub-topics or file groups.
- You have re-read the same file more than twice in the session without it changing.
- The user has said something like "okay, now let's move on to…" — a phase boundary.
- A long research thread has concluded with a clear decision or finding.
- You are about to start a NEW top-level task (different domain, different layer,
  different file cluster).

### Hold Off — Red Signals

Do NOT compact when any of these are true:

- You are mid-stack-trace: the full error + call path is still the active subject.
  Compacting will lose the exact error text and the reasoning chain connecting it
  to a cause.
- You are mid-implementation: you've made some edits but haven't verified they work.
  The diff and the intent behind it are live context.
- The user just asked a clarifying question about something said earlier in the
  session — the earlier content is still load-bearing.
- You are in an active evaluation loop: test → fail → hypothesize → test.
  The prior hypothesis is part of the working memory.
- A plan was just approved but no edits have been made yet — the plan details
  need to survive into the edit phase.

---

## Focus Text Templates

Pass focus text to `/compact` to guide what the summary preserves. Choose by
session type. Edit the `[bracketed]` parts to be specific.

### Architecture Sessions

Use when: designing layers, choosing patterns, writing ADRs, mapping domain boundaries.

```
/compact Preserve: (1) all architectural decisions made and their rationale,
(2) the layer/module names and their responsibilities as defined so far,
(3) any constraints or non-goals explicitly stated,
(4) open design questions not yet resolved,
(5) the names of all files read and what role they play in the system.
Drop: exploratory tangents that didn't lead to a decision, repeated explanations
of the same concept.
```

### Debugging Sessions

Use when: chasing a bug across stack frames, tracing data flow, reading logs.

```
/compact Preserve: (1) the exact error message or symptom, verbatim,
(2) the full call path from entry point to failure site,
(3) every hypothesis considered and its current status (ruled out / live / confirmed),
(4) the specific files and line numbers that are suspects,
(5) what has already been tried and the outcome.
Drop: general explanations of how the framework works, tangential file reads
that were ruled out as unrelated.
```

### Long Research Sessions

Use when: surveying a codebase before a large refactor, reading design docs,
mapping an unfamiliar system.

```
/compact Preserve: (1) the research goal stated at the start,
(2) a structured map of what was found — file/module names, their purpose,
and how they relate to each other,
(3) any surprising findings or inconsistencies noted,
(4) the list of files NOT yet read that still need investigation,
(5) any provisional conclusions drawn so far.
Drop: verbatim file contents already summarized, exploratory reads that found
nothing relevant.
```

---

## Situational Variants

### Before Handing Off to a Sub-Agent

If you are about to spawn an agent to do independent work:

```
/compact Preserve: (1) the exact task the sub-agent will receive,
(2) the files and interfaces it will need to know about,
(3) any constraints or "do not touch" areas,
(4) the expected output format.
```

### After a Long Planning Phase, Before Acting

Compact just before the first edit so the implementation phase starts clean:

```
/compact Preserve: the full implementation plan with file list and per-file
change descriptions, any user-approved decisions, constraints stated as
out-of-scope, and the test strategy if discussed.
Drop: all exploration reasoning that led to the plan — the plan itself is
the conclusion.
```

### Mid-Session Topic Switch

User pivots to a completely different area:

```
/compact Preserve: a one-paragraph summary of what was completed before the pivot,
any outstanding follow-up items from the prior topic, then full detail on
[the new topic starting point].
```

---

## Quick Reference

| Situation | Compact? | Focus emphasis |
|-----------|----------|----------------|
| Phase transition complete | Yes | Decisions made, open questions |
| Mid-stack-trace | No | — |
| Mid-implementation | No | — |
| Research survey done, now designing | Yes | Findings map, research goal |
| Active test-fail-hypothesize loop | No | — |
| About to spawn sub-agent | Yes | Task spec + interfaces |
| Plan approved, first edit pending | Yes | Plan steps only |
| User pivots topic | Yes | Prior summary + new starting point |
| 3+ re-reads of same file | Yes | Current task focus |

---

## Self-Diagnosis Prompts

Before deciding, answer these:

1. **Is there an unresolved reasoning thread in flight?** If yes → hold.
2. **Would losing the last N exchanges break something I'm about to do?** If yes → hold.
3. **Can I state the current task in one sentence without re-reading anything?** If no → hold.
4. **Has the conversation passed a natural phase boundary?** If yes → compact now.
