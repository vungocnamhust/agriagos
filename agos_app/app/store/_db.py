"""Shared database helpers for store modules."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from typing import Any, Iterator

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal

__all__ = [
    "is_enabled",
    "to_float",
    "_to_float",
    "SessionLocal",
    "current_session",
    "read_session",
    "write_session",
    "transaction",
]

_CURRENT_SESSION: ContextVar[Session | None] = ContextVar("agri_os_store_session", default=None)


def is_enabled() -> bool:
    return settings.postgres_write_path_enabled


def _to_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    if value is None:
        return 0.0
    return float(value)


def to_float(value: Any) -> float:
    return _to_float(value)


def current_session() -> Session | None:
    return _CURRENT_SESSION.get()


@contextmanager
def read_session(session: Session | None = None) -> Iterator[Session]:
    bound_session = session or current_session()
    if bound_session is not None:
        yield bound_session
        return

    local_session = SessionLocal()
    try:
        yield local_session
    finally:
        local_session.close()


@contextmanager
def write_session(session: Session | None = None) -> Iterator[tuple[Session, bool]]:
    bound_session = session or current_session()
    if bound_session is not None:
        yield bound_session, False
        return

    local_session = SessionLocal()
    try:
        yield local_session, True
    except Exception:
        local_session.rollback()
        raise
    finally:
        local_session.close()


@contextmanager
def transaction(session: Session | None = None) -> Iterator[Session]:
    bound_session = session or current_session()
    if bound_session is not None:
        yield bound_session
        return

    local_session = SessionLocal()
    token = _CURRENT_SESSION.set(local_session)
    try:
        yield local_session
        local_session.commit()
    except Exception:
        local_session.rollback()
        raise
    finally:
        _CURRENT_SESSION.reset(token)
        local_session.close()
