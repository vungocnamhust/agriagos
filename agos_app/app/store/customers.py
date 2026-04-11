"""Customer store operations."""
from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from app.store import _db

__all__ = [
    "customer_code_exists",
    "customer_exists",
    "fetch_customer",
    "fetch_customer_preferences",
    "list_customers",
    "phone_exists",
    "upsert_customer",
    "upsert_customer_preference",
]


def customer_exists(customer_id: str) -> bool:
    if not _db.is_enabled():
        return False

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM customers WHERE customer_id = :customer_id"),
            {"customer_id": customer_id},
        ).first()
    return row is not None


def customer_code_exists(customer_code: str) -> bool:
    if not _db.is_enabled():
        return False

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM customers WHERE customer_code = :customer_code"),
            {"customer_code": customer_code},
        ).first()
    return row is not None


def phone_exists(phone: str) -> bool:
    if not _db.is_enabled():
        return False

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM customers WHERE phone = :phone"),
            {"phone": phone},
        ).first()
    return row is not None


def _float_value(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def upsert_customer(record: dict[str, Any]) -> None:
    """Upsert a customer record. No-op if postgres is disabled."""
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO customers (
                    customer_id,
                    customer_code,
                    full_name,
                    phone,
                    channel_source,
                    default_address,
                    district,
                    province,
                    tags,
                    notes,
                    status,
                    tenant_id,
                    updated_at
                ) VALUES (
                    :customer_id,
                    :customer_code,
                    :full_name,
                    :phone,
                    :channel_source,
                    :default_address,
                    :district,
                    :province,
                    CAST(:tags AS jsonb),
                    :notes,
                    :status,
                    :tenant_id,
                    now()
                )
                ON CONFLICT (customer_id) DO UPDATE SET
                    customer_code = EXCLUDED.customer_code,
                    full_name = EXCLUDED.full_name,
                    phone = EXCLUDED.phone,
                    channel_source = EXCLUDED.channel_source,
                    default_address = EXCLUDED.default_address,
                    district = EXCLUDED.district,
                    province = EXCLUDED.province,
                    tags = EXCLUDED.tags,
                    notes = EXCLUDED.notes,
                    status = EXCLUDED.status,
                    updated_at = now()
                """
            ),
            {
                "customer_id": record["customerId"],
                "customer_code": record["customerCode"],
                "full_name": record["fullName"],
                "phone": record["phone"],
                "channel_source": record.get("channelSource"),
                "default_address": record.get("defaultAddress"),
                "district": record.get("district"),
                "province": record.get("province"),
                "tags": json.dumps(record.get("tags", [])),
                "notes": record.get("notes"),
                "status": record["status"],
                "tenant_id": record.get("tenantId", "default"),
            },
        )
        if should_commit:
            session.commit()


def list_customers(
    phone: str | None,
    q: str | None,
    tag: str | None,
) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    conditions: list[str] = []
    params: dict[str, Any] = {}
    if phone:
        conditions.append("phone = :phone")
        params["phone"] = phone
    if q:
        conditions.append("(full_name ILIKE :query OR phone ILIKE :query)")
        params["query"] = f"%{q}%"
    if tag:
        conditions.append("tags @> CAST(:tag_filter AS jsonb)")
        params["tag_filter"] = json.dumps([tag])

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    with _db.read_session() as session:
        rows = session.execute(
            text(
                f"""
                SELECT
                    customer_id,
                    customer_code,
                    full_name,
                    phone,
                    status,
                    created_at,
                    tags
                FROM customers
                {where_clause}
                ORDER BY created_at DESC
                """
            ),
            params,
        ).mappings().all()

    return [
        {
            "customerId": str(row["customer_id"]),
            "customerCode": row["customer_code"],
            "fullName": row["full_name"],
            "phone": row["phone"],
            "status": row["status"],
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
            "tags": list(row["tags"] or []),
        }
        for row in rows
    ]


def fetch_customer(customer_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    customer_id, tenant_id, customer_code, full_name, phone,
                    channel_source, default_address, district, province,
                    notes, status, tags, last_order_at, created_at
                FROM customers
                WHERE customer_id = :customer_id
                """
            ),
            {"customer_id": customer_id},
        ).mappings().first()

    if row is None:
        return None

    return {
        "customerId": str(row["customer_id"]),
        "tenantId": row["tenant_id"],
        "customerCode": row["customer_code"],
        "fullName": row["full_name"],
        "phone": row["phone"],
        "channelSource": row["channel_source"],
        "defaultAddress": row["default_address"],
        "district": row["district"],
        "province": row["province"],
        "notes": row["notes"],
        "status": row["status"],
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "tags": list(row["tags"] or []),
        "lastOrderAt": row["last_order_at"].isoformat() if row["last_order_at"] else None,
    }


def fetch_customer_preferences(customer_id: str) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT preference_type, preference_value, source, confidence_level
                FROM customer_preferences
                WHERE customer_id = :customer_id
                ORDER BY updated_at DESC, preference_type ASC
                """
            ),
            {"customer_id": customer_id},
        ).mappings().all()

    return [
        {
            "preferenceType": row["preference_type"],
            "preferenceValue": row["preference_value"],
            "source": row["source"],
            "confidenceLevel": _float_value(row["confidence_level"]),
        }
        for row in rows
    ]


def upsert_customer_preference(customer_id: str, preference: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    params = {
        "preference_id": str(uuid.uuid4()),
        "tenant_id": preference.get("tenantId", "default"),
        "customer_id": customer_id,
        "preference_type": preference["preferenceType"],
        "preference_value": preference["preferenceValue"],
        "source": preference.get("source", "human"),
        "confidence_level": preference.get("confidenceLevel", 1.0),
    }

    with _db.write_session() as (session, should_commit):
        updated = session.execute(
            text(
                """
                UPDATE customer_preferences
                SET
                    preference_value = :preference_value,
                    source = :source,
                    confidence_level = :confidence_level,
                    updated_at = now()
                WHERE customer_id = :customer_id
                  AND preference_type = :preference_type
                """
            ),
            params,
        )
        if getattr(updated, "rowcount", 0) == 0:
            session.execute(
                text(
                    """
                    INSERT INTO customer_preferences (
                        preference_id,
                        tenant_id,
                        customer_id,
                        preference_type,
                        preference_value,
                        source,
                        confidence_level,
                        updated_at
                    ) VALUES (
                        :preference_id,
                        :tenant_id,
                        :customer_id,
                        :preference_type,
                        :preference_value,
                        :source,
                        :confidence_level,
                        now()
                    )
                    """
                ),
                params,
            )
        if should_commit:
            session.commit()


