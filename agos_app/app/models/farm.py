from pydantic import BaseModel
from app.models.enums import CropCycleStatus, GrowthStage

class PlotSummary(BaseModel):
    plotId: str
    plotCode: str
    name: str
    locationText: str | None = None
    areaValue: float
    areaUnit: str
    status: str = "active"  # plot status not in state-transitions.md yet — plain str for now

class CropCycleSummary(BaseModel):
    cropCycleId: str
    plotId: str
    cropName: str
    growthStage: GrowthStage  # (06-state-transitions.md)
    status: CropCycleStatus  # (06-state-transitions.md)
    expectedHarvestFrom: str | None = None
    expectedHarvestTo: str | None = None

class FarmView(BaseModel):
    plots: list[PlotSummary]
    cropCycles: list[CropCycleSummary]
