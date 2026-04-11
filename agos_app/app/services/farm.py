import uuid
from typing import Any

from app.store import farm as farm_store
from app.store import postgres_sync
from app.store import memory as store


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
