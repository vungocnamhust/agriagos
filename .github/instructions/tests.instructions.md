---
description: "Use when writing or reviewing tests for Agri OS. Prefer high-signal tests for state transitions, API contracts, idempotency, and integration mappings over snapshot-heavy coverage."
applyTo: "tests/**/*.py,**/test_*.py,**/*_test.py"
---

# Test Instructions

- Prefer focused tests that prove business behavior: successful state changes, invalid transitions, missing dependencies, and idempotent replay.
- For API-facing changes, test contract shape and status codes, not just happy-path payloads.
- For integration work, test boundary mappings and external ID handling explicitly.
- Avoid snapshot-heavy tests unless they protect a stable public contract.
- This repo does not yet have a confirmed automated test harness; if tests exist, use them. If you add tests, document the runner and setup assumptions in the same change.
- If no executable tests exist for the touched slice, say so explicitly and fall back to the cheapest meaningful validation.
