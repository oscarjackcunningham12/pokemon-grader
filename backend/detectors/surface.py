from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.utils.regions import RegionBox, crop_region


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
    analyzed_area: int
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
    penalty += issue_count * 0.13
    penalty += area_ratio * 55

    score = 10 - penalty
    return round(max(1.0, min(10.0, score)), 1)


def get_surface_crop(
    card: np.ndarray,
    regions: Optional[Dict[str, RegionBox]] = None
) -> Tuple[np.ndarray, Tuple[int, int]]:
    if regions and "surface" in regions:
        region = regions["surface"]
        return crop_region(card, region), (region.x, region.y)

    h, w = card.shape[:2]
    margin_x = int(w * 0.14)
    margin_y = int(h * 0.14)

    return (
        card[margin_y:h - margin_y, margin_x:w - margin_x],
        (margin_x, margin_y),
    )


def build_print_edge_mask(gray: np.ndarray) -> np.ndarray:
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    strong_edges = cv2.Canny(blurred, 90, 220)

    kernel = np.ones((3, 3), np.uint8)
    strong_edges = cv2.dilate(strong_edges, kernel, iterations=2)
    strong_edges = cv2.morphologyEx(strong_edges, cv2.MORPH_CLOSE, kernel, iterations=1)

    return strong_edges


def build_print_detail_mask(image_bgr: np.ndarray) -> np.ndarray:
    """
    Suppresses printed ink and text strokes before surface damage detection.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    saturated_ink = np.logical_and(saturation > 55, value < 245)
    dark_ink = value < 95

    ink_mask = np.logical_or(saturated_ink, dark_ink).astype(np.uint8) * 255

    kernel = np.ones((3, 3), np.uint8)
    ink_mask = cv2.dilate(ink_mask, kernel, iterations=2)

    print_edge_mask = build_print_edge_mask(gray)

    return cv2.bitwise_or(ink_mask, print_edge_mask)


def build_surface_anomaly_mask(image_bgr: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    smooth = cv2.GaussianBlur(gray, (15, 15), 0)
    diff = cv2.absdiff(gray, smooth)

    _, anomaly_mask = cv2.threshold(diff, 26, 255, cv2.THRESH_BINARY)

    print_detail_mask = build_print_detail_mask(image_bgr)

    anomaly_mask[print_detail_mask > 0] = 0

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

        if area < 14:
            continue

        if area > crop_area * 0.08:
            continue

        x, y, w, h = cv2.boundingRect(contour)

        aspect_ratio = max(w, h) / max(1, min(w, h))

        if aspect_ratio > 14 and area < 80:
            continue

        spots.append((x, y, w, h, area))

    return spots, mask


def severity_color(severity: str) -> Tuple[int, int, int]:
    """
    OpenCV uses BGR color order.
    """
    if severity == "minor":
        return (0, 255, 255)      # yellow
    if severity == "moderate":
        return (0, 165, 255)      # orange
    if severity == "heavy":
        return (0, 0, 255)        # red

    return (0, 255, 255)


def draw_surface_finding(
    overlay: np.ndarray,
    x: int,
    y: int,
    w: int,
    h: int,
    severity: str
) -> None:
    color = severity_color(severity)

    temp = overlay.copy()

    cv2.rectangle(
        temp,
        (x, y),
        (x + w, y + h),
        color,
        -1,
    )

    cv2.addWeighted(temp, 0.24, overlay, 0.76, 0, overlay)

    cv2.rectangle(
        overlay,
        (x, y),
        (x + w, y + h),
        color,
        2,
    )

    cv2.circle(
        overlay,
        (x + max(2, w // 2), y + max(2, h // 2)),
        max(4, min(10, max(w, h) // 3)),
        color,
        2,
    )


def analyze_surface(
    card: np.ndarray,
    regions: Optional[Dict[str, RegionBox]] = None
) -> SurfaceAnalysisResult:
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

        draw_surface_finding(
            overlay,
            int(global_x),
            int(global_y),
            int(w),
            int(h),
            severity,
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
        analyzed_area=int(crop_area),
        severity=classify_severity(score),
        spots=spots,
        overlay_image=overlay,
    )


def surface_result_to_dict(result: SurfaceAnalysisResult) -> dict:
    return {
        "score": result.score,
        "issue_count": result.issue_count,
        "total_issue_area": result.total_issue_area,
        "analyzed_area": result.analyzed_area,
        "severity": result.severity,
        "spots": [asdict(spot) for spot in result.spots],
    }
