"""
Single source of truth for all domain state values.
Matches state-transitions.md exactly — do not add states here without updating that doc.
"""
from enum import Enum


class CustomerStatus(str, Enum):
    active = "active"
    inactive = "inactive"
    blocked = "blocked"


class PreorderStatus(str, Enum):
    draft = "draft"
    confirmed = "confirmed"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class OrderStatus(str, Enum):
    draft = "draft"
    confirmed = "confirmed"
    allocated = "allocated"
    partially_allocated = "partially_allocated"
    packed = "packed"
    partially_packed = "partially_packed"
    shipped = "shipped"
    delivered = "delivered"
    partially_delivered = "partially_delivered"
    cancel_requested = "cancel_requested"
    cancelled = "cancelled"
    failed = "failed"


class OrderLineStatus(str, Enum):
    open = "open"
    allocated = "allocated"
    packed = "packed"
    delivered = "delivered"
    cancelled = "cancelled"


class LotStatus(str, Enum):
    draft = "draft"
    harvested = "harvested"
    qc_pending = "qc_pending"
    released = "released"
    blocked = "blocked"
    depleted = "depleted"
    closed = "closed"


class AllocationStatus(str, Enum):
    active = "active"
    released = "released"
    consumed = "consumed"
    cancelled = "cancelled"


class DeliveryStatus(str, Enum):
    pending = "pending"
    shipped = "shipped"
    delivered = "delivered"
    partially_delivered = "partially_delivered"
    failed = "failed"
    returned = "returned"


class PaymentStatus(str, Enum):
    unpaid = "unpaid"
    partially_paid = "partially_paid"
    paid = "paid"
    refunded = "refunded"
    writeoff = "writeoff"


class CropCycleStatus(str, Enum):
    planned = "planned"
    active = "active"
    near_harvest = "near_harvest"
    harvested = "harvested"
    closed = "closed"
    cancelled = "cancelled"


class GrowthStage(str, Enum):
    seeded = "seeded"
    growing = "growing"
    maturing = "maturing"
    harvest_window = "harvest_window"
    harvested = "harvested"


class EventSource(str, Enum):
    core = "core"
    integration = "integration"
    system_job = "system_job"
    agent = "agent"


class SyncStatus(str, Enum):
    pending = "pending"
    synced = "synced"
    failed = "failed"
    needs_review = "needs_review"
