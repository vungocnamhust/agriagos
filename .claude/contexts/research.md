## Research Context

- Use this context only for repo exploration, debugging reconnaissance, or change impact discovery.
- Stay read-only unless the task explicitly switches to implementation mode.
- Start from the user’s concrete anchor: file, symbol, route, DTO, failing behavior, or command.
- Gather only enough context to identify the controlling code path and its nearest dependencies.
- Prefer targeted reads over broad repo mapping.
- Consult `.claude/rules/canonical-model.md` before inferring aggregate ownership or moving truth.
- Trace behavior in this order when relevant: route -> service -> core -> store/event-store -> docs.
- For API work, inspect the route signature and the matching models before inferring behavior.
- For evented flows, inspect the service that emits the event and the store or projection surface it affects.
- Note domain boundaries, aggregate ownership, and lifecycle rules before proposing edits.
- Distinguish current implementation from architecture docs when they diverge.
- Record whether a change would affect contracts, events, docs, or integrations beyond the local file.
- When multiple paths look plausible, choose the one with the cheapest discriminating check.
- Use nearby tests, call sites, and sibling services to confirm intent instead of guessing.
- Summarize findings as concrete hypotheses, risks, and touched surfaces.
- Do not propose broad refactors unless the local path is proven insufficient.
- Stop exploring once you can name the owning code path, one falsifiable hypothesis, and the smallest next action.