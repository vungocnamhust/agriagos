---
name: integration-audit
description: >
  Audits an integration flow for coupling, missing field mapping, retry gaps,
  idempotency issues, ownership confusion, and missing observability.
  Outputs a prioritized fix list with severity labels.
  Trigger when the user says "audit this integration", "review the flow between
  X and Y", "check this integration for issues", "what's wrong with this
  connector", "is this integration production-ready", or "find problems in
  this event/API/queue flow".
  Critical behavior: this skill asks for the flow description before auditing —
  never guess about what is being integrated.
---

# Integration Flow Audit

Systematically inspect an integration for the six failure classes that make
integrations unreliable in production, then produce a single prioritized fix
list the team can work from.

The six classes are:

| # | Class | Core question |
|---|-------|--------------|
| 1 | **Coupling** | Can each side change, deploy, and fail independently? |
| 2 | **Missing mapping** | Is every field explicitly transformed across system boundaries? |
| 3 | **Retry gaps** | Will transient failures recover automatically and safely? |
| 4 | **Idempotency** | Is duplicate or replayed delivery handled without side effects? |
| 5 | **Ownership confusion** | Is contract ownership, versioning, and schema authority clear? |
| 6 | **Missing observability** | Can you detect, diagnose, and alert on failures from outside? |

---

## Phase 1 — Collect the Integration Description

Before auditing, you need a description of the flow. If the user has not
provided one, ask:

```
To audit this integration I need:

1. The two (or more) systems involved — names, types (API, queue, DB,
   webhook, file, etc.), and which side initiates.
2. The data that crosses the boundary — payload shape, key fields, volume/frequency.
3. The transport mechanism — HTTP, message broker, shared DB, file drop, etc.
4. Any existing error handling — retries, dead-letter queues, circuit breakers.
5. Any existing observability — logs, metrics, traces, alerts.
6. Known pain points or recent incidents (optional but valuable).
```

If the user provides a code snippet, diagram description, or prose, extract
what you can and note what is missing without asking again.

---

## Phase 2 — Run the Six-Dimension Audit

Work through each dimension in order. For each one, list every finding you
can support from the provided description. If you lack evidence to evaluate
a dimension, note it as "**Insufficient information — assumption required**"
and state what you are assuming.

---

### Dimension 1: Coupling

Coupling makes each side fragile to the other's changes, availability, and
deployment schedule. Look for:

**Temporal coupling**
- Synchronous call where async would suffice (caller blocks until callee responds)
- Caller fails if callee is slow or down (no timeout + fallback)
- Hard dependency on response latency for caller's SLA

**Structural / data coupling**
- Caller uses callee's internal schema directly (no published contract or DTO)
- Shared database or shared mutable store
- Caller references callee's internal IDs, table names, or enum values

**Deployment coupling**
- Must deploy both sides in lockstep
- Shared library containing protocol types forces joint releases

**Knowledge coupling**
- Caller encodes callee business logic (e.g., price calculation duplicated
  on the calling side)
- Caller checks callee's internal state to decide its own behavior

**Output per finding:**
```
COUPLING | <severity> | <location in flow>
<one-sentence description of what is coupled>
Fix: <concrete decoupling step>
```

---

### Dimension 2: Missing Mapping

Every field that crosses a system boundary must be explicitly mapped.
Implicit coercion, assumed defaults, and structural similarity are sources
of silent data corruption. Look for:

**Field mapping gaps**
- Fields present in the source that have no explicit target mapping
- Fields required by the target that the source does not always provide
- Fields that exist on both sides but carry different semantics (same name,
  different meaning)

**Type and format mismatches**
- Numeric types with different precision (float vs decimal for money)
- Date/time without explicit timezone handling
- Strings that are actually enums — are the enum sets aligned?
- Boolean fields where one side uses null as a third state

**Null / missing field handling**
- What happens when an optional source field is absent?
- Are defaults applied explicitly or left to the target's interpretation?

**Unit and encoding mismatches**
- Quantities in different units (kg vs g, cents vs dollars)
- String encoding differences (UTF-8 vs latin-1, URL-encoded vs raw)
- ID format differences (UUID vs integer vs string)

**Output per finding:**
```
MAPPING | <severity> | <field or fields>
<description of the gap or mismatch>
Fix: <explicit mapping rule or schema alignment step>
```

---

### Dimension 3: Retry Gaps

Transient failures (network blip, downstream restart, rate limit) must be
handled by the integration layer — not by humans. Look for:

**No retry at all**
- Single-attempt calls with no retry policy
- "Fire and forget" calls where the result matters

**Unsafe retry configuration**
- No maximum attempt count (infinite retry loop)
- No backoff (hammers the callee, worsens an outage)
- Fixed backoff instead of exponential + jitter (synchronized thundering herd)

**Retrying non-idempotent operations**
- Retry logic applied to state-changing calls that lack idempotency keys
- POST calls retried without checking whether the first attempt succeeded

**Missing failure escalation**
- No dead-letter queue or dead-letter topic for exhausted retries
- No alert or human escalation path when DLQ depth grows
- Retried messages are silently dropped after max attempts

**Missing circuit breaker**
- No circuit breaker protecting a downstream service that is consistently
  slow or unavailable
- All retries run to exhaustion during a sustained callee outage

**Output per finding:**
```
RETRY | <severity> | <call or step>
<description of the gap>
Fix: <specific policy — e.g., "exponential backoff: 1s, 2s, 4s, max 3 attempts + DLQ">
```

---

### Dimension 4: Idempotency

At-least-once delivery is the norm for queues and HTTP retries. Every
consumer or handler must be safe to call multiple times with the same input.
Look for:

**Non-idempotent writes**
- INSERT without duplicate check (creates duplicates on replay)
- Mutable counters or balance fields incremented on every delivery
- Side effects triggered unconditionally (email sent, webhook fired) on
  every delivery

**No idempotency key**
- Command or event carries no stable identifier usable for deduplication
- The caller generates a new ID on each retry instead of reusing the original

**No deduplication check**
- Consumer does not check whether an event or command has already been
  processed before acting
- Idempotency key is passed but never checked

**Partial idempotency**
- Some steps in a multi-step handler are idempotent; others are not
- Idempotency checked at ingress but not after internal routing or fanout

**Output per finding:**
```
IDEMPOTENCY | <severity> | <operation or handler>
<description of the non-idempotent behavior>
Fix: <strategy — e.g., "add idempotency_key field; check processed_events table before executing">
```

---

### Dimension 5: Ownership Confusion

An integration without a clear owner has no one responsible for keeping the
contract stable, versioning changes, or resolving incidents. Look for:

**Unclear contract ownership**
- No canonical schema definition with an authoritative owner
- Both sides maintain separate schema copies that drift
- Schema is defined in code comments or in undocumented assumptions

**No versioning**
- No version field or version prefix in the message/request
- Breaking changes silently deployed to shared channels
- No deprecation timeline or sunset date for old versions

**Multiple producers on a single channel**
- Multiple services write to the same topic or table without a coordinator
- Consumers must handle incompatible schema variants from different producers

**Ambiguous error ownership**
- When integration fails, it is unclear which side is responsible for
  remediation
- No runbook or escalation path tied to the integration owner

**Consumer-side schema pinning**
- Consumer is coded against a specific schema version with no tolerance
  for additive changes (fragile deserialization)

**Output per finding:**
```
OWNERSHIP | <severity> | <boundary or contract>
<description of the confusion>
Fix: <ownership assignment, versioning strategy, or schema registry recommendation>
```

---

### Dimension 6: Missing Observability

You cannot fix what you cannot see. An integration with missing observability
is a liability the moment it hits production. Look for:

**No correlation / trace ID**
- Requests cross service boundaries without a propagated trace ID
- Logs on each side cannot be correlated to a single business transaction

**No latency metrics**
- Integration call duration is not measured or exported
- No baseline or alert threshold for latency degradation

**No error rate tracking**
- Failures are logged but not counted or alerted on
- No distinction between transient errors (retry-able) and permanent errors

**No throughput or backlog metrics**
- Queue depth or message lag is not monitored
- Spikes in volume cause silent slowdowns without alerting

**Insufficient logging**
- No log entry at integration call boundaries (entry + exit + outcome)
- Payload not logged even at DEBUG level, making incident reproduction impossible
- Sensitive fields logged in plaintext (log too much)

**No alerting**
- No alert fires when error rate exceeds threshold
- No alert fires when DLQ depth grows
- Incidents are discovered by end users, not monitoring

**Output per finding:**
```
OBSERVABILITY | <severity> | <missing signal>
<description of what is invisible and why it matters>
Fix: <specific instrumentation — e.g., "emit integration.call.duration histogram with service and operation labels">
```

---

## Phase 3 — Produce the Prioritized Fix List

Assign each finding a severity:

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Can cause data loss, duplicate processing, silent corruption, or complete integration failure in production. Fix before shipping. |
| **HIGH** | Significantly degrades reliability or debuggability. Likely to cause an incident under real load. Fix in the next sprint. |
| **MEDIUM** | Operational pain or risk that grows over time. Fix within the next release cycle. |
| **LOW** | Improvement worth making but not blocking. Fix in a cleanup pass. |

Output the findings as a single numbered list, sorted CRITICAL → HIGH →
MEDIUM → LOW. Within the same severity level, sort by dimension number
(Coupling first, Observability last).

**Format:**

```
## Integration Audit — Fix List

**Flow:** <name or short description of the integration>
**Audited:** <date>
**Total findings:** <n> (CRITICAL: <n>, HIGH: <n>, MEDIUM: <n>, LOW: <n>)

---

### CRITICAL

1. [IDEMPOTENCY] **<short title>**
   Location: <where in the flow>
   Problem: <one sentence — what goes wrong and when>
   Fix: <concrete action — what to add, change, or remove>
   Effort: <XS / S / M / L>

2. [RETRY] **<short title>**
   ...

---

### HIGH

3. [COUPLING] **<short title>**
   ...

---

### MEDIUM

...

---

### LOW

...

---

## Audit Gaps

List any dimensions where you lacked enough information to audit fully.
State what you assumed and what additional information would let you complete
the audit.

- <dimension>: <what was unclear> — assumed <X>
```

---

## Phase 4 — Quick-Win Summary

After the fix list, output a short section for the team:

```
## Quick Wins (fix in < 1 day)

<List items rated CRITICAL or HIGH with Effort XS or S. These are the
highest-leverage fixes: severe impact, low effort.>

## Architectural Concerns (require design discussion)

<List items rated HIGH or CRITICAL with Effort L, or any finding that
requires changing the integration protocol rather than just adding code.>
```

---

## Constraints

- Never invent findings. Every finding must be traceable to something in
  the description. If you suspect a problem but cannot confirm it, note it
  as a "potential concern" and ask the user to verify.
- Never assign CRITICAL to a finding unless it can cause data loss,
  duplicate side effects, or complete integration failure.
- Do not recommend redesigning the entire integration unless the coupling
  and ownership findings together make the current design untenable. Prefer
  targeted fixes over big rewrites.
- If the integration is a messaging system, default to assuming at-least-once
  delivery unless the user states otherwise.
- Effort estimates are for a single engineer familiar with the codebase:
  XS = hours, S = 1–2 days, M = 3–5 days, L = > 1 week.
