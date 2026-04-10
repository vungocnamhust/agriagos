---
name: "OpenAPI From Domain"
description: "Turn a domain use case into endpoint design, request and response schemas, error models, and versioning notes without guessing missing invariants."
argument-hint: "Describe the use case"
agent: "agent"
---

Convert the use case into an Agri OS API contract.

First, ask for any missing invariants around:
- actor and authorization
- preconditions and allowed states
- required and optional fields
- idempotency and concurrency
- side effects and events
- versioning and backward compatibility

Only after the invariants are explicit, output:
- endpoint and HTTP method
- request schema
- response schema
- error envelope and status codes
- emitted domain events
- versioning notes
