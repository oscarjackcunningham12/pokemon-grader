from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional

import cv2
import numpy as np

from utils.regions import RegionBox, crop_region


@dataclass
class CornerSpot:
    corner: str
    x: int
    y: int
    width: int
    height: int
    area: int
    severity: str


@dataclass
class CornerResult:
    corner: str
    score: float
    spot_count: int
    total_spot_area: int
    analyzed_area: int
    severity: str


@dataclass
class CornerAnalysisResult:
    overall_score: float
    corners: Dict[str, CornerResult]
    spots: List[CornerSpot]
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
    if area < 10:
        return "minor"
    if area < 35:
        return "moderate"
    return "heavy"


def score_corner(spot_count: int, total_area: int, corner_area: int) -> float:
    if corner_area <= 0:
        return 0.0

    area_ratio = total_area / corner_area

    penalty = 0
    penalty += spot_count * 0.35
    penalty += area_ratio * 65

    score = 10 - penalty
    return round(max(1.0, min(10.0, score)), 1)


def crop_corner(
    card: np.ndarray,
    corner: str,
    corner_ratio: float = 0.12
) -> Tuple[np.ndarray, Tuple[int, int]]:
    h, w = card.shape[:2]

    crop_w = max(20, int(w * corner_ratio))
    crop_h = max(20, int(h * corner_ratio))

    if corner == "top_left":
        return card[:crop_h, :crop_w], (0, 0)

    if corner == "top_right":
        return card[:crop_h, w - crop_w:w], (w - crop_w, 0)

    if corner == "bottom_left":
        return card[h - crop_h:h, :crop_w], (0, h - crop_h)

    if corner == "bottom_right":
        return card[h - crop_h:h, w - crop_w:w], (w - crop_w, h - crop_h)

    raise ValueError(f"Unknown corner: {corner}")


def get_corner_crop(
    card: np.ndarray,
    corner: str,
    regions: Optional[Dict[str, RegionBox]] = None
) -> Tuple[np.ndarray, Tuple[int, int]]:
    """
    If manual centering regions exist, use the selected corner regions.
    Otherwise fall back to automatic corner crops.
    """
    if regions:
        region_key = f"{corner}_corner"
        if region_key in regions:
            region = regions[region_key]
            return crop_region(card, region), (region.x, region.y)

    return crop_corner(card, corner)


def detect_corner_whitening(
    corner_img: np.ndarray,
    min_area: int = 4,
    brightness_threshold: int = 205,
    saturation_threshold: int = 80,
) -> Tuple[List[Tuple[int, int, int, int, int]], np.ndarray]:
    hsv = cv2.cvtColor(corner_img, cv2.COLOR_BGR2HSV)

    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    bright_mask = value > brightness_threshold
    low_sat_mask = saturation < saturation_threshold

    mask = np.logical_and(bright_mask, low_sat_mask).astype(np.uint8) * 255

    kernel = np.ones((2, 2), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    spots = []
    for contour in contours:
        area = int(cv2.contourArea(contour))
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        spots.append((x, y, w, h, area))

    return spots, mask


def analyze_corners(
    card: np.ndarray,
    regions: Optional[Dict[str, RegionBox]] = None
) -> CornerAnalysisResult:
    """
    Analyze corner whitening/chipping.

    If regions are provided from manual centering, this uses:
    - top_left_corner
    - top_right_corner
    - bottom_left_corner
    - bottom_right_corner
    """
    overlay = card.copy()

    corner_results = {}
    all_spots: List[CornerSpot] = []

    for corner in ["top_left", "top_right", "bottom_left", "bottom_right"]:
        crop, offset = get_corner_crop(card, corner, regions)
        offset_x, offset_y = offset

        raw_spots, _ = detect_corner_whitening(crop)

        total_area = 0

        for x, y, w, h, area in raw_spots:
            global_x = x + offset_x
            global_y = y + offset_y

            total_area += area
            severity = classify_spot(area)

            all_spots.append(
                CornerSpot(
                    corner=corner,
                    x=int(global_x),
                    y=int(global_y),
                    width=int(w),
                    height=int(h),
                    area=int(area),
                    severity=severity,
                )
            )

            cv2.rectangle(
                overlay,
                (global_x, global_y),
                (global_x + w, global_y + h),
                (255, 0, 255),
                1,
            )

        corner_area = crop.shape[0] * crop.shape[1]
        score = score_corner(len(raw_spots), total_area, corner_area)

        corner_results[corner] = CornerResult(
            corner=corner,
            score=score,
            spot_count=len(raw_spots),
            total_spot_area=int(total_area),
            analyzed_area=int(corner_area),
            severity=classify_severity(score),
        )

    overall_score = round(
        sum(result.score for result in corner_results.values()) / len(corner_results),
        1,
    )

    return CornerAnalysisResult(
        overall_score=overall_score,
        corners=corner_results,
        spots=all_spots,
        overlay_image=overlay,
    )


def corner_result_to_dict(result: CornerAnalysisResult) -> dict:
    return {
        "overall_score": result.overall_score,
        "corners": {
            corner: asdict(corner_result)
            for corner, corner_result in result.corners.items()
        },
        "spots": [asdict(spot) for spot in result.spots],
    }
