"""Farm summary store operations."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.store import _db

__all__ = ["fetch_crop_cycle", "fetch_crop_cycles", "fetch_plot", "fetch_plots", "is_enabled"]


def is_enabled() -> bool:
    return _db.is_enabled()


def _normalize_growth_stage(value: str | None) -> str | None:
    if value == "flowering_or_maturing":
        return "maturing"
    return value


def fetch_plots() -> list[dict[str, Any]]:
    if not is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    plot_id,
                    plot_code,
                    organization_id,
                    name,
                    location_text,
                    area_value,
                    area_unit,
                    status
                FROM plots
                ORDER BY plot_code
                """
            )
        ).mappings().all()

    return [
        {
            "plotId": str(row["plot_id"]),
            "plotCode": row["plot_code"],
            "organizationId": str(row["organization_id"]) if row["organization_id"] is not None else None,
            "name": row["name"],
            "locationText": row["location_text"],
            "areaValue": _db.to_float(row["area_value"]),
            "areaUnit": row["area_unit"],
            "status": row["status"],
        }
        for row in rows
    ]


def fetch_plot(plot_id: str) -> dict[str, Any] | None:
    if not is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    plot_id,
                    plot_code,
                    organization_id,
                    name,
                    location_text,
                    area_value,
                    area_unit,
                    status
                FROM plots
                WHERE plot_id = CAST(:plot_id AS uuid)
                """
            ),
            {"plot_id": plot_id},
        ).mappings().first()

    if row is None:
        return None

    return {
        "plotId": str(row["plot_id"]),
        "plotCode": row["plot_code"],
        "organizationId": str(row["organization_id"]) if row["organization_id"] is not None else None,
        "name": row["name"],
        "locationText": row["location_text"],
        "areaValue": _db.to_float(row["area_value"]),
        "areaUnit": row["area_unit"],
        "status": row["status"],
    }


def fetch_crop_cycles(plot_id: str | None, status: str | None) -> list[dict[str, Any]]:
    if not is_enabled():
        return []

    where_clauses: list[str] = []
    params: dict[str, Any] = {}
    if plot_id is not None:
        where_clauses.append("plot_id = CAST(:plot_id AS uuid)")
        params["plot_id"] = plot_id
    if status is not None:
        where_clauses.append("status = :status")
        params["status"] = status

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    with _db.read_session() as session:
        rows = session.execute(
            text(
                f"""
                SELECT
                    crop_cycle_id,
                    plot_id,
                    organization_id,
                    crop_name,
                    growth_stage,
                    status,
                    expected_harvest_from,
                    expected_harvest_to
                FROM crop_cycles
                {where_sql}
                ORDER BY expected_harvest_from NULLS LAST, crop_cycle_id
                """
            ),
            params,
        ).mappings().all()

    return [
        {
            "cropCycleId": str(row["crop_cycle_id"]),
            "plotId": str(row["plot_id"]),
            "organizationId": str(row["organization_id"]) if row["organization_id"] is not None else None,
            "cropName": row["crop_name"],
            "growthStage": _normalize_growth_stage(row["growth_stage"]),
            "status": row["status"],
            "expectedHarvestFrom": (
                row["expected_harvest_from"].isoformat()
                if row["expected_harvest_from"] else None
            ),
            "expectedHarvestTo": (
                row["expected_harvest_to"].isoformat()
                if row["expected_harvest_to"] else None
            ),
        }
        for row in rows
    ]


def fetch_crop_cycle(crop_cycle_id: str) -> dict[str, Any] | None:
    if not is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    crop_cycle_id,
                    plot_id,
                    organization_id,
                    crop_name,
                    growth_stage,
                    status,
                    expected_harvest_from,
                    expected_harvest_to
                FROM crop_cycles
                WHERE crop_cycle_id = CAST(:crop_cycle_id AS uuid)
                """
            ),
            {"crop_cycle_id": crop_cycle_id},
        ).mappings().first()

    if row is None:
        return None

    return {
        "cropCycleId": str(row["crop_cycle_id"]),
        "plotId": str(row["plot_id"]),
        "organizationId": str(row["organization_id"]) if row["organization_id"] is not None else None,
        "cropName": row["crop_name"],
        "growthStage": _normalize_growth_stage(row["growth_stage"]),
        "status": row["status"],
        "expectedHarvestFrom": row["expected_harvest_from"].isoformat() if row["expected_harvest_from"] else None,
        "expectedHarvestTo": row["expected_harvest_to"].isoformat() if row["expected_harvest_to"] else None,
    }