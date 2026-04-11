"""Shared database helpers for store modules."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.config import settings
from app.db.session import SessionLocal

__all__ = ["is_enabled", "_to_float", "SessionLocal"]


def is_enabled() -> bool:
    return settings.postgres_write_path_enabled


def _to_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    if value is None:
        return 0.0
    return float(value)
