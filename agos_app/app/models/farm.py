from pydantic import BaseModel

class PlotSummary(BaseModel):
    plotId: str
    plotCode: str
    name: str
    locationText: str | None = None
    areaValue: float
    areaUnit: str

class CropCycleSummary(BaseModel):
    cropCycleId: str
    plotId: str
    cropName: str
    growthStage: str
    status: str
    expectedHarvestFrom: str | None = None
    expectedHarvestTo: str | None = None

class FarmView(BaseModel):
    plots: list[PlotSummary]
    cropCycles: list[CropCycleSummary]
