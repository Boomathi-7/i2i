from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.services.roi_detection import detect_drawing_rois


@dataclass
class Region:
    id: int
    x: int
    y: int
    width: int
    height: int
    area_pixels: int
    location: str
    severity: str
    centroid_x: float = 0.0
    centroid_y: float = 0.0
    confidence_score: float = 1.0
    relative_position: str = ""


@dataclass
class DifferenceResult:
    image_a: np.ndarray
    image_b: np.ndarray
    aligned_b: np.ndarray
    mask: np.ndarray
    heatmap: np.ndarray
    overlay: np.ndarray
    side_by_side: np.ndarray
    regions: list[Region]
    changed_percentage: float
    changed_area_pixels: int
    total_area_pixels: int
    alignment_status: str
    confidence: str
    roi_mask: np.ndarray
    detected_regions: np.ndarray


def _skeletonize(img: np.ndarray) -> np.ndarray:
    # Morphological skeletonization / thinning
    size = np.size(img)
    skel = np.zeros(img.shape, np.uint8)
    element = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    temp = np.zeros(img.shape, np.uint8)
    
    img_copy = img.copy()
    while True:
        cv2.morphologyEx(img_copy, cv2.MORPH_OPEN, element, dst=temp)
        cv2.subtract(img_copy, temp, dst=temp)
        cv2.bitwise_or(skel, temp, dst=skel)
        cv2.erode(img_copy, element, dst=img_copy)
        if cv2.countNonZero(img_copy) == 0:
            break
    return skel


def _find_coarse_candidates(gray_a: np.ndarray, gray_b: np.ndarray, tile_size: int = 96) -> list[tuple[int, int, int, int]]:
    # Stage 1: Coarse tile screening via edge changes
    edges_a = cv2.Canny(gray_a, 50, 150)
    edges_b = cv2.Canny(gray_b, 50, 150)
    edge_diff = cv2.absdiff(edges_a, edges_b)
    
    h, w = gray_a.shape
    candidates = np.zeros((h // tile_size + 1, w // tile_size + 1), dtype=np.uint8)
    
    for ty in range(h // tile_size + 1):
        for tx in range(w // tile_size + 1):
            y1, y2 = ty * tile_size, min(h, (ty + 1) * tile_size)
            x1, x2 = tx * tile_size, min(w, (tx + 1) * tile_size)
            if y2 - y1 <= 0 or x2 - x1 <= 0:
                continue
            tile_diff = edge_diff[y1:y2, x1:x2]
            if np.mean(tile_diff > 0) >= 0.012:
                candidates[ty, tx] = 255
                
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(candidates)
    boxes = []
    for i in range(1, num_labels):
        tx, ty, tw, th, area = stats[i]
        bx = tx * tile_size
        by = ty * tile_size
        bw = tw * tile_size
        bh = th * tile_size
        bx = max(0, bx)
        by = max(0, by)
        bw = min(w - bx, bw)
        bh = min(h - by, bh)
        boxes.append((bx, by, bw, bh))
    return boxes


def _subdivide_region(bx: int, by: int, bw: int, bh: int, mask: np.ndarray, regions_list: list[tuple[int, int, int, int, int]]):
    # Stage 3: Split large merged regions recursively
    max_size = 160
    crop = mask[by:by+bh, bx:bx+bw]
    area = int(cv2.countNonZero(crop))
    
    if area < 100:
        return
        
    if bw > max_size and bw >= bh:
        # Split horizontally
        half = bw // 2
        _subdivide_region(bx, by, half, bh, mask, regions_list)
        _subdivide_region(bx + half, by, bw - half, bh, mask, regions_list)
    elif bh > max_size:
        # Split vertically
        half = bh // 2
        _subdivide_region(bx, by, bw, half, mask, regions_list)
        _subdivide_region(bx, by + half, bw, bh - half, mask, regions_list)
    else:
        # Region is small enough, store it
        regions_list.append((bx, by, bw, bh, area))


def _segment_difference_mask(mask: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    # Separation logic combining Connected Components, Watershed, and subdivision
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = mask.shape[0] * mask.shape[1]
    min_area = max(100, int(image_area * 0.0001))
    
    final_regions = []
    
    for contour in contours:
        area = int(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        if w < 10 or h < 10:
            continue
            
        # If component is massive, try Watershed separation using distance peaks
        if w > 120 or h > 120:
            crop = mask[y:y+h, x:x+w]
            dist = cv2.distanceTransform(crop, cv2.DIST_L2, 5)
            dist_max = dist.max()
            if dist_max > 0:
                _, peaks = cv2.threshold(dist, 0.35 * dist_max, 255, cv2.THRESH_BINARY)
                peaks = np.uint8(peaks)
                
                num_labels, markers = cv2.connectedComponents(peaks)
                if num_labels > 2:
                    crop_bgr = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
                    markers = markers + 1
                    markers[crop == 0] = 0
                    cv2.watershed(crop_bgr, markers)
                    
                    for label in range(2, num_labels + 1):
                        sub_mask = np.zeros_like(crop)
                        sub_mask[markers == label] = 255
                        sub_mask = cv2.morphologyEx(sub_mask, cv2.MORPH_OPEN, np.ones((2,2), np.uint8))
                        sub_contours, _ = cv2.findContours(sub_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        for sc in sub_contours:
                            s_area = int(cv2.contourArea(sc))
                            if s_area >= min_area:
                                sx, sy, sw, sh = cv2.boundingRect(sc)
                                _subdivide_region(x + sx, y + sy, sw, sh, mask, final_regions)
                    continue
                    
        # Apply standard subdivision
        _subdivide_region(x, y, w, h, mask, final_regions)
        
    return final_regions


def _compute_confidence(crop_a: np.ndarray, crop_b: np.ndarray, diff_mask: np.ndarray) -> float:
    # Estimate confidence score
    h, w = crop_a.shape[:2]
    diff_pix = cv2.countNonZero(diff_mask)
    if diff_pix == 0:
        return 0.0
        
    # Local template matching score as SSIM proxy
    res = cv2.matchTemplate(crop_a, crop_b, cv2.TM_CCOEFF_NORMED)
    cc = float(res[0][0]) if res is not None else 1.0
    ssim_term = max(0.0, 1.0 - max(0.0, cc))
    
    # Edge changes inside mask
    edges_a = cv2.Canny(crop_a, 50, 150)
    edges_b = cv2.Canny(crop_b, 50, 150)
    edge_diff = cv2.absdiff(edges_a, edges_b)
    edge_diff_in_mask = cv2.bitwise_and(edge_diff, diff_mask)
    edge_term = cv2.countNonZero(edge_diff_in_mask) / max(1, diff_pix)
    
    # Size impact
    size_term = min(1.0, diff_pix / 200.0)
    
    score = 0.40 * ssim_term + 0.40 * edge_term + 0.20 * size_term
    return round(float(np.clip(score, 0.1, 1.0)), 2)


def _generate_and_save_region_crops(
    image_a: np.ndarray,
    image_b: np.ndarray,
    diff_mask: np.ndarray,
    regions: list[Region],
    job_dir: Path
) -> None:
    # Save Ref Crop, Comp Crop with yellow box, mask crop, and Edge Overlay
    crops_dir = job_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)
    
    for r in regions:
        pad = 15
        h, w = image_a.shape[:2]
        x1 = max(0, r.x - pad)
        y1 = max(0, r.y - pad)
        x2 = min(w, r.x + r.width + pad)
        y2 = min(h, r.y + r.height + pad)
        
        crop_ref = image_a[y1:y2, x1:x2]
        crop_cmp = image_b[y1:y2, x1:x2]
        crop_mask = diff_mask[y1:y2, x1:x2]
        
        crop_box = crop_cmp.copy()
        cv2.rectangle(crop_box, (r.x - x1, r.y - y1), (r.x + r.width - x1, r.y + r.height - y1), (0, 255, 255), 2)
        
        gray_ref = cv2.cvtColor(crop_ref, cv2.COLOR_BGR2GRAY)
        gray_cmp = cv2.cvtColor(crop_cmp, cv2.COLOR_BGR2GRAY)
        edges_a = cv2.Canny(gray_ref, 50, 150)
        edges_b = cv2.Canny(gray_cmp, 50, 150)
        edge_diff = cv2.absdiff(edges_a, edges_b)
        
        gray_ref_bgr = cv2.cvtColor(gray_ref, cv2.COLOR_GRAY2BGR)
        edge_overlay = gray_ref_bgr.copy()
        edge_overlay[edge_diff > 0] = [0, 0, 255]
        
        cv2.imwrite(str(crops_dir / f"R_{r.id}_ref.png"), crop_ref)
        cv2.imwrite(str(crops_dir / f"R_{r.id}_cmp.png"), crop_box)
        cv2.imwrite(str(crops_dir / f"R_{r.id}_mask.png"), crop_mask)
        cv2.imwrite(str(crops_dir / f"R_{r.id}_edge.png"), edge_overlay)


def analyze_images(image_a: np.ndarray, image_b: np.ndarray, job_dir: Path = None) -> DifferenceResult:
    prepared_a, prepared_b = _resize_to_common_canvas(image_a, image_b)
    
    gray_a = cv2.cvtColor(prepared_a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(prepared_b, cv2.COLOR_BGR2GRAY)
    is_doc = _is_document_like(gray_a, gray_b)
    
    if is_doc:
        roi_mask, detected_regions, detected_boxes = detect_drawing_rois(prepared_a, job_dir=job_dir)
    else:
        roi_mask = np.ones_like(gray_a) * 255
        detected_regions = prepared_a.copy()

    aligned_b, alignment_status = _align_image(prepared_a, prepared_b, roi_mask)
    gray_b = cv2.cvtColor(aligned_b, cv2.COLOR_BGR2GRAY)
    
    if is_doc:
        # Engineering Drawing hierarchical difference pipeline
        ignore_outside = cv2.bitwise_not(roi_mask)
        ignore_mask = cv2.bitwise_or(ignore_outside, _non_image_artifact_mask(gray_a, gray_b))
        
        # Stage 1: Coarse localization
        candidate_boxes = _find_coarse_candidates(gray_a, gray_b)
        
        # Stage 2: Fine localization & local registration
        global_mask = np.zeros_like(gray_a)
        for bx, by, bw, bh in candidate_boxes:
            crop_a = prepared_a[by:by+bh, bx:bx+bw]
            crop_b = aligned_b[by:by+bh, bx:bx+bw]
            
            gray_crop_a = cv2.cvtColor(crop_a, cv2.COLOR_BGR2GRAY)
            gray_crop_b = cv2.cvtColor(crop_b, cv2.COLOR_BGR2GRAY)
            dx, dy = 0.0, 0.0
            if bw >= 32 and bh >= 32:
                f_a = np.float32(gray_crop_a)
                f_b = np.float32(gray_crop_b)
                shift, response = cv2.phaseCorrelate(f_a, f_b)
                if response >= 0.12 and (abs(shift[0]) <= 15 and abs(shift[1]) <= 15):
                    dx, dy = shift[0], shift[1]
            
            if abs(dx) >= 0.5 or abs(dy) >= 0.5:
                matrix = np.float32([[1, 0, dx], [0, 1, dy]])
                crop_b_aligned = cv2.warpAffine(crop_b, matrix, (bw, bh), borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))
            else:
                crop_b_aligned = crop_b.copy()
                
            # Foreground strokes + adaptive morphological closing + skeletonization (thinning)
            fg_a = _foreground_strokes(gray_crop_a)
            fg_b = _foreground_strokes(cv2.cvtColor(crop_b_aligned, cv2.COLOR_BGR2GRAY))
            
            # Local thinned stroke comparison
            tol = 3
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tol, tol))
            near_a = cv2.dilate(fg_a, kernel, iterations=1)
            near_b = cv2.dilate(fg_b, kernel, iterations=1)
            
            missing = cv2.bitwise_and(fg_a, cv2.bitwise_not(near_b))
            added = cv2.bitwise_and(fg_b, cv2.bitwise_not(near_a))
            local_diff = cv2.bitwise_or(missing, added)
            
            local_ignore = ignore_mask[by:by+bh, bx:bx+bw]
            local_diff[local_ignore > 0] = 0
            
            local_diff = cv2.dilate(local_diff, np.ones((3, 3), np.uint8))
            local_diff = cv2.morphologyEx(local_diff, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
            local_diff = cv2.morphologyEx(local_diff, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=1)
            local_diff[local_ignore > 0] = 0
            
            global_mask[by:by+bh, bx:bx+bw] = cv2.bitwise_or(global_mask[by:by+bh, bx:bx+bw], local_diff)
            
        # Global Morphology cleanup (close gaps and merge lines into solid blobs)
        global_mask = cv2.morphologyEx(global_mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8), iterations=1)
        global_mask[ignore_mask > 0] = 0
        
        # Stage 3: Split large regions and segment clustering
        segmented_boxes = _segment_difference_mask(global_mask)
        
        # Build Region dataclass list with centroids and confidence scores
        regions: list[Region] = []
        image_area = global_mask.shape[0] * global_mask.shape[1]
        for index, (rx, ry, rw, rh, ra) in enumerate(segmented_boxes, 1):
            cx = rx + rw / 2.0
            cy = ry + rh / 2.0
            
            crop_a = prepared_a[ry:ry+rh, rx:rx+rw]
            crop_b = aligned_b[ry:ry+rh, rx:rx+rw]
            crop_mask = global_mask[ry:ry+rh, rx:rx+rw]
            conf = _compute_confidence(crop_a, crop_b, crop_mask)
            
            location = _location_label(cx, cy, global_mask.shape[1], global_mask.shape[0])
            regions.append(
                Region(
                    id=index,
                    x=int(rx),
                    y=int(ry),
                    width=int(rw),
                    height=int(rh),
                    area_pixels=int(ra),
                    location=location,
                    severity=_severity_label(ra / image_area),
                    centroid_x=round(cx, 1),
                    centroid_y=round(cy, 1),
                    confidence_score=conf,
                    relative_position=location
                )
            )
            
        if job_dir is not None:
            _generate_and_save_region_crops(prepared_a, aligned_b, global_mask, regions, job_dir)
            
        diff = cv2.absdiff(gray_a, gray_b)
        mask = global_mask
        
    else:
        # Photo pipeline (Grayscale threshold flow)
        gray_a_norm = _normalize_gray(prepared_a)
        gray_b_norm = _normalize_gray(aligned_b)
        diff, mask = _difference_mask(gray_a_norm, gray_b_norm)
        regions_raw = _extract_regions(mask)
        regions = []
        for r in regions_raw:
            regions.append(
                Region(
                    id=r.id,
                    x=r.x,
                    y=r.y,
                    width=r.width,
                    height=r.height,
                    area_pixels=r.area_pixels,
                    location=r.location,
                    severity=r.severity,
                    centroid_x=round(r.x + r.width / 2.0, 1),
                    centroid_y=round(r.y + r.height / 2.0, 1),
                    confidence_score=1.0,
                    relative_position=r.location
                )
            )
            
    changed_area = int(cv2.countNonZero(mask))
    total_area = int(mask.shape[0] * mask.shape[1])
    changed_percentage = round((changed_area / total_area) * 100, 2) if total_area else 0.0

    heatmap = _make_heatmap(prepared_a, diff, mask)
    overlay = _make_overlay(aligned_b, mask, regions)
    side_by_side = np.hstack([prepared_a, aligned_b])
    confidence = _confidence_label(len(regions), changed_percentage, alignment_status)

    return DifferenceResult(
        image_a=prepared_a,
        image_b=prepared_b,
        aligned_b=aligned_b,
        mask=mask,
        heatmap=heatmap,
        overlay=overlay,
        side_by_side=side_by_side,
        regions=regions,
        changed_percentage=changed_percentage,
        changed_area_pixels=changed_area,
        total_area_pixels=total_area,
        alignment_status=alignment_status,
        confidence=confidence,
        roi_mask=roi_mask,
        detected_regions=detected_regions
    )


def _resize_to_common_canvas(image_a: np.ndarray, image_b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    max_width = 1800
    height = min(image_a.shape[0], image_b.shape[0])
    width = min(image_a.shape[1], image_b.shape[1])
    scale = min(1.0, max_width / max(width, 1))
    target_size = (max(1, int(width * scale)), max(1, int(height * scale)))
    return cv2.resize(image_a, target_size, interpolation=cv2.INTER_AREA), cv2.resize(
        image_b, target_size, interpolation=cv2.INTER_AREA
    )


def _align_image(reference: np.ndarray, comparison: np.ndarray, roi_mask: np.ndarray = None) -> tuple[np.ndarray, str]:
    gray_ref = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
    gray_cmp = cv2.cvtColor(comparison, cv2.COLOR_BGR2GRAY)
    
    # Check if document-like to use clean border fill and restrict to Affine transforms
    is_doc = _is_document_like(gray_ref, gray_cmp)
    border_mode = cv2.BORDER_CONSTANT if is_doc else cv2.BORDER_REPLICATE
    border_value = (255, 255, 255) if is_doc else (0, 0, 0)

    ref_points, cmp_points = _matched_feature_points(gray_ref, gray_cmp, roi_mask)

    if is_doc:
        # Document/Drawing: restrict to Affine transforms to prevent perspective distortion
        if len(ref_points) >= 10:
            matrix, inliers = cv2.estimateAffine2D(cmp_points, ref_points, method=cv2.RANSAC, ransacReprojThreshold=3)
            if matrix is not None and inliers is not None and int(inliers.sum()) >= 8:
                aligned = cv2.warpAffine(
                    comparison,
                    matrix,
                    (reference.shape[1], reference.shape[0]),
                    flags=cv2.INTER_LINEAR,
                    borderMode=border_mode,
                    borderValue=border_value,
                )
                return aligned, f"Affine feature alignment applied using {int(inliers.sum())} inlier points."
        
        if len(ref_points) >= 10:
            matrix, inliers = cv2.estimateAffinePartial2D(cmp_points, ref_points, method=cv2.RANSAC, ransacReprojThreshold=3)
            if matrix is not None and inliers is not None and int(inliers.sum()) >= 8:
                aligned = cv2.warpAffine(
                    comparison,
                    matrix,
                    (reference.shape[1], reference.shape[0]),
                    flags=cv2.INTER_LINEAR,
                    borderMode=border_mode,
                    borderValue=border_value,
                )
                return aligned, f"Affine feature alignment applied using {int(inliers.sum())} inlier points."
    else:
        # Photo/Scene: allow Homography (Perspective) warp
        if len(ref_points) >= 18:
            homography, inliers = cv2.findHomography(cmp_points, ref_points, cv2.RANSAC, 4.0)
            if homography is not None and inliers is not None and int(inliers.sum()) >= 12:
                aligned = cv2.warpPerspective(
                    comparison,
                    homography,
                    (reference.shape[1], reference.shape[0]),
                    flags=cv2.INTER_LINEAR,
                    borderMode=border_mode,
                    borderValue=border_value,
                )
                return aligned, f"Perspective feature alignment applied using {int(inliers.sum())} inlier points."

        if len(ref_points) >= 10:
            matrix, inliers = cv2.estimateAffinePartial2D(cmp_points, ref_points, method=cv2.RANSAC, ransacReprojThreshold=3)
            if matrix is not None and inliers is not None and int(inliers.sum()) >= 8:
                aligned = cv2.warpAffine(
                    comparison,
                    matrix,
                    (reference.shape[1], reference.shape[0]),
                    flags=cv2.INTER_LINEAR,
                    borderMode=border_mode,
                    borderValue=border_value,
                )
                return aligned, f"Affine feature alignment applied using {int(inliers.sum())} inlier points."

    shifted, response = cv2.phaseCorrelate(np.float32(gray_ref), np.float32(gray_cmp))
    shift_x, shift_y = shifted
    if response >= 0.18 and (abs(shift_x) >= 0.5 or abs(shift_y) >= 0.5):
        matrix = np.float32([[1, 0, shift_x], [0, 1, shift_y]])
        aligned = cv2.warpAffine(
            comparison,
            matrix,
            (reference.shape[1], reference.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=border_mode,
            borderValue=border_value,
        )
        return aligned, f"Translation alignment applied using phase correlation (response {response:.2f})."

    return comparison, "Alignment retained original positioning - insufficient reliable matching detail."


def _matched_feature_points(gray_ref: np.ndarray, gray_cmp: np.ndarray, roi_mask: np.ndarray = None) -> tuple[np.ndarray, np.ndarray]:
    detector = cv2.AKAZE_create()
    kp1, des1 = detector.detectAndCompute(gray_ref, roi_mask)
    kp2, des2 = detector.detectAndCompute(gray_cmp, roi_mask)
    if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
        detector = cv2.ORB_create(3000)
        kp1, des1 = detector.detectAndCompute(gray_ref, roi_mask)
        kp2, des2 = detector.detectAndCompute(gray_cmp, roi_mask)

    if des1 is None or des2 is None or len(kp1) < 10 or len(kp2) < 10:
        return np.empty((0, 1, 2), dtype=np.float32), np.empty((0, 1, 2), dtype=np.float32)

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    raw_matches = matcher.knnMatch(des1, des2, k=2)
    good_matches = []
    for pair in raw_matches:
        if len(pair) != 2:
            continue
        best, second = pair
        if best.distance < 0.78 * second.distance:
            good_matches.append(best)

    if len(good_matches) < 10:
        return np.empty((0, 1, 2), dtype=np.float32), np.empty((0, 1, 2), dtype=np.float32)

    good_matches = sorted(good_matches, key=lambda match: match.distance)[:160]
    ref_points = np.float32([kp1[match.queryIdx].pt for match in good_matches]).reshape(-1, 1, 2)
    cmp_points = np.float32([kp2[match.trainIdx].pt for match in good_matches]).reshape(-1, 1, 2)
    return ref_points, cmp_points


def _normalize_gray(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def _difference_mask(gray_a: np.ndarray, gray_b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    diff = cv2.absdiff(gray_a, gray_b)
    diff = cv2.GaussianBlur(diff, (5, 5), 0)

    if _is_document_like(gray_a, gray_b):
        mask = _document_stroke_difference_mask(gray_a, gray_b)
    else:
        mask = _photo_difference_mask(gray_a, gray_b, diff)

    ignore_mask = _non_image_artifact_mask(gray_a, gray_b)
    mask[ignore_mask > 0] = 0
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=1)
    mask[ignore_mask > 0] = 0
    return diff, mask


def _photo_difference_mask(gray_a: np.ndarray, gray_b: np.ndarray, diff: np.ndarray) -> np.ndarray:
    _, intensity_mask = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    strong_threshold = max(22, int(np.percentile(diff, 94)))
    _, strong_mask = cv2.threshold(diff, strong_threshold, 255, cv2.THRESH_BINARY)

    edges_a = cv2.Canny(gray_a, 60, 160)
    edges_b = cv2.Canny(gray_b, 60, 160)
    edge_diff = cv2.absdiff(edges_a, edges_b)
    edge_diff = cv2.dilate(edge_diff, np.ones((3, 3), np.uint8), iterations=1)

    mask = cv2.bitwise_or(strong_mask, cv2.bitwise_and(intensity_mask, edge_diff))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8), iterations=2)
    mask = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=1)
    return mask


def _is_document_like(gray_a: np.ndarray, gray_b: np.ndarray) -> bool:
    bright_ratio = (np.mean(gray_a > 215) + np.mean(gray_b > 215)) / 2
    edge_ratio = (
        np.mean(cv2.Canny(gray_a, 60, 160) > 0) + np.mean(cv2.Canny(gray_b, 60, 160) > 0)
    ) / 2
    return bool(bright_ratio >= 0.45 and edge_ratio <= 0.18)


def _document_stroke_difference_mask(gray_a: np.ndarray, gray_b: np.ndarray) -> np.ndarray:
    fg_a = _foreground_strokes(gray_a)
    fg_b = _foreground_strokes(gray_b)
    tolerance = max(3, min(9, int(round(min(gray_a.shape) / 260))))
    if tolerance % 2 == 0:
        tolerance += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tolerance, tolerance))

    near_a = cv2.dilate(fg_a, kernel, iterations=1)
    near_b = cv2.dilate(fg_b, kernel, iterations=1)
    missing_from_b = cv2.bitwise_and(fg_a, cv2.bitwise_not(near_b))
    added_to_b = cv2.bitwise_and(fg_b, cv2.bitwise_not(near_a))
    mask = cv2.bitwise_or(missing_from_b, added_to_b)

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    return mask


def _foreground_strokes(gray: np.ndarray) -> np.ndarray:
    # Preprocessing: Noise removal, adaptive thresholding, small gap closing, and thinning (skeletonization)
    blurred = cv2.medianBlur(gray, 3)
    adaptive = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        29,
        9,
    )
    _, dark = cv2.threshold(blurred, 185, 255, cv2.THRESH_BINARY_INV)
    strokes = cv2.bitwise_or(adaptive, dark)
    # Close small gaps (gap closing)
    strokes = cv2.morphologyEx(strokes, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    # Morphological thinning
    return _skeletonize(strokes)


def _non_image_artifact_mask(gray_a: np.ndarray, gray_b: np.ndarray) -> np.ndarray:
    foreground = cv2.bitwise_or(_foreground_strokes(gray_a), _foreground_strokes(gray_b))
    h, w = foreground.shape
    ignore = np.zeros_like(foreground)

    margin = max(10, int(min(h, w) * 0.025))
    ignore[:margin, :] = 255
    ignore[h - margin :, :] = 255
    ignore[:, :margin] = 255
    ignore[:, w - margin :] = 255

    border_like = _long_rule_and_edge_mask(foreground)
    text_like = _text_like_mask(foreground)
    ignore = cv2.bitwise_or(ignore, border_like)
    ignore = cv2.bitwise_or(ignore, text_like)
    return cv2.dilate(ignore, np.ones((5, 5), np.uint8), iterations=1)


def _long_rule_and_edge_mask(foreground: np.ndarray) -> np.ndarray:
    h, w = foreground.shape
    mask = np.zeros_like(foreground)
    contours, _ = cv2.findContours(foreground, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    edge_band = max(8, int(min(h, w) * 0.018))
    line_thickness = max(6, int(round(min(h, w) * 0.01)))

    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        touches_edge = x <= edge_band or y <= edge_band or x + width >= w - edge_band or y + height >= h - edge_band
        long_horizontal = width >= 0.32 * w and height <= 0.035 * h
        long_vertical = height >= 0.32 * h and width <= 0.035 * w
        title_block_rule = y >= 0.84 * h and (long_horizontal or width >= 0.12 * w)
        if touches_edge or long_horizontal or long_vertical or title_block_rule:
            cv2.drawContours(mask, [contour], -1, 255, thickness=line_thickness)

    return cv2.dilate(mask, np.ones((7, 7), np.uint8), iterations=1)


def _text_like_mask(foreground: np.ndarray) -> np.ndarray:
    h, w = foreground.shape
    char_candidates = np.zeros_like(foreground)
    contours, _ = cv2.findContours(foreground, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if x <= 3 or y <= 3 or x + width >= w - 3 or y + height >= h - 3:
            continue
        if 4 <= height <= max(12, int(h * 0.035)) and 2 <= width <= max(20, int(w * 0.045)) and area <= 700:
            aspect = width / max(height, 1)
            if 0.08 <= aspect <= 12:
                cv2.drawContours(char_candidates, [contour], -1, 255, thickness=cv2.FILLED)

    group_kernel_width = max(9, int(w * 0.012))
    grouped = cv2.dilate(char_candidates, cv2.getStructuringElement(cv2.MORPH_RECT, (group_kernel_width, 3)), iterations=1)
    text_mask = np.zeros_like(foreground)
    grouped_contours, _ = cv2.findContours(grouped, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in grouped_contours:
        x, y, width, height = cv2.boundingRect(contour)
        aspect = width / max(height, 1)
        if 6 <= height <= max(16, int(h * 0.055)) and 10 <= width <= max(80, int(w * 0.22)) and aspect >= 1.25:
            text_mask[y : y + height, x : x + width] = 255

    return cv2.dilate(text_mask, np.ones((5, 3), np.uint8), iterations=1)


def _extract_regions(mask: np.ndarray) -> list[Region]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = mask.shape[0] * mask.shape[1]
    min_area = max(120, int(image_area * 0.00018))
    regions: list[Region] = []
    for contour in contours:
        area = int(cv2.contourArea(contour))
        if area < min_area:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        box_area = int(width * height)
        fill_ratio = area / max(box_area, 1)
        if box_area < min_area or fill_ratio < 0.08:
            continue
        regions.append(
            Region(
                id=0,
                x=int(x),
                y=int(y),
                width=int(width),
                height=int(height),
                area_pixels=box_area,
                location=_location_label(x + width / 2, y + height / 2, mask.shape[1], mask.shape[0]),
                severity=_severity_label(box_area / image_area),
            )
        )

    regions.sort(key=lambda region: region.area_pixels, reverse=True)
    return [Region(**{**region.__dict__, "id": index}) for index, region in enumerate(regions, 1)]


def _location_label(cx: float, cy: float, width: int, height: int) -> str:
    horizontal = "left" if cx < width / 3 else "right" if cx > (2 * width) / 3 else "center"
    vertical = "upper" if cy < height / 3 else "lower" if cy > (2 * height) / 3 else "middle"
    if horizontal == "center" and vertical == "middle":
        return "center"
    if horizontal == "center":
        return vertical
    if vertical == "middle":
        return horizontal
    return f"{vertical}-{horizontal}"


def _severity_label(area_ratio: float) -> str:
    if area_ratio >= 0.05:
        return "major"
    if area_ratio >= 0.01:
        return "moderate"
    return "minor"


def _make_heatmap(reference: np.ndarray, diff: np.ndarray, mask: np.ndarray) -> np.ndarray:
    normalized = cv2.normalize(diff, None, 0, 255, cv2.NORM_MINMAX)
    color_map = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
    color_map[mask == 0] = reference[mask == 0]
    return cv2.addWeighted(reference, 0.55, color_map, 0.45, 0)


def _make_overlay(image: np.ndarray, mask: np.ndarray, regions: list[Region]) -> np.ndarray:
    overlay = image.copy()
    red_layer = np.zeros_like(image)
    red_layer[:, :, 2] = 255
    overlay[mask > 0] = cv2.addWeighted(image, 0.45, red_layer, 0.55, 0)[mask > 0]
    for region in regions:
        cv2.rectangle(overlay, (region.x, region.y), (region.x + region.width, region.y + region.height), (0, 255, 255), 3)
        cv2.putText(
            overlay,
            f"R{region.id}",
            (region.x, max(24, region.y - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.75,
            (0, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return overlay


def _confidence_label(region_count: int, changed_percentage: float, alignment_status: str) -> str:
    if region_count == 0:
        return "High - no significant regions detected after noise filtering."
    if "applied" in alignment_status.lower() and changed_percentage <= 15:
        return "High"
    if changed_percentage <= 25:
        return "Moderate"
    return "Review recommended - extensive change or possible viewpoint mismatch."
