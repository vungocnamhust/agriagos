"""Centralized human-readable code generation for canonical entities.

Phase 1: in-memory sequence counter per (entity_prefix, YYYYMM).
Phase 2: replace _next_seq() with a DB sequence SELECT nextval() per (entity, month).

Format reference (ADR-010):
    Organization: ORG-YYYYMM-0001
  Customer:  KH-YYYYMM-0001
  Preorder:  DT-YYYYMM-0001
  Order:     ORD-YYYYMM-0001
  Lot:       LOT-{SKU}-YYYYMM-001
  Plot:      VU-001
"""
from __future__ import annotations

from datetime import datetime, timezone

# In-memory counters: key = "{prefix}-{YYYYMM}", value = last seq used.
# Reset on process restart — acceptable for Phase 1 single-process deployment.
_counters: dict[str, int] = {}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _next_seq(prefix: str, now: datetime) -> int:
    key = f"{prefix}-{now:%Y%m}"
    _counters[key] = _counters.get(key, 0) + 1
    return _counters[key]


def generate_customer_code(now: datetime | None = None) -> str:
    t = now or _now()
    return f"KH-{t:%Y%m}-{_next_seq('KH', t):04d}"


def generate_organization_code(now: datetime | None = None) -> str:
    t = now or _now()
    return f"ORG-{t:%Y%m}-{_next_seq('ORG', t):04d}"


def generate_project_scope_code(now: datetime | None = None) -> str:
    t = now or _now()
    return f"PRJ-{t:%Y%m}-{_next_seq('PRJ', t):04d}"


def generate_shared_resource_code(now: datetime | None = None) -> str:
    t = now or _now()
    return f"RES-{t:%Y%m}-{_next_seq('RES', t):04d}"


def generate_actor_code(now: datetime | None = None) -> str:
    t = now or _now()
    return f"ACT-{t:%Y%m}-{_next_seq('ACT', t):04d}"


def generate_preorder_code(now: datetime | None = None) -> str:
    t = now or _now()
    return f"DT-{t:%Y%m}-{_next_seq('DT', t):04d}"


def generate_order_code(now: datetime | None = None) -> str:
    t = now or _now()
    return f"ORD-{t:%Y%m}-{_next_seq('ORD', t):04d}"


def generate_lot_code(sku_abbr: str, now: datetime | None = None) -> str:
    t = now or _now()
    return f"LOT-{sku_abbr.upper()}-{t:%Y%m}-{_next_seq('LOT', t):03d}"


def generate_plot_code(seq: int) -> str:
    return f"VU-{seq:03d}"
