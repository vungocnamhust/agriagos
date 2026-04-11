---
description: "Use when editing architecture docs, ADRs, diagrams, README files, or repository guidance. Keeps canonical terminology, diagrams, ADRs, and code descriptions aligned with the implemented system."
applyTo: "docs/**/*.md,CLAUDE.md,system_v1.md,determistic_layer_spec_v1.md,event_desc.md,deterministic_core_diagram.md,minimal_requirement.md"
---

# Documentation Instructions

- Treat `.claude/rules/docs-sync.md` as the enforcement rule for this surface and `docs/changelog/v1/architecture/00-source-of-truth-registry.md` as the authority map for mutable architecture facts.
- Describe the architecture that exists in this repo. Do not invent layers, workflows, or integration components.
- Preserve canonical names for aggregates, states, events, layers, and bounded contexts.
- Resolve mutable fact questions through the registry first. Do not treat `docs/architecture/CLAUDE.md`, repo-root summaries, or nearby code comments as primary authority when the changelog docs already own the concern.
- If architecture behavior, state flow, ownership, or event contracts change, update the relevant diagrams and ADRs in the same change.
- Prefer the smallest documentation correction that restores accuracy.
- If code and docs intentionally diverge, record the divergence explicitly instead of hiding it.
- Cross-check event names, domain ownership, and route/module descriptions against current code before editing prose.
