---
name: impact-analysis
description: "Map the blast radius of a requested change across entities, routes, events, tests, docs, migrations, and integrations before coding."
argument-hint: "Describe the requested change"
---

# Impact Analysis

Produce an impact map before implementation.

## Procedure
1. Resolve the owning authority doc through `docs/changelog/v1/architecture/00-source-of-truth-registry.md`.
2. Identify the target and the type of change.
3. Scan entities, routes, events, migrations, tests, docs, integrations, and infrastructure.
4. Assign HIGH, MEDIUM, or LOW risk to each affected surface.
5. Return a compact edit order and coordination warnings for public or external contracts.

## Output
- affected areas by category
- risk summary
- recommended edit order
- any coordination needed before code changes
