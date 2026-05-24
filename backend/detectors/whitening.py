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
    analyzed_area: int
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
    if area < 12:
        return "minor"
    if area < 45:
        return "moderate"
    return "heavy"


def score_whitening(spot_count: int, total_area: int, image_area: int) -> float:
    if image_area <= 0:
        return 0.0

    area_ratio = total_area / image_area

    penalty = 0
    penalty += spot_count * 0.08
    penalty += area_ratio * 65

    score = 10 - penalty
    return round(max(1.0, min(10.0, score)), 1)


def build_print_edge_mask(image_bgr: np.ndarray) -> np.ndarray:
    """
    Masks strong printed edges so logo/text/artwork highlights are less likely
    to be counted as whitening.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(blur, 90, 220)

    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    return edges


def normalize_lighting(image_bgr: np.ndarray) -> np.ndarray:
    """
    Reduces broad lighting casts before thresholding tiny bright whitening marks.
    """
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=1.8, tileGridSize=(8, 8))
    lightness = clahe.apply(lightness)

    normalized = cv2.merge((lightness, a_channel, b_channel))
    return cv2.cvtColor(normalized, cv2.COLOR_LAB2BGR)


def adaptive_whitening_thresholds(
    image_bgr: np.ndarray,
    brightness_floor: int,
    saturation_ceiling: int,
) -> Tuple[int, int]:
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    bright_threshold = int(np.percentile(value, 88))
    low_sat_threshold = int(np.percentile(saturation, 35))

    return (
        max(brightness_floor, min(245, bright_threshold)),
        min(saturation_ceiling, max(28, low_sat_threshold)),
    )


def detect_whitening_mask(
    image_bgr: np.ndarray,
    brightness_threshold: int = 218,
    saturation_threshold: int = 60,
) -> np.ndarray:
    """
    Finds low-saturation bright marks, but suppresses printed design edges.
    """
    normalized_bgr = normalize_lighting(image_bgr)
    adaptive_brightness, adaptive_saturation = adaptive_whitening_thresholds(
        normalized_bgr,
        brightness_threshold,
        saturation_threshold,
    )

    hsv = cv2.cvtColor(normalized_bgr, cv2.COLOR_BGR2HSV)

    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    bright_mask = value > adaptive_brightness
    low_sat_mask = saturation < adaptive_saturation

    mask = np.logical_and(bright_mask, low_sat_mask).astype(np.uint8) * 255

    print_edge_mask = build_print_edge_mask(normalized_bgr)

    # Ignore hard printed edges/logos/text.
    mask[print_edge_mask > 0] = 0

    kernel = np.ones((2, 2), np.uint8)

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    return mask


def extract_whitening_spots(
    mask: np.ndarray,
    min_area: int = 6,
) -> List[Tuple[int, int, int, int, int]]:
    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE,
    )

    spots = []

    for contour in contours:
        area = int(cv2.contourArea(contour))

        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(contour)

        # Filter tiny printed specks or text-like strokes.
        aspect_ratio = max(w, h) / max(1, min(w, h))

        if aspect_ratio > 10 and area < 45:
            continue

        spots.append((x, y, w, h, area))

    return spots


def get_whitening_regions(
    card: np.ndarray,
    regions: Optional[Dict[str, RegionBox]] = None
) -> Dict[str, Tuple[np.ndarray, Tuple[int, int]]]:
    """
    Whitening should only analyze edge/corner regions.
    It should NOT analyze logos, art boxes, or inner card text.
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

    edge_w = max(8, int(w * 0.035))
    edge_h = max(8, int(h * 0.035))
    corner_w = max(20, int(w * 0.10))
    corner_h = max(20, int(h * 0.10))

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

            color = (255, 255, 0)
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

    score = score_whitening(
        spot_count=len(whitening_spots),
        total_area=total_area,
        image_area=max(1, total_region_area),
    )

    return WhiteningAnalysisResult(
        score=score,
        spot_count=len(whitening_spots),
        total_spot_area=int(total_area),
        analyzed_area=int(total_region_area),
        severity=classify_severity(score),
        spots=whitening_spots,
        overlay_image=overlay,
    )


def whitening_result_to_dict(result: WhiteningAnalysisResult) -> dict:
    return {
        "score": result.score,
        "spot_count": result.spot_count,
        "total_spot_area": result.total_spot_area,
        "analyzed_area": result.analyzed_area,
        "severity": result.severity,
        "spots": [asdict(spot) for spot in result.spots],
    }
