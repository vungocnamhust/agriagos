---
name: usecase-to-openapi
description: >
  Converts a domain use case description into a complete OpenAPI specification:
  endpoints, request/response schemas, error models, and versioning notes.
  Trigger this skill when the user says "design an endpoint for X", "I need an
  API for Y", "add a route that does Z", "what should the API look like for
  this use case", or "convert this requirement into an API spec".
  Critical behavior: this skill never guesses missing invariants — it asks
  targeted questions first and only generates the spec after the invariants are
  confirmed. A spec with wrong constraints is worse than no spec.
---

# Use Case → OpenAPI

Turn a domain use case into a precise, implementable OpenAPI specification.
The core discipline here is asking before assuming. A wrong invariant silently
becomes a wrong implementation, a wrong test, and eventually a production bug.

---

## Phase 1 — Extract the Use Case

Read the user's description and extract the following. If any item is missing
or ambiguous, add it to the questions list in Phase 2.

**What to extract:**

| Item | Example |
|------|---------|
| Actor | Farmer, Staff, Admin, System |
| Intent | "allocate lot to order", "record harvest", "cancel pre-order" |
| Preconditions | "lot must be in RELEASED state" |
| Postconditions | "order moves to ALLOCATED state; lot quantity reduced" |
| Side effects | "triggers LotAllocated domain event", "sends notification" |
| Failure modes | "lot already allocated", "insufficient quantity", "order already cancelled" |
| Authorization | who can call this, under what role/scope |
| Idempotency | is re-calling with the same input safe? |

---

## Phase 2 — Gather Missing Invariants

This is the most important phase. **Do not skip it. Do not guess.**

After extracting what you can, compile a list of everything still unclear.
Group questions by category and ask them all at once — do not ask one at a
time across multiple turns.

**Question categories:**

**Authorization & ownership**
- Who is allowed to perform this action? (role, ownership check, scope)
- Can a user act on behalf of another (impersonation, delegation)?

**State & preconditions**
- What state must the resource be in before this action is valid?
- What happens if the resource is in the wrong state — reject silently or
  return a structured error?
- Are there time windows, quotas, or rate limits?

**Input constraints**
- Are there fields with domain-specific validation (e.g. quantity must be a
  positive integer in kg)? Ranges, formats, enums?
- Which fields are required vs optional? Any conditionally required fields?
- What happens with extra/unknown fields — strip silently or reject?

**Idempotency & concurrency**
- If the same request is sent twice, should the second call succeed, fail, or
  be a no-op?
- Is there a client-provided idempotency key?
- Can two concurrent calls conflict, and if so, how is that handled?

**Side effects**
- What domain events are emitted on success?
- Are there notifications, webhooks, or async jobs triggered?
- Does this mutate multiple aggregates (distributed transaction risk)?

**Versioning**
- Is this endpoint new or replacing an existing one?
- If replacing: does the old endpoint need to stay alive, under what version,
  for how long?
- Are there breaking changes to existing consumers?

**Format your questions as a numbered list**, e.g.:

```
Before I generate the spec, I need to clarify a few invariants:

1. [Authorization] Can any authenticated user cancel a pre-order, or only the
   farmer who created it?
2. [State] What states can a pre-order be in when cancellation is requested?
   Should we reject cancellation for CONFIRMED orders or allow it?
3. [Idempotency] If the cancel endpoint is called twice for the same order,
   should the second call return 200 (no-op) or 409 (already cancelled)?
4. [Side effects] Should cancellation trigger a notification to the farmer?
   If so, synchronous or async?
```

Wait for answers. Do not generate the spec until all questions are answered.
If the user says "use your best judgment" for a specific question, document
the assumption explicitly in the spec as a `# NOTE:` comment.

---

## Phase 3 — Generate the OpenAPI Spec

Once all invariants are confirmed, produce the spec in this format.

### 3.1 Endpoint definition

```yaml
# -------------------------------------------------------
# Use Case: <use case name>
# Actor: <who calls this>
# Preconditions: <bullet list>
# Postconditions: <bullet list>
# -------------------------------------------------------

paths:
  /api/v1/<resource>/<action>:
    post:                          # or GET / PATCH / DELETE
      operationId: <camelCaseId>
      summary: <one line>
      description: |
        <paragraph: what this does, who calls it, when>
      tags:
        - <domain tag>
      security:
        - BearerAuth: []           # adjust to actual auth scheme
      parameters: []               # path / query params if any
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/<CommandName>Request'
            example:
              <inline example>
      responses:
        '200':
          description: <success description>
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/<CommandName>Response'
              example:
                <inline example>
        '400':
          $ref: '#/components/responses/ValidationError'
        '409':
          $ref: '#/components/responses/ConflictError'
        '422':
          $ref: '#/components/responses/DomainError'
        '401':
          $ref: '#/components/responses/Unauthorized'
        '403':
          $ref: '#/components/responses/Forbidden'
        '404':
          $ref: '#/components/responses/NotFound'
```

### 3.2 Request schema

```yaml
components:
  schemas:
    <CommandName>Request:
      type: object
      required:
        - <required fields>
      properties:
        <field>:
          type: <string | integer | number | boolean | array | object>
          description: <what this field means in domain terms>
          example: <realistic value>
          # add: format, minimum, maximum, minLength, maxLength, enum, pattern
          # as determined by the invariants collected in Phase 2
      additionalProperties: false   # unless user confirmed otherwise
```

### 3.3 Response schema

```yaml
    <CommandName>Response:
      type: object
      required:
        - id
        - status
      properties:
        id:
          type: string
          format: uuid
          description: Resource identifier
        status:
          type: string
          enum: [<valid states>]
          description: New state after the action
        # include fields the caller needs to continue their workflow
        # omit internal/audit fields unless explicitly requested
```

### 3.4 Error models

Use a consistent error envelope across all endpoints:

```yaml
    ErrorResponse:
      type: object
      required: [code, message]
      properties:
        code:
          type: string
          description: Machine-readable error code
          example: LOT_ALREADY_ALLOCATED
        message:
          type: string
          description: Human-readable explanation
          example: "Lot L-2024-001 has already been allocated to order O-789"
        details:
          type: array
          items:
            type: object
            properties:
              field:
                type: string
              message:
                type: string
          description: Field-level validation errors (present on 400 only)
        trace_id:
          type: string
          description: Correlation ID for debugging

  responses:
    ValidationError:
      description: Request failed schema or business-rule validation
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
          example:
            code: VALIDATION_ERROR
            message: "quantity must be greater than 0"
            details:
              - field: quantity
                message: "must be > 0"

    ConflictError:
      description: Action conflicts with current resource state
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'

    DomainError:
      description: Business rule violation (precondition not met)
      content:
        application/json:
          schema:
            $ref: '#/components/schemas/ErrorResponse'
```

---

## Phase 4 — Versioning Notes

After the spec, output a versioning section:

```
## Versioning Notes

**Version:** v1
**Status:** <new | extends-existing | replaces-existing>

**If replacing an existing endpoint:**
- Old endpoint: <path>
- Deprecation strategy: <keep alive until / sunset header / parallel run>
- Migration path for consumers: <what they need to change>

**Breaking changes introduced:**
- <list any breaking changes, or "none">

**Forward-compatibility considerations:**
- <fields marked optional today that might become required>
- <enum values that consumers should treat as open sets>

**Assumptions recorded (from "use your judgment" answers):**
- <any assumption made on behalf of the user, so it can be revisited>
```

---

## Output Summary

At the end, provide a compact summary for the implementation team:

```
## Implementation Checklist

- [ ] Route: <METHOD> <path>
- [ ] Request model: <CommandName>Request — <n> required fields
- [ ] Response model: <CommandName>Response
- [ ] Error codes to handle: <list>
- [ ] Precondition checks to implement: <list>
- [ ] Domain events emitted on success: <list>
- [ ] Auth: <role/scope required>
- [ ] Idempotency: <yes/no — strategy>
- [ ] Migration needed: <yes/no>
- [ ] Tests to write: happy path, <list of failure modes>
```

---

## Constraints

- Never add a field to the schema that the user did not mention or confirm.
  If a field seems necessary but wasn't specified, ask rather than add.
- Use `additionalProperties: false` by default to make schemas strict.
- Always include at least one realistic example per schema.
- HTTP method selection: POST for commands that change state, GET for queries,
  PATCH for partial updates, DELETE for removal. Never use GET for state changes.
- Error HTTP codes: 400 for schema/validation failures, 409 for state conflicts,
  422 for domain rule violations, 404 for missing resources, 403 for
  authorization failures.
