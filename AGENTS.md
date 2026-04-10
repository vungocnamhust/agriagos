# Agri OS Agent Bridge

This file is a thin compatibility bridge for Copilot CLI and agent discovery.
Primary always-on workspace guidance lives in `.github/copilot-instructions.md`.
Primary architecture truth lives in `CLAUDE.md`, `agos_app/app/api/CLAUDE.md`, `docs/architecture/CLAUDE.md`, and `agos_app/app/integrations/CLAUDE.md`.

## Mission

Agri OS is a deterministic-core FastAPI repository for agricultural supply chain operations. Keep the core as the canonical write-path owner. AI and integrations are advisory or translational, not authoritative.

## Lookup Order

1. `.github/copilot-instructions.md` for Copilot-specific workflow guidance
2. `CLAUDE.md` for repository architecture and operating model
3. Nearest nested `CLAUDE.md` or `.claude/rules/*.md` file for local boundaries

## Runtime Facts

- App root: `agos_app/`
- Install: `pip install -r agos_app/requirements.txt`
- Run: from `agos_app/`, use `uvicorn app.main:app --reload`
- Validation: no confirmed lint or automated test harness yet; state any validation gaps explicitly
