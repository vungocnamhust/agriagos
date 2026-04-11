"""Backward-compatibility shim — implementations moved to per-entity store modules.

New code should import from those modules directly:
  from app.store.customers import upsert_customer, fetch_customer
  from app.store.orders   import upsert_order, fetch_order
  from app.store.lots     import upsert_lot, fetch_lot
  from app.store.preorders import upsert_preorder, fetch_preorder
"""
from __future__ import annotations

from app.store._db import is_enabled
from app.store.customers import customer_exists, fetch_customer, upsert_customer
from app.store.lots import fetch_lot, upsert_lot
from app.store.orders import (
    allocate_order_atomic,
    cancel_order_atomic,
    fetch_allocations_for_order,
    fetch_order,
    replace_allocations_for_order,
    upsert_order,
)
from app.store.preorders import (
    fetch_preorder,
    increment_delivered_qty_atomic,
    upsert_preorder,
)

# Backward-compat alias — old callers used this longer name
increment_preorder_delivered_qty_atomic = increment_delivered_qty_atomic

__all__ = [
    "is_enabled",
    "customer_exists",
    "upsert_customer",
    "fetch_customer",
    "upsert_preorder",
    "fetch_preorder",
    "increment_delivered_qty_atomic",
    "increment_preorder_delivered_qty_atomic",
    "upsert_lot",
    "fetch_lot",
    "upsert_order",
    "fetch_order",
    "fetch_allocations_for_order",
    "replace_allocations_for_order",
    "allocate_order_atomic",
    "cancel_order_atomic",
]
