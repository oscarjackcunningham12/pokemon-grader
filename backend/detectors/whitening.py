from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional

import cv2
import numpy as np

from utils.regions import RegionBox, crop_region


@dataclass
class WhiteningSpot:
    x: int
    y: int
    width: int
    height: int
    area: int
    severity: str
    region: str


@dataclass
class WhiteningAnalysisResult:
    score: float
    spot_count: int
    total_spot_area: int
    severity: str
    spots: List[WhiteningSpot]
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
    if area < 40:
        return "moderate"
    return "heavy"


def score_whitening(spot_count: int, total_area: int, image_area: int) -> float:
    if image_area <= 0:
        return 0.0

    area_ratio = total_area / image_area

    penalty = 0
    penalty += spot_count * 0.10
    penalty += area_ratio * 80

    score = 10 - penalty
    return round(max(1.0, min(10.0, score)), 1)


def detect_whitening_mask(
    image_bgr: np.ndarray,
    brightness_threshold: int = 210,
    saturation_threshold: int = 75,
) -> np.ndarray:
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)

    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    bright_mask = value > brightness_threshold
    low_sat_mask = saturation < saturation_threshold

    mask = np.logical_and(bright_mask, low_sat_mask).astype(np.uint8) * 255

    kernel = np.ones((2, 2), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_DILATE, kernel, iterations=1)

    return mask


def extract_whitening_spots(
    mask: np.ndarray,
    min_area: int = 5,
) -> List[Tuple[int, int, int, int, int]]:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    spots = []

    for contour in contours:
        area = int(cv2.contourArea(contour))
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)
        spots.append((x, y, w, h, area))

    return spots


def get_whitening_regions(
    card: np.ndarray,
    regions: Optional[Dict[str, RegionBox]] = None
) -> Dict[str, Tuple[np.ndarray, Tuple[int, int]]]:
    """
    Whitening should mostly analyze edges and corners.
    This prevents bright artwork/text areas from being mistaken for whitening.
    """
    if regions:
        keys = [
            "left_edge",
            "right_edge",
            "top_edge",
            "bottom_edge",
            "top_left_corner",
            "top_right_corner",
            "bottom_left_corner",
            "bottom_right_corner",
        ]

        selected = {}

        for key in keys:
            if key in regions:
                region = regions[key]
                selected[key] = (crop_region(card, region), (region.x, region.y))

        if selected:
            return selected

    h, w = card.shape[:2]
    edge_w = max(8, int(w * 0.04))
    edge_h = max(8, int(h * 0.04))
    corner_w = max(20, int(w * 0.12))
    corner_h = max(20, int(h * 0.12))

    return {
        "left_edge": (card[:, :edge_w], (0, 0)),
        "right_edge": (card[:, w - edge_w:w], (w - edge_w, 0)),
        "top_edge": (card[:edge_h, :], (0, 0)),
        "bottom_edge": (card[h - edge_h:h, :], (0, h - edge_h)),
        "top_left_corner": (card[:corner_h, :corner_w], (0, 0)),
        "top_right_corner": (card[:corner_h, w - corner_w:w], (w - corner_w, 0)),
        "bottom_left_corner": (card[h - corner_h:h, :corner_w], (0, h - corner_h)),
        "bottom_right_corner": (card[h - corner_h:h, w - corner_w:w], (w - corner_w, h - corner_h)),
    }


def analyze_whitening(
    card: np.ndarray,
    regions: Optional[Dict[str, RegionBox]] = None
) -> WhiteningAnalysisResult:
    """
    Whitening detection focused on selected edge/corner regions.
    """
    overlay = card.copy()

    whitening_regions = get_whitening_regions(card, regions)

    whitening_spots: List[WhiteningSpot] = []
    total_area = 0
    total_region_area = 0

    for region_name, (crop, offset) in whitening_regions.items():
        offset_x, offset_y = offset

        mask = detect_whitening_mask(crop)
        raw_spots = extract_whitening_spots(mask)

        total_region_area += crop.shape[0] * crop.shape[1]

        for x, y, w, h, area in raw_spots:
            global_x = x + offset_x
            global_y = y + offset_y

            total_area += area
            severity = classify_spot(area)

            whitening_spots.append(
                WhiteningSpot(
                    x=int(global_x),
                    y=int(global_y),
                    width=int(w),
                    height=int(h),
                    area=int(area),
                    severity=severity,
                    region=region_name,
                )
            )

            cv2.rectangle(
                overlay,
                (global_x, global_y),
                (global_x + w, global_y + h),
                (255, 255, 0),
                1,
            )

    score = score_whitening(
        spot_count=len(whitening_spots),
        total_area=total_area,
        image_area=max(1, total_region_area),
    )

    return WhiteningAnalysisResult(
        score=score,
        spot_count=len(whitening_spots),
        total_spot_area=int(total_area),
        severity=classify_severity(score),
        spots=whitening_spots,
        overlay_image=overlay,
    )


def whitening_result_to_dict(result: WhiteningAnalysisResult) -> dict:
    return {
        "score": result.score,
        "spot_count": result.spot_count,
        "total_spot_area": result.total_spot_area,
        "severity": result.severity,
        "spots": [asdict(spot) for spot in result.spots],
    }