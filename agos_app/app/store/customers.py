"""Customer store operations."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.store._db import SessionLocal, _to_float, is_enabled

__all__ = ["customer_exists"]


def customer_exists(customer_id: str) -> bool:
    if not is_enabled():
        return False

    with SessionLocal() as session:
        row = session.execute(
            text("SELECT 1 FROM customers WHERE customer_id = :customer_id"),
            {"customer_id": customer_id},
        ).first()
    return row is not None


def upsert_customer(record: dict[str, Any]) -> None:
    """Upsert a customer record. No-op if postgres is disabled."""
    if not is_enabled():
        return

    with SessionLocal() as session:
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
                "notes": record.get("notes"),
                "status": record["status"],
                "tenant_id": record.get("tenantId", "default"),
            },
        )
        session.commit()


def fetch_customer(customer_id: str) -> dict[str, Any] | None:
    if not is_enabled():
        return None

    with SessionLocal() as session:
        row = session.execute(
            text(
                """
                SELECT
                    customer_id, customer_code, full_name, phone,
                    channel_source, default_address, district, province,
                    notes, status, created_at
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
        "customerCode": row["customer_code"],
        "fullName": row["full_name"],
        "phone": row["phone"],
        "channelSource": row["channel_source"],
        "defaultAddress": row["default_address"],
        "district": row["district"],
        "province": row["province"],
        "notes": row["notes"],
        "status": row["status"],
    }


# Suppress unused import warning — _to_float imported for consistency across store modules
_ = _to_float
