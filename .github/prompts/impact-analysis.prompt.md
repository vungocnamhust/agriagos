---
name: "Impact Analysis"
description: "Map affected entities, routes, events, migrations, tests, docs, integrations, and risk before coding. Use when a change request might have hidden blast radius."
argument-hint: "Describe the requested change"
agent: "agent"
---

Produce a compact impact map for the requested change.

Include:
- target and nature of change
- affected entities and DTOs
- affected routes and projections
- affected domain events
- migrations or DDL impact
- tests and fixtures likely to move
- docs, diagrams, ADRs, and OpenAPI surfaces at risk
- integrations or external consumers at risk
- a HIGH / MEDIUM / LOW risk summary
- recommended edit order

Do not start implementation in this prompt.
