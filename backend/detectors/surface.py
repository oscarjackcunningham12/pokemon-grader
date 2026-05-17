from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from utils.regions import RegionBox, crop_region


@dataclass
class SurfaceSpot:
    x: int
    y: int
    width: int
    height: int
    area: int
    severity: str
    issue_type: str


@dataclass
class SurfaceAnalysisResult:
    score: float
    issue_count: int
    total_issue_area: int
    severity: str
    spots: List[SurfaceSpot]
    overlay_image: np.ndarray


def classify_severity(score: float) -> str:
    if score >= 9.0:
        return "clean"
    if score >= 8.0:
        return "minor"
    if score >= 6.5:
        return "moderate"
    return "heavy"


def classify_spot(area: int) -> str:
    if area < 25:
        return "minor"
    if area < 110:
        return "moderate"
    return "heavy"


def score_surface(issue_count: int, total_area: int, image_area: int) -> float:
    if image_area <= 0:
        return 0.0

    area_ratio = total_area / image_area

    penalty = 0
    penalty += issue_count * 0.08
    penalty += area_ratio * 35

    score = 10 - penalty
    return round(max(1.0, min(10.0, score)), 1)


def get_surface_crop(
    card: np.ndarray,
    regions: Optional[Dict[str, RegionBox]] = None
) -> Tuple[np.ndarray, Tuple[int, int]]:
    """
    Surface analysis should only inspect the inner selected card area.
    """
    if regions and "surface" in regions:
        region = regions["surface"]
        return crop_region(card, region), (region.x, region.y)

    h, w = card.shape[:2]
    margin_x = int(w * 0.14)
    margin_y = int(h * 0.14)

    return (
        card[margin_y:h - margin_y, margin_x:w - margin_x],
        (margin_x, margin_y)
    )


def build_print_edge_mask(gray: np.ndarray) -> np.ndarray:
    """
    Detects strong printed design edges/text/logo-like edges so surface detection
    can ignore them instead of counting them as damage.
    """
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    strong_edges = cv2.Canny(blurred, 90, 220)

    kernel = np.ones((3, 3), np.uint8)

    strong_edges = cv2.dilate(strong_edges, kernel, iterations=2)
    strong_edges = cv2.morphologyEx(strong_edges, cv2.MORPH_CLOSE, kernel, iterations=1)

    return strong_edges


def build_surface_anomaly_mask(image_bgr: np.ndarray) -> np.ndarray:
    """
    Finds softer surface anomalies while suppressing normal printed design edges.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    # Smooth printed texture, then compare against original.
    smooth = cv2.GaussianBlur(gray, (15, 15), 0)
    diff = cv2.absdiff(gray, smooth)

    # Only keep noticeable local irregularities.
    _, anomaly_mask = cv2.threshold(diff, 22, 255, cv2.THRESH_BINARY)

    print_edge_mask = build_print_edge_mask(gray)

    # Remove logo/text/artwork hard edges from surface candidate mask.
    anomaly_mask[print_edge_mask > 0] = 0

    kernel = np.ones((2, 2), np.uint8)

    anomaly_mask = cv2.morphologyEx(anomaly_mask, cv2.MORPH_OPEN, kernel, iterations=1)
    anomaly_mask = cv2.morphologyEx(anomaly_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    return anomaly_mask


def detect_surface_damage(
    image_bgr: np.ndarray
) -> Tuple[List[Tuple[int, int, int, int, int]], np.ndarray]:
    mask = build_surface_anomaly_mask(image_bgr)

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    spots = []

    crop_area = image_bgr.shape[0] * image_bgr.shape[1]

    for contour in contours:
        area = int(cv2.contourArea(contour))

        if area < 10:
            continue

        if area > crop_area * 0.08:
            # Huge regions are usually lighting/glare/background artifacts.
            continue

        x, y, w, h = cv2.boundingRect(contour)

        aspect_ratio = max(w, h) / max(1, min(w, h))

        # Ignore tiny long text/logo strokes.
        if aspect_ratio > 14 and area < 80:
            continue

        spots.append((x, y, w, h, area))

    return spots, mask


def analyze_surface(
    card: np.ndarray,
    regions: Optional[Dict[str, RegionBox]] = None
) -> SurfaceAnalysisResult:
    """
    Surface analysis focused on abnormal marks, not printed artwork/logo edges.
    """
    overlay = card.copy()

    surface_crop, offset = get_surface_crop(card, regions)
    offset_x, offset_y = offset

    raw_spots, _ = detect_surface_damage(surface_crop)

    spots: List[SurfaceSpot] = []
    total_area = 0

    for x, y, w, h, area in raw_spots:
        global_x = x + offset_x
        global_y = y + offset_y

        total_area += area
        severity = classify_spot(area)

        spots.append(
            SurfaceSpot(
                x=int(global_x),
                y=int(global_y),
                width=int(w),
                height=int(h),
                area=int(area),
                severity=severity,
                issue_type="surface_anomaly",
            )
        )

        color = (0, 255, 255)
        if severity == "moderate":
            color = (0, 165, 255)
        elif severity == "heavy":
            color = (0, 0, 255)

        cv2.rectangle(
            overlay,
            (global_x, global_y),
            (global_x + w, global_y + h),
            color,
            1,
        )

    crop_area = surface_crop.shape[0] * surface_crop.shape[1]

    score = score_surface(
        issue_count=len(spots),
        total_area=total_area,
        image_area=max(1, crop_area),
    )

    return SurfaceAnalysisResult(
        score=score,
        issue_count=len(spots),
        total_issue_area=int(total_area),
        severity=classify_severity(score),
        spots=spots,
        overlay_image=overlay,
    )


def surface_result_to_dict(result: SurfaceAnalysisResult) -> dict:
    return {
        "score": result.score,
        "issue_count": result.issue_count,
        "total_issue_area": result.total_issue_area,
        "severity": result.severity,
        "spots": [asdict(spot) for spot in result.spots],
    }