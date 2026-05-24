from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional

import cv2
import numpy as np

from backend.utils.regions import RegionBox, crop_region


@dataclass
class EdgeSpot:
    side: str
    x: int
    y: int
    width: int
    height: int
    area: int
    severity: str


@dataclass
class EdgeSideResult:
    side: str
    score: float
    spot_count: int
    total_spot_area: int
    analyzed_area: int
    severity: str


@dataclass
class EdgeAnalysisResult:
    overall_score: float
    sides: Dict[str, EdgeSideResult]
    spots: List[EdgeSpot]
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


def score_edge(spot_count: int, total_area: int, edge_area: int) -> float:
    if edge_area <= 0:
        return 0.0

    area_ratio = total_area / edge_area

    penalty = 0
    penalty += spot_count * 0.14
    penalty += area_ratio * 60

    score = 10 - penalty
    return round(max(1.0, min(10.0, score)), 1)


def crop_edge_strip(
    card: np.ndarray,
    side: str,
    strip_ratio: float = 0.035
) -> Tuple[np.ndarray, Tuple[int, int]]:
    h, w = card.shape[:2]

    strip_w = max(8, int(w * strip_ratio))
    strip_h = max(8, int(h * strip_ratio))

    if side == "left":
        return card[:, :strip_w], (0, 0)

    if side == "right":
        return card[:, w - strip_w:w], (w - strip_w, 0)

    if side == "top":
        return card[:strip_h, :], (0, 0)

    if side == "bottom":
        return card[h - strip_h:h, :], (0, h - strip_h)

    raise ValueError(f"Unknown edge side: {side}")


def get_edge_crop(
    card: np.ndarray,
    side: str,
    regions: Optional[Dict[str, RegionBox]] = None
) -> Tuple[np.ndarray, Tuple[int, int]]:
    if regions:
        key = f"{side}_edge"
        if key in regions:
            region = regions[key]
            return crop_region(card, region), (region.x, region.y)

    return crop_edge_strip(card, side)


def build_print_edge_mask(image_bgr: np.ndarray) -> np.ndarray:
    """
    Suppresses printed text/logo/art edges so they are less likely to be
    counted as edge damage.
    """
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    edges = cv2.Canny(blur, 90, 220)

    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    return edges


def detect_edge_whitening(
    strip: np.ndarray,
    min_area: int = 6,
    brightness_threshold: int = 215,
    saturation_threshold: int = 65,
) -> Tuple[List[Tuple[int, int, int, int, int]], np.ndarray]:
    hsv = cv2.cvtColor(strip, cv2.COLOR_BGR2HSV)

    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]

    bright_mask = value > brightness_threshold
    low_sat_mask = saturation < saturation_threshold

    mask = np.logical_and(bright_mask, low_sat_mask).astype(np.uint8) * 255

    print_edge_mask = build_print_edge_mask(strip)

    # Remove printed line/logo/text edges from detection candidates.
    mask[print_edge_mask > 0] = 0

    kernel = np.ones((2, 2), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

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

        aspect_ratio = max(w, h) / max(1, min(w, h))

        # Thin long printed strokes near edges are often text/logo, not damage.
        if aspect_ratio > 12 and area < 55:
            continue

        spots.append((x, y, w, h, area))

    return spots, mask


def analyze_edges(
    card: np.ndarray,
    regions: Optional[Dict[str, RegionBox]] = None
) -> EdgeAnalysisResult:
    overlay = card.copy()

    sides = {}
    all_spots: List[EdgeSpot] = []

    for side in ["left", "right", "top", "bottom"]:
        strip, offset = get_edge_crop(card, side, regions)
        offset_x, offset_y = offset

        raw_spots, _ = detect_edge_whitening(strip)

        total_area = 0

        for x, y, w, h, area in raw_spots:
            global_x = x + offset_x
            global_y = y + offset_y

            total_area += area
            severity = classify_spot(area)

            all_spots.append(
                EdgeSpot(
                    side=side,
                    x=int(global_x),
                    y=int(global_y),
                    width=int(w),
                    height=int(h),
                    area=int(area),
                    severity=severity,
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

        edge_area = strip.shape[0] * strip.shape[1]
        score = score_edge(len(raw_spots), total_area, edge_area)

        sides[side] = EdgeSideResult(
            side=side,
            score=score,
            spot_count=len(raw_spots),
            total_spot_area=int(total_area),
            analyzed_area=int(edge_area),
            severity=classify_severity(score),
        )

    overall_score = round(
        sum(side_result.score for side_result in sides.values()) / len(sides),
        1,
    )

    return EdgeAnalysisResult(
        overall_score=overall_score,
        sides=sides,
        spots=all_spots,
        overlay_image=overlay,
    )


def edge_result_to_dict(result: EdgeAnalysisResult) -> dict:
    return {
        "overall_score": result.overall_score,
        "sides": {
            side: asdict(side_result)
            for side, side_result in result.sides.items()
        },
        "spots": [asdict(spot) for spot in result.spots],
    }
