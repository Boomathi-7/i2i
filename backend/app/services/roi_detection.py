import cv2
import numpy as np
from pathlib import Path

def detect_drawing_rois(image: np.ndarray, job_dir: Path = None) -> tuple[np.ndarray, np.ndarray, list[tuple[int, int, int, int]]]:
    """
    Detects one or multiple engineering drawings on the sheet.
    Ignores title blocks, revision tables, logos, borders, margins, and notes.
    Saves debugging outputs in job_dir if provided.
    Returns:
        roi_mask: A binary mask (0 and 255) where drawing regions are white.
        overlay_image: The original image with green bounding boxes around detected regions.
        boxes: List of bounding boxes (x, y, w, h) of detected drawing regions.
    """
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # 1. Base foreground linework
    blurred = cv2.medianBlur(gray, 3)
    fg = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        29,
        9
    )
    
    # 2. Suppress sheet borders and title block outer grids (long horizontal/vertical lines)
    hl = cv2.morphologyEx(fg, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (80, 1)))
    vl = cv2.morphologyEx(fg, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 80)))
    fg_no_borders = cv2.bitwise_and(fg, cv2.bitwise_not(cv2.bitwise_or(hl, vl)))
    
    # 3. Suppress small connected components (text notes, labels, sheet numbers, logos)
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(fg_no_borders, connectivity=8)
    clean_fg = fg_no_borders.copy()
    for i in range(1, num_labels):
        bx = stats[i, cv2.CC_STAT_LEFT]
        by = stats[i, cv2.CC_STAT_TOP]
        bw = stats[i, cv2.CC_STAT_WIDTH]
        bh = stats[i, cv2.CC_STAT_HEIGHT]
        # Text/labels/small notes are typically small in both dimensions
        if bw < 50 and bh < 50:
            clean_fg[labels == i] = 0
            
    # 4. Dilate remaining graphics horizontally to merge views
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (81, 15))
    merged = cv2.dilate(clean_fg, kernel, iterations=1)
    merged = cv2.erode(merged, kernel, iterations=1)
    
    # 5. Extract contours and filter them
    all_contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    detected_boxes = []
    selected_contours = []
    
    for c in all_contours:
        bx, by, bw, bh = cv2.boundingRect(c)
        # Filter out noise blocks
        if bw < 100 or bh < 100:
            continue
        detected_boxes.append((bx, by, bw, bh))
        selected_contours.append(c)
        
    # 6. Generate ROI Mask
    roi_mask = np.zeros_like(gray)
    pad = 20
    for bx, by, bw, bh in detected_boxes:
        rx1 = max(0, bx - pad)
        ry1 = max(0, by - pad)
        rx2 = min(w, bx + bw + pad)
        ry2 = min(h, by + bh + pad)
        cv2.rectangle(roi_mask, (rx1, ry1), (rx2, ry2), 255, thickness=cv2.FILLED)
        
    # 7. Create green boundary box overlay
    overlay = image.copy()
    for bx, by, bw, bh in detected_boxes:
        cv2.rectangle(overlay, (bx, by), (bx + bw, by + bh), (0, 200, 0), 4)
        
    # 8. Save Debugging Outputs
    if job_dir is not None:
        job_dir = Path(job_dir)
        job_dir.mkdir(parents=True, exist_ok=True)
        
        cv2.imwrite(str(job_dir / "debug_roi_1_original.png"), image)
        cv2.imwrite(str(job_dir / "debug_roi_2_foreground.png"), clean_fg)
        
        detected_contours_img = image.copy()
        cv2.drawContours(detected_contours_img, all_contours, -1, (255, 0, 0), 2)
        cv2.imwrite(str(job_dir / "debug_roi_3_detected_contours.png"), detected_contours_img)
        
        selected_contours_img = image.copy()
        cv2.drawContours(selected_contours_img, selected_contours, -1, (0, 255, 0), 2)
        cv2.imwrite(str(job_dir / "debug_roi_4_selected_contours.png"), selected_contours_img)
        
        cv2.imwrite(str(job_dir / "debug_roi_5_mask.png"), roi_mask)
        
        final_comp = cv2.bitwise_and(image, image, mask=roi_mask)
        final_comp[roi_mask == 0] = [255, 255, 255]
        cv2.imwrite(str(job_dir / "debug_roi_6_final_comparison.png"), final_comp)
        
    return roi_mask, overlay, detected_boxes
