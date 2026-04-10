---
name: impact-analysis
description: "Map the blast radius of a requested change across entities, routes, events, tests, docs, migrations, and integrations before coding."
argument-hint: "Describe the requested change"
---

# Impact Analysis

Produce an impact map before implementation.

## Procedure
1. Identify the target and the type of change.
2. Scan entities, routes, events, migrations, tests, docs, integrations, and infrastructure.
3. Assign HIGH, MEDIUM, or LOW risk to each affected surface.
4. Return a compact edit order and coordination warnings for public or external contracts.

## Output
- affected areas by category
- risk summary
- recommended edit order
- any coordination needed before code changes
