"""Customer store operations."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import text

from app.store import _db

__all__ = [
    "create_duplicate_candidate",
    "customer_code_exists",
    "customer_exists",
    "fetch_customer",
    "fetch_duplicate_candidate",
    "fetch_customer_preferences",
    "find_potential_duplicate_customers",
    "list_customer_duplicate_candidates",
    "list_duplicate_candidates",
    "list_customers",
    "phone_exists",
    "review_duplicate_candidate",
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


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("84") and len(digits) > 9:
        return f"0{digits[2:]}"
    return digits


def phone_exists(phone: str) -> bool:
    if not _db.is_enabled():
        return False

    normalized_phone = _normalize_phone(phone)

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM customers WHERE phone_normalized = :normalized_phone"),
            {"normalized_phone": normalized_phone},
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
                    phone_normalized,
                    channel_source,
                    default_address,
                    district,
                    province,
                    tags,
                    notes,
                    status,
                    last_order_at,
                    tenant_id,
                    updated_at
                ) VALUES (
                    :customer_id,
                    :customer_code,
                    :full_name,
                    :phone,
                    :phone_normalized,
                    :channel_source,
                    :default_address,
                    :district,
                    :province,
                    CAST(:tags AS jsonb),
                    :notes,
                    :status,
                    CAST(:last_order_at AS timestamptz),
                    :tenant_id,
                    now()
                )
                ON CONFLICT (customer_id) DO UPDATE SET
                    customer_code = EXCLUDED.customer_code,
                    full_name = EXCLUDED.full_name,
                    phone = EXCLUDED.phone,
                    phone_normalized = EXCLUDED.phone_normalized,
                    channel_source = EXCLUDED.channel_source,
                    default_address = EXCLUDED.default_address,
                    district = EXCLUDED.district,
                    province = EXCLUDED.province,
                    tags = EXCLUDED.tags,
                    notes = EXCLUDED.notes,
                    status = EXCLUDED.status,
                    last_order_at = EXCLUDED.last_order_at,
                    updated_at = now()
                """
            ),
            {
                "customer_id": record["customerId"],
                "customer_code": record["customerCode"],
                "full_name": record["fullName"],
                "phone": record["phone"],
                "phone_normalized": _normalize_phone(record["phone"]),
                "channel_source": record.get("channelSource"),
                "default_address": record.get("defaultAddress"),
                "district": record.get("district"),
                "province": record.get("province"),
                "tags": json.dumps(record.get("tags", [])),
                "notes": record.get("notes"),
                "status": record["status"],
                "last_order_at": record.get("lastOrderAt"),
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
        conditions.append("phone_normalized = :phone_normalized")
        params["phone_normalized"] = _normalize_phone(phone)
    if q:
        conditions.append("(full_name ILIKE :query OR phone ILIKE :query OR customer_code ILIKE :query)")
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
                    phone_normalized, channel_source, default_address, district, province,
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
        "phoneNormalized": row["phone_normalized"],
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
                SELECT preference_type, preference_value, source, confidence_level, confirmed_by, confirmed_at
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
            "confirmedBy": row["confirmed_by"],
            "confirmedAt": row["confirmed_at"].isoformat() if row["confirmed_at"] else None,
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
        "confirmed_by": preference.get("confirmedBy"),
        "confirmed_at": preference.get("confirmedAt"),
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
                    confirmed_by = :confirmed_by,
                    confirmed_at = CAST(:confirmed_at AS timestamptz),
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
                        confirmed_by,
                        confirmed_at,
                        updated_at
                    ) VALUES (
                        :preference_id,
                        :tenant_id,
                        :customer_id,
                        :preference_type,
                        :preference_value,
                        :source,
                        :confidence_level,
                        :confirmed_by,
                        CAST(:confirmed_at AS timestamptz),
                        now()
                    )
                    """
                ),
                params,
            )
        if should_commit:
            session.commit()


def find_potential_duplicate_customers(record: dict[str, Any]) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    has_district = bool(record.get("district"))
    has_province = bool(record.get("province"))
    if not has_district and not has_province:
        return []

    params = {
        "customer_id": record["customerId"],
        "full_name": record["fullName"],
    }
    location_clause = ""
    if has_district and has_province:
        location_clause = """
          AND (
            (district IS NOT NULL AND lower(trim(district)) = lower(trim(:district)))
            OR (province IS NOT NULL AND lower(trim(province)) = lower(trim(:province)))
          )
        """
        params["district"] = record["district"]
        params["province"] = record["province"]
    elif has_district:
        location_clause = """
          AND district IS NOT NULL
          AND lower(trim(district)) = lower(trim(:district))
        """
        params["district"] = record["district"]
    else:
        location_clause = """
          AND province IS NOT NULL
          AND lower(trim(province)) = lower(trim(:province))
        """
        params["province"] = record["province"]

    with _db.read_session() as session:
        rows = session.execute(
            text(
                f"""
                SELECT customer_id, customer_code, full_name, phone, district, province, status, tags, created_at
                FROM customers
                WHERE customer_id <> CAST(:customer_id AS uuid)
                  AND lower(trim(regexp_replace(full_name, '\\s+', ' ', 'g'))) = lower(trim(regexp_replace(:full_name, '\\s+', ' ', 'g')))
                  {location_clause}
                ORDER BY created_at DESC, customer_id DESC
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
            "district": row["district"],
            "province": row["province"],
            "status": row["status"],
            "tags": list(row["tags"] or []),
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


def create_duplicate_candidate(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    params = {
        "candidate_id": record["candidateId"],
        "primary_customer_id": record["primaryCustomerId"],
        "suspected_customer_id": record["suspectedCustomerId"],
        "match_reason": record["matchReason"],
        "match_score": record["matchScore"],
        "status": record["status"],
        "evidence_json": json.dumps(record.get("evidence", {})),
        "detected_by": record.get("detectedBy"),
        "reviewed_by": record.get("reviewedBy"),
        "review_note": record.get("note"),
        "detected_at": record.get("detectedAt"),
        "reviewed_at": record.get("reviewedAt"),
    }

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO customer_duplicate_candidates (
                    candidate_id,
                    primary_customer_id,
                    suspected_customer_id,
                    match_reason,
                    match_score,
                    status,
                    evidence_json,
                    detected_by,
                    reviewed_by,
                    review_note,
                    detected_at,
                    reviewed_at
                ) VALUES (
                    CAST(:candidate_id AS uuid),
                    CAST(:primary_customer_id AS uuid),
                    CAST(:suspected_customer_id AS uuid),
                    :match_reason,
                    :match_score,
                    :status,
                    CAST(:evidence_json AS jsonb),
                    :detected_by,
                    :reviewed_by,
                    :review_note,
                    CAST(:detected_at AS timestamptz),
                    CAST(:reviewed_at AS timestamptz)
                )
                ON CONFLICT (primary_customer_id, suspected_customer_id, match_reason, status) DO NOTHING
                """
            ),
            params,
        )
        if should_commit:
            session.commit()


def list_duplicate_candidates() -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT candidate_id, primary_customer_id, suspected_customer_id, match_reason,
                       match_score, status, detected_at, reviewed_at, reviewed_by, review_note
                FROM customer_duplicate_candidates
                ORDER BY detected_at DESC, candidate_id DESC
                """
            )
        ).mappings().all()

    return [_duplicate_candidate_row(row) for row in rows]


def list_customer_duplicate_candidates(customer_id: str) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT candidate_id, primary_customer_id, suspected_customer_id, match_reason,
                       match_score, status, detected_at, reviewed_at, reviewed_by, review_note
                FROM customer_duplicate_candidates
                WHERE primary_customer_id = CAST(:customer_id AS uuid)
                   OR suspected_customer_id = CAST(:customer_id AS uuid)
                ORDER BY detected_at DESC, candidate_id DESC
                """
            ),
            {"customer_id": customer_id},
        ).mappings().all()

    return [_duplicate_candidate_row(row) for row in rows]


def fetch_duplicate_candidate(candidate_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT candidate_id, primary_customer_id, suspected_customer_id, match_reason,
                       match_score, status, detected_at, reviewed_at, reviewed_by, review_note
                FROM customer_duplicate_candidates
                WHERE candidate_id = CAST(:candidate_id AS uuid)
                """
            ),
            {"candidate_id": candidate_id},
        ).mappings().first()

    if row is None:
        return None
    return _duplicate_candidate_row(row)


def review_duplicate_candidate(candidate_id: str, *, status: str, note: str | None, reviewed_by: str | None, reviewed_at: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.write_session() as (session, should_commit):
        updated = session.execute(
            text(
                """
                UPDATE customer_duplicate_candidates
                SET status = :status,
                    review_note = :review_note,
                    reviewed_by = :reviewed_by,
                    reviewed_at = CAST(:reviewed_at AS timestamptz)
                WHERE candidate_id = CAST(:candidate_id AS uuid)
                RETURNING candidate_id, primary_customer_id, suspected_customer_id, match_reason,
                          match_score, status, detected_at, reviewed_at, reviewed_by, review_note
                """
            ),
            {
                "candidate_id": candidate_id,
                "status": status,
                "review_note": note,
                "reviewed_by": reviewed_by,
                "reviewed_at": reviewed_at,
            },
        ).mappings().first()
        if should_commit:
            session.commit()

    if updated is None:
        return None
    return _duplicate_candidate_row(updated)


def _duplicate_candidate_row(row: Any) -> dict[str, Any]:
    return {
        "candidateId": str(row["candidate_id"]),
        "primaryCustomerId": str(row["primary_customer_id"]),
        "suspectedCustomerId": str(row["suspected_customer_id"]),
        "matchReason": row["match_reason"],
        "matchScore": _float_value(row["match_score"]),
        "status": row["status"],
        "detectedAt": row["detected_at"].isoformat() if row["detected_at"] else None,
        "reviewedAt": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
        "reviewedBy": row["reviewed_by"],
        "note": row["review_note"],
    }


