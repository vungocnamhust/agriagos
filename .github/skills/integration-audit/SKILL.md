---
name: integration-audit
description: "Audit an integration flow for coupling, missing mappings, retry gaps, idempotency issues, ownership confusion, and missing observability. Use for adapters and cross-system sync work."
argument-hint: "Describe the integration flow"
---

# Integration Audit

Audit Agri OS integration flows systematically.

## Procedure
1. Confirm the systems, transport, data shape, error handling, and observability.
2. Review the flow across six dimensions: coupling, mapping, retry, idempotency, ownership, observability.
3. Produce a prioritized fix list with severity and effort.

## Constraints
- Never guess the flow. Ask for missing details first.
- Keep external schemas out of the deterministic core.
- Call out external ID leakage and replay hazards explicitly.
