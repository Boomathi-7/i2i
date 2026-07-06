from pydantic import BaseModel


class RegionImages(BaseModel):
    before: str
    after: str
    mask: str
    overlay: str


class ChangedRegion(BaseModel):
    id: int
    confidence: float
    severity: str
    bbox: list[int]
    area: int
    center: list[float]
    images: RegionImages


class DifferenceStatistics(BaseModel):
    total_changes: int
    changed_area_percent: float
    similarity: float
    processing_time: float


class AnalysisOutputs(BaseModel):
    annotated_image: str
    difference_mask: str
    heatmap: str
    roi_mask: str
    detected_regions: str
    reference_image: str
    aligned_image: str
    report_pdf: str
    report_html: str


class AnalysisResponse(BaseModel):
    status: str
    summary: str = ""
    statistics: DifferenceStatistics
    regions: list[ChangedRegion]
    outputs: AnalysisOutputs

