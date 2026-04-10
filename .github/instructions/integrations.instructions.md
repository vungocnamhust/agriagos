---
description: "Use when editing integration adapters, vendor payload mappings, external ID handling, or integration DTOs. Enforces anti-corruption layers, schema isolation, idempotency, retry clarity, and observability at the boundary."
applyTo: "agos_app/app/integrations/**/*.py,agos_app/app/models/integrations.py"
---

# Integrations Instructions

- Treat `.claude/rules/integrations.md`, `.claude/rules/canonical-model.md`, and `agos_app/app/integrations/CLAUDE.md` as the detailed authority for this surface.
- Treat integration code as an adapter layer around external systems, not as an extension of the core domain.
- Translate vendor payloads at the boundary before calling canonical services.
- Keep external schemas, vendor IDs, and vendor-specific conditionals out of `app.core`, `app.store`, and canonical DTO modules.
- Resolve external IDs to internal IDs through explicit mappings such as `ExternalMappingRecord`.
- Make retry behavior and idempotency explicit. Do not hide background retry loops inside route handlers or services.
- Log sync attempts and outcomes with enough context to reconstruct failures.
