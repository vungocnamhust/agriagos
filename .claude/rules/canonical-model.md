# Canonical Model Rules — Agri OS

This document is the authoritative reference for what each entity owns, what it does not own,
naming conventions, and the rules for adding new entities without duplicating truth that already
belongs elsewhere. Every service, schema, projection, and agent integration must comply.

---

## 1. Canonical Entities and Their Ownership

### 1.1 `CustomerProfile`

**Owns:**
- stable customer identity (`customer_id`, `customer_code`)
- contact channels (phone, `zalo_id`, `fb_psid`, email)
- source channel and region
- customer type tags and segment
- lifecycle state (new → qualified → active → loyal → dormant → at_risk)
- channel identity mappings to external systems (CRM, chat)
- preference timeline (product interests, purchase rhythm)
- purchase history summary (`last_purchase_at`, `total_orders`)

**Does not own:**
- order line items or financial totals — owned by `SalesOrder`
- preorder quota — owned by `Preorder`
- lot-level traceability — owned by `LotBatch`
- interaction transcripts — owned by `CRMInteraction`

**Core rule:** One phone number = one canonical profile. Suspected duplicates become a
`candidate_merge` record; merges are never silent. `customer_code` is stable and must never
be reassigned.

---

### 1.2 `Preorder`

**Owns:**
- preorder identity and its link to `CustomerProfile`
- the commitment quantities: `committed_qty`, `allocated_qty`, `delivered_qty`, `cancelled_qty`, `remaining_qty`
- expected delivery schedule
- deposit or payment notes
- preorder lifecycle state: `draft → confirmed → active → completed | cancelled`
- append-only `preorder_adjustments` history for committed quantity changes

**Does not own:**
- the actual delivery — that belongs to `SalesOrder` + `DeliveryRecord`
- lot assignments — those are `Allocation` records pointing at `LotBatch`
- product master data — `ProductSKU` owns that

**Core rule:** Preorder is a commitment contract, not a delivery instruction. `delivered_qty`
advances only when a linked `SalesOrder` reaches `delivered` state. `remaining_qty` means
allocatable balance: `committed_qty - allocated_qty - delivered_qty - cancelled_qty`. No silent
quantity edits — every committed quantity change emits `PreorderAdjusted` and records an append-only
adjustment entry.

---

### 1.3 `ProductSKU`

**Owns:**
- stable SKU identity (`sku_code`, canonical name)
- product group / category
- unit of measure
- pricing tiers (list price, member price, partner price)
- availability state (`active`, `paused`, `discontinued`)
- whether the SKU requires lot-level traceability
- whether the SKU has an expiry date

**Does not own:**
- physical inventory quantities — owned by `LotBatch`
- lot origin or evidence — owned by `LotBatch` / `LotEvidence`
- order line pricing after discounts — owned by `SalesOrderLine`

**Core rule:** No "colloquial" product names as first-class data. Every sellable item must have
a `ProductSKU` record. Lots reference `sku_code`; orders reference `sku_code`.

---

### 1.4 `Farmer`

**Owns:**
- farmer identity and contact
- status (`active`, `inactive`)
- tags (region, co-op membership, certification level)

**Does not own:**
- plot geometry or agricultural details — owned by `Plot`
- crop schedules — owned by `CropCycle`
- task assignments — owned by `CropTask`

---

### 1.5 `Plot`

**Owns:**
- physical land unit: area, location text, GPS boundary if available
- link to `Farmer` (the responsible household)
- operational status

**Does not own:**
- what is growing on it right now — owned by `CropCycle`
- harvest outcomes — owned by `LotBatch`

**Core rule:** A plot is a stable geographic entity. It does not get deleted when a crop cycle
ends; it is reused across seasons.

---

### 1.6 `CropCycle`

**Owns:**
- a single growing season on a single `Plot`
- crop type, variety, planting date, expected harvest window
- planned and actual yield
- lifecycle state: `planned → active → harvested → closed | cancelled`

**Does not own:**
- farm task execution — owned by `CropTask`
- the resulting physical lot — owned by `LotBatch` (which back-references the cycle)

**Core rule:** A lot must trace back to a `CropCycle`. If a lot has no crop cycle (external
purchase), it must explicitly mark `source_type = external` and `source_crop_cycle_id = null`.

---

### 1.7 `CropTask`

**Owns:**
- a single actionable farm task (planting, watering, weeding, harvesting, etc.)
- link to `CropCycle`
- due date, assignment, completion and verification state
- whether evidence is required for verification
- overdue flag (set by the scheduler, not by humans)

**Does not own:**
- evidence files — owned by `LotEvidence` (attached at the lot level after harvest)
- yield outcomes — owned by `CropCycle`

---

### 1.8 `LotBatch`

**Owns:**
- physical batch identity (`lot_id`, `lot_code`)
- lot type: `harvest` or `processed`
- source lineage: `source_crop_cycle_id` and/or `source_lot_id` for processed lots
- quantity: `quantity_in`, `quantity_out`, unit
- harvest and processing timestamps
- QC lifecycle state: `created → in_progress → waiting_evidence → qc_review → released | blocked → consumed | archived`
- available quantity (quantity not yet allocated or consumed)
- back-reference to `ProductSKU` via `sku_code`

**Does not own:**
- evidence files — owned by `LotEvidence`
- QC decision logic — owned by `QCReview`
- which orders this lot was allocated to — owned by `Allocation`

**Core rule:** Orders allocate from lots, never from "generic stock". A lot that is not `released`
cannot be allocated. Quantity consumed by an order decrements `available_qty` only via an
`Allocation` record — never by a direct update.

---

### 1.9 `LotEvidence`

**Owns:**
- individual evidence items attached to a `LotBatch`
- evidence type: `photo`, `video`, `checklist`, `note`, `document`, `measurement`
- object storage key or text value
- capture timestamp and actor
- evidence status: `active` | `rejected`

**Does not own:**
- the QC decision itself — owned by `QCReview`
- lot metadata — owned by `LotBatch`

---

### 1.10 `QCReview`

**Owns:**
- one QC decision record per lot submission
- checklist version applied
- result: `pending → passed | failed | needs_more_evidence`
- reviewer identity and timestamp
- notes

**Does not own:**
- the evidence items themselves — owned by `LotEvidence`
- the release/block action — that is a `LotReleased` / `LotBlocked` domain event
  and the resulting state on `LotBatch`

**Core rule:** Only `qc_reviewer` role may record a `QCReview`. The gateway enforces this;
no code path bypasses it.

---

### 1.11 `SalesOrder`

**Owns:**
- order identity (`order_id`, `order_code`)
- link to `CustomerProfile`
- source channel
- commercial lifecycle state: `draft → confirmed → allocated → packed → shipped → delivered | cancel_requested → cancelled`
- shipping intent (requested ship date, delivery address)
- pack, ship, deliver timestamps
- cancel reason

**Does not own:**
- payment records — separate concern; link by `order_id` but not nested here in v1
- lot inventory — owned by `LotBatch`; the link is `Allocation`
- customer preference data — owned by `CustomerProfile`

**Core rule:** Commercial state and operational state are always two separate fields (see also
`SalesOrderLine`). "Paid" and "delivered" are orthogonal axes. Never merge them.

---

### 1.12 `SalesOrderLine`

**Owns:**
- one line in a `SalesOrder`: `sku_code`, `qty`, `unit`, agreed price
- `allocated_qty` against this line
- per-line operational state: `open → allocated → packed → shipped | cancelled`

**Does not own:**
- which lot backs this line — owned by `Allocation`

---

### 1.13 `Allocation`

**Owns:**
- a single assignment of quantity from a specific `LotBatch` to a specific `SalesOrderLine`
- `allocated_qty`
- allocation state: `active → released | cancelled`

**Does not own:**
- anything else. This entity exists solely to record the lot-to-order-line link.

**Core rule:** Allocations are the only mechanism that connects lots to orders. There is no
direct foreign key from `SalesOrder` to `LotBatch`. If an allocation is cancelled the
quantity must return to `LotBatch.available_qty` via a domain event, not a direct update.

---

### 1.14 `DomainEvent`

**Owns:**
- immutable record of every state-changing fact: what happened, when, who caused it,
  which aggregate it belongs to
- `aggregate_type`, `aggregate_id`, `event_type`, `event_version`
- `actor_type` (`user`, `system`, `api`, `future_ai`), `actor_id`
- `idempotency_key`, `correlation_id`, `causation_id`
- `payload_json`

**Does not own:**
- mutable state — events are append-only, never updated or deleted
- projection state — that lives in read-model tables updated by projection workers

---

## 2. Forbidden Overlaps

| Truth | Wrong place to store it | Why |
|-------|------------------------|-----|
| Canonical customer identity | Inside a chat log, a spreadsheet field, or a CRM tool | Creates split identity; merges become impossible |
| Available lot quantity | As a computed sum in the order service | Race conditions; the lot owns its own quantity |
| Lot QC decision | As a boolean flag on `LotBatch` | Loses reviewer, checklist version, and audit trail |
| Order payment status | Inside `SalesOrder.status` enum | Commercial and financial state must stay separate |
| Preorder `delivered_qty` | Updated directly when a shipment leaves | Must only advance when `OrderDelivered` event fires |
| Product price | Duplicated into `LotBatch` | SKU owns pricing; lots own physical attributes |
| Evidence files | As binary blobs in the core DB | Evidence metadata lives in `LotEvidence`; actual files in object storage |
| Customer segment / preference | Hard-coded into order query filters | Preferences are a `CustomerProfile` concern, read by projections |

---

## 3. Naming Conventions

### IDs and Codes

| Pattern | Convention | Example |
|---------|-----------|---------|
| Internal surrogate ID | `{entity}_id` as UUID or ULID | `customer_id`, `lot_id` |
| Human-readable code | `{entity}_code` as short stable string | `customer_code: KH-2026-001` |
| Lot code | `LOT-{PRODUCT}-{SEASON}-{SEQ}` | `LOT-GAO-MUA2026-01` |
| Order code | `ORD-{YYYYMM}-{SEQ}` | `ORD-202604-0042` |

### Entity Names

- Aggregate roots: `PascalCase` singular — `CustomerProfile`, `LotBatch`, `SalesOrder`
- Value objects and subordinate records: `PascalCase` singular — `LotEvidence`, `QCReview`, `Allocation`
- Domain events: past-tense `PascalCase` verb phrase — `LotReleased`, `OrderAllocated`, `CustomerMerged`
- Commands: imperative `PascalCase` verb phrase — `ReleaseLot`, `AllocateOrderLine`, `CreateCustomer`
- State enums: `snake_case` lowercase — `qc_review`, `waiting_evidence`, `cancel_requested`

### Fields

- Timestamps: suffix `_at` — `created_at`, `released_at`, `delivered_at`
- Quantities: suffix `_qty` or `_kg` depending on semantics — `allocated_qty`, `quantity_kg`
- Boolean flags: `is_` or `has_` prefix — `evidence_required`, `is_active`
- Foreign keys: `{entity}_id` matching the referenced entity — `crop_cycle_id`, `customer_id`
- Source enum for external integrations: `source_type` field — `internal`, `litefarm_sync`, `erp_sync`

### Bounded Contexts (module/package names)

`identity` | `farm_core` | `crop_task` | `lot_traceability` | `qc_workflow` | `order_ops` | `policy_workflow` | `eventing_audit` | `projections`

No abbreviations. No generic names like `core`, `common`, `utils` at the domain level.

---

## 4. Rules for Adding New Entities

Before creating a new entity, answer all four questions:

### 4.1 Who owns the truth you are modeling?

Check the ownership table in Section 1. If an existing entity already owns this data,
**add a field to that entity** rather than creating a new one.

Examples of wrong additions:
- A `LotQualityScore` entity when `QCReview.result` already captures the decision
- A `CustomerOrderCount` entity when `CustomerProfile.purchase_history` covers it
- A `BatchAvailability` entity when `LotBatch.available_qty` is the source

### 4.2 Does this entity have its own lifecycle?

An entity is justified when it has states that transition independently of its parent.
If it is just an attribute of an existing aggregate, it is a field, not an entity.

Justified: `Allocation` has its own `active → released | cancelled` lifecycle independent of the order or lot.

Not justified: a `LotQuantitySnapshot` with no independent lifecycle.

### 4.3 Does this entity cross a bounded-context boundary?

If data from two bounded contexts must appear together in a read, create a **projection**,
not a new canonical entity. Projections are disposable and rebuildable; canonical entities are not.

### 4.4 Who emits changes, who reads them?

Define at minimum:
- one domain event that fires when this entity is created (`{Entity}Created`)
- one domain event per meaningful state transition
- the role(s) permitted to issue the write command
- the projection(s) that consume this entity's events

If you cannot name these, the entity's scope is not yet well-understood.

### 4.5 Anti-duplication checklist

Before finalizing a new entity, verify:
- [ ] No existing entity already owns this responsibility (Sections 1–2)
- [ ] The new entity has its own lifecycle, not just attributes of an existing aggregate
- [ ] If this crosses context boundaries, a projection is used instead
- [ ] The entity has a clear `{entity}_id` and human-readable `{entity}_code` if user-facing
- [ ] At least one `{Entity}Created` event and one command are defined
- [ ] RBAC permissions for the write command are specified
- [ ] The new entity's ownership boundaries are documented in this file

---

## 5. AI and Agent Integration Contract

The canonical model exists so that AI agents never become the source of truth.

**Agents may:**
- query read models and projections
- propose commands (suggest an allocation, draft an order)
- surface missing evidence alerts

**Agents must not:**
- write directly to canonical tables
- resolve merge conflicts on `CustomerProfile` without human approval
- change lot state without going through the Command Gateway
- update `delivered_qty` on a `Preorder` without a corresponding `OrderDelivered` event

Every agent action that changes state must flow through the Command Gateway, pass policy
checks, and produce a `DomainEvent` with `actor_type = future_ai`. This preserves full
auditability and prevents AI from silently corrupting the deterministic core.
