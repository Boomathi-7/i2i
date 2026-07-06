import time
from pathlib import Path
from uuid import uuid4

import cv2
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import RESULTS_DIR, STATIC_DIR
from app.models import AnalysisResponse, ChangedRegion, DifferenceStatistics, AnalysisOutputs, RegionImages
from app.services.difference import analyze_images
from app.services.image_io import read_upload_bytes, upload_to_bgr, validate_upload
from app.services.report import build_pdf_report, build_html_report
from app.services.summary import build_engineering_summary

app = FastAPI(title="AI-Based Image Difference Detection API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze(reference: UploadFile = File(...), comparison: UploadFile = File(...)) -> AnalysisResponse:
    start_time = time.time()
    
    reference_suffix = validate_upload(reference)
    comparison_suffix = validate_upload(comparison)
    reference_data = await read_upload_bytes(reference)
    comparison_data = await read_upload_bytes(comparison)

    image_a = upload_to_bgr(reference_data, reference_suffix)
    image_b = upload_to_bgr(comparison_data, comparison_suffix)
    job_id = uuid4().hex
    job_dir = RESULTS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    result = analyze_images(image_a, image_b, job_dir=job_dir)

    paths = {
        "image_a": job_dir / "reference.png",
        "image_b": job_dir / "comparison_aligned.png",
        "side_by_side": job_dir / "side_by_side.png",
        "heatmap": job_dir / "heatmap.png",
        "overlay": job_dir / "changed_regions.png",
        "mask": job_dir / "difference_mask.png",
        "roi_mask": job_dir / "roi_mask.png",
        "detected_regions": job_dir / "detected_regions.png",
    }
    cv2.imwrite(str(paths["image_a"]), result.image_a)
    cv2.imwrite(str(paths["image_b"]), result.aligned_b)
    cv2.imwrite(str(paths["side_by_side"]), result.side_by_side)
    cv2.imwrite(str(paths["heatmap"]), result.heatmap)
    cv2.imwrite(str(paths["overlay"]), result.overlay)
    cv2.imwrite(str(paths["mask"]), result.mask)
    cv2.imwrite(str(paths["roi_mask"]), result.roi_mask)
    cv2.imwrite(str(paths["detected_regions"]), result.detected_regions)

    regions = []
    for r in result.regions:
        regions.append(
            ChangedRegion(
                id=r.id,
                confidence=r.confidence_score,
                severity=r.severity,
                bbox=[r.x, r.y, r.width, r.height],
                area=r.area_pixels,
                center=[r.centroid_x, r.centroid_y],
                images=RegionImages(
                    before=f"/static/results/{job_id}/crops/R_{r.id}_ref.png",
                    after=f"/static/results/{job_id}/crops/R_{r.id}_cmp.png",
                    mask=f"/static/results/{job_id}/crops/R_{r.id}_mask.png",
                    overlay=f"/static/results/{job_id}/crops/R_{r.id}_edge.png",
                )
            )
        )

    processing_time = round(time.time() - start_time, 2)
    similarity = round(max(0.0, 100.0 - result.changed_percentage), 2)
    
    statistics = DifferenceStatistics(
        total_changes=len(regions),
        changed_area_percent=result.changed_percentage,
        similarity=similarity,
        processing_time=processing_time,
    )
    
    report_path = job_dir / "civil_engineering_change_report.pdf"
    report_html_path = job_dir / "report.html"

    outputs = AnalysisOutputs(
        annotated_image=_url(paths["overlay"]),
        difference_mask=_url(paths["mask"]),
        heatmap=_url(paths["heatmap"]),
        roi_mask=_url(paths["roi_mask"]),
        detected_regions=_url(paths["detected_regions"]),
        reference_image=_url(paths["image_a"]),
        aligned_image=_url(paths["image_b"]),
        report_pdf=_url(report_path),
        report_html=_url(report_html_path)
    )

    summary = build_engineering_summary(result.regions, result.changed_percentage, result.alignment_status, result.confidence)

    response = AnalysisResponse(
        status="success",
        summary=summary,
        statistics=statistics,
        regions=regions,
        outputs=outputs
    )
    
    build_pdf_report(response, report_path, paths)
    build_html_report(response, report_html_path, paths)
    
    return response


def _url(path: Path) -> str:
    return "/" + path.relative_to(STATIC_DIR.parent).as_posix()

