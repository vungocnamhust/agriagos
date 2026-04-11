# CLAUDE.md

This file provides architecture-documentation guidance for Claude Code when working under `docs/architecture/`.

## Core Rule

Describe the architecture that exists in this repository. Do not invent layers, services, workflows, or integration components that are not already present in the current architecture docs, ADRs, diagrams, or code layout.

## Canonical Terminology

- Preserve canonical terminology exactly as established in the current architecture corpus.
- Reuse the existing names for aggregates, events, states, layers, and bounded contexts.
- Do not introduce synonyms for canonical concepts when an approved term already exists.
- If multiple docs appear to use different names, resolve the conflict by checking the ADRs and the latest architecture docs before writing new text.

## Required Cross-Checks

**Note: `docs/architecture/` is an empty placeholder. All actual documentation lives under `docs/changelog/v1/architecture/`.**

Before adding or editing architecture documentation, always cross-check:

1. event names against `event_desc.md` and `docs/changelog/v1/architecture/05-event-catalog.md`
2. domain boundaries against `system_v1.md`, `determistic_layer_spec_v1.md`, and `docs/changelog/v1/architecture/`
3. source-of-truth ownership against `minimal_requirement.md`, `docs/changelog/v1/architecture/04-canonical-data-model.md`, and the ADR set under `docs/changelog/v1/adrs/`
4. route, module, and workflow descriptions against the current implementation under `agos_app/app/`
5. human-readable code formats against `docs/changelog/v1/architecture/naming-conventions.md` and `agos_app/app/core/codegen.py`
6. event naming (dotted lowercase runtime / PascalCase docs) against `docs/changelog/v1/architecture/naming-conventions.md`

## Diagrams And ADRs

- Keep Mermaid diagrams, architecture prose, and ADRs aligned.
- If a documentation change affects domain ownership, state transitions, event flow, or architectural boundaries, update the relevant diagrams in `docs/changelog/v1/diagram/` as part of the same change.
- If a change alters or supersedes an architectural decision, add or supersede an ADR under `docs/changelog/v1/adrs/` instead of silently changing prose.
- Do not leave diagrams or ADRs describing an older architecture after updating narrative docs.

## Boundary Discipline

- Respect the current bounded contexts: customers, preorders, orders, lots, farm, views, events, and the deterministic core layers around them.
- Do not collapse separate concepts such as command, event, state, projection, and source-of-truth record into one term.
- Do not describe CRM, ERP, LiteFarm, or future AI agents as the canonical owner of data that the current architecture assigns to Agri OS Core.
- Do not describe AI or agents as write-path authorities; they remain advisory unless an approved ADR states otherwise.

## When Unsure

- Prefer the existing ADRs and architecture docs over assumptions.
- If the current docs and implementation disagree, surface the inconsistency explicitly instead of normalizing it away.
- Make the smallest documentation change that restores accuracy and internal consistency.