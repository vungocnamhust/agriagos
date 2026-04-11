"""Durable idempotency storage."""
from __future__ import annotations

import json
from enum import Enum
from typing import Any

from sqlalchemy import text

from app.store._db import SessionLocal, is_enabled


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    isoformat = getattr(value, "isoformat", None)
    if callable(isoformat):
        return isoformat()
    return str(value)


def fetch_response(idempotency_key: str) -> Any | None:
    if not is_enabled():
        return None

    with SessionLocal() as session:
        row = session.execute(
            text(
                """
                SELECT response_snapshot
                FROM idempotency_records
                WHERE idempotency_key = :idempotency_key
                  AND (expires_at IS NULL OR expires_at > now())
                """
            ),
            {"idempotency_key": idempotency_key},
        ).mappings().first()

    if row is None:
        return None
    return row["response_snapshot"]


def save_response(idempotency_key: str, result: Any) -> None:
    if not is_enabled():
        return

    with SessionLocal() as session:
        try:
            session.execute(
                text(
                    """
                    INSERT INTO idempotency_records (
                        idempotency_key,
                        operation_name,
                        request_hash,
                        response_snapshot,
                        expires_at
                    ) VALUES (
                        :idempotency_key,
                        :operation_name,
                        :request_hash,
                        CAST(:response_snapshot AS jsonb),
                        now() + interval '24 hours'
                    )
                    ON CONFLICT (idempotency_key) DO NOTHING
                    """
                ),
                {
                    "idempotency_key": idempotency_key,
                    "operation_name": "core.write",
                    "request_hash": idempotency_key,
                    "response_snapshot": json.dumps(result, default=_json_default),
                },
            )
            session.commit()
        except Exception:
            session.rollback()
            raise