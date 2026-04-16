import uuid
from typing import Any

from app.models.common import Meta
from app.models.project_assignments import ProjectAssignmentSummary
from app.services.read_authz import authorize_read_surface
from app.store import farm as farm_store
from app.store import postgres_sync
from app.store import memory as store
from app.store import project_assignments as project_assignment_store


def list_plots() -> list[dict[str, Any]]:
    if postgres_sync.is_enabled():
        return farm_store.fetch_plots()
    return store.list_plots()


def list_crop_cycles(plot_id: str | None, status: str | None) -> list[dict[str, Any]]:
    if postgres_sync.is_enabled():
        return farm_store.fetch_crop_cycles(plot_id, status)
    items = store.list_crop_cycles()
    if plot_id:
        items = [c for c in items if c.get("plotId") == plot_id]
    if status:
        items = [c for c in items if c.get("status") == status]
    return items


def list_plots_for_actor(meta: Meta | None) -> list[dict[str, Any]]:
    authorize_read_surface(
        meta=meta,
        action_name="farm.plot.list",
        target_type="Plot",
        target_id="all",
        allowed_roles={"founder", "super_admin", "admin", "ops", "farm_manager"},
        reason_code="forbidden_farm_plot_read",
        detail="Actor is not allowed to list raw farm plots.",
    )
    return [_with_assignments(plot, "plot", plot["plotId"]) for plot in list_plots()]


def list_crop_cycles_for_actor(plot_id: str | None, status: str | None, meta: Meta | None) -> list[dict[str, Any]]:
    authorize_read_surface(
        meta=meta,
        action_name="farm.crop_cycle.list",
        target_type="CropCycle",
        target_id=plot_id or status or "all",
        allowed_roles={"founder", "super_admin", "admin", "ops", "farm_manager"},
        reason_code="forbidden_crop_cycle_read",
        detail="Actor is not allowed to list raw crop cycles.",
    )
    return [_with_assignments(cycle, "crop_cycle", cycle["cropCycleId"]) for cycle in list_crop_cycles(plot_id, status)]


def _with_assignments(record: dict[str, Any], target_type: str, target_id: str) -> dict[str, Any]:
    enriched = dict(record)
    enriched["assignments"] = _list_assignment_summaries(target_type, target_id)
    return enriched


def _list_assignment_summaries(target_type: str, target_id: str) -> list[ProjectAssignmentSummary]:
    records = (
        project_assignment_store.list_project_assignments_for_target(target_type, target_id)
        if postgres_sync.is_enabled()
        else store.list_project_assignments_for_target(target_type, target_id)
    )
    return [ProjectAssignmentSummary(**record) for record in records]


def seed_demo_farm() -> None:
    """Populate demo plot and crop cycle data so the farm view is non-empty on first run."""
    if store.list_plots():
        return

    plot_id = str(uuid.uuid4())
    store.save_plot(plot_id, {
        "plotId": plot_id,
        "plotCode": "PLOT-001",
        "name": "Vườn A1",
        "locationText": "Đà Lạt, Lâm Đồng",
        "areaValue": 2.5,
        "areaUnit": "ha",
    })

    cycle_id = str(uuid.uuid4())
    store.save_crop_cycle(cycle_id, {
        "cropCycleId": cycle_id,
        "plotId": plot_id,
        "cropName": "Dâu tây",
        "growthStage": "maturing",   # GrowthStage.maturing — closest valid enum to "flowering"
        "status": "active",          # CropCycleStatus.active
        "expectedHarvestFrom": "2026-05-01",
        "expectedHarvestTo": "2026-05-15",
    })
