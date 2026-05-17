from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from utils.geometry import four_point_transform
from utils.image_utils import resize_for_display
from utils.regions import centering_measurements_from_lines


@dataclass
class BorderMeasurements:
    left: int
    right: int
    top: int
    bottom: int


@dataclass
class AnalysisResult:
    card_image: np.ndarray
    overlay_image: np.ndarray
    borders: BorderMeasurements
    horizontal_ratio: str
    vertical_ratio: str
    confidence_note: str


def centering_ratio(a: int, b: int) -> str:
    total = a + b
    if total <= 0:
        return "N/A"

    smaller = min(a, b)
    small_pct = round((smaller / total) * 100)
    large_pct = 100 - small_pct
    return f"{small_pct}/{large_pct}"


def find_card_corners(image: np.ndarray) -> Optional[np.ndarray]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blur, 50, 150)

    kernel = np.ones((5, 5), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=2)
    edges = cv2.erode(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    image_area = image.shape[0] * image.shape[1]

    for contour in contours[:20]:
        area = cv2.contourArea(contour)
        if area < image_area * 0.08:
            continue

        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

        if len(approx) == 4:
            return approx.reshape(4, 2).astype("float32")

        rect = cv2.minAreaRect(contour)
        box = cv2.boxPoints(rect)
        box = np.array(box, dtype="float32")

        if cv2.contourArea(box) > image_area * 0.08:
            return box

    return None


def estimate_border_thickness(card: np.ndarray, side: str, roi_pct: float = 0.22) -> Optional[int]:
    h, w = card.shape[:2]
    hsv = cv2.cvtColor(card, cv2.COLOR_BGR2HSV)

    if side in ("left", "right"):
        roi_width = max(20, int(w * roi_pct))
        y1, y2 = int(h * 0.20), int(h * 0.80)

        if side == "left":
            roi = hsv[y1:y2, :roi_width]
            signal = 0.6 * roi[:, :, 1].mean(axis=0) + 0.4 * roi[:, :, 2].mean(axis=0)
            grad = np.abs(np.diff(signal))
            if len(grad) < 5:
                return None
            return int(np.argmax(grad[5:]) + 5)

        roi = hsv[y1:y2, w - roi_width:w]
        signal = 0.6 * roi[:, :, 1].mean(axis=0) + 0.4 * roi[:, :, 2].mean(axis=0)
        grad = np.abs(np.diff(signal[::-1]))
        if len(grad) < 5:
            return None
        return int(np.argmax(grad[5:]) + 5)

    roi_height = max(20, int(h * roi_pct))
    x1, x2 = int(w * 0.20), int(w * 0.80)

    if side == "top":
        roi = hsv[:roi_height, x1:x2]
        signal = 0.6 * roi[:, :, 1].mean(axis=1) + 0.4 * roi[:, :, 2].mean(axis=1)
        grad = np.abs(np.diff(signal))
        if len(grad) < 5:
            return None
        return int(np.argmax(grad[5:]) + 5)

    roi = hsv[h - roi_height:h, x1:x2]
    signal = 0.6 * roi[:, :, 1].mean(axis=1) + 0.4 * roi[:, :, 2].mean(axis=1)
    grad = np.abs(np.diff(signal[::-1]))

    if len(grad) < 5:
        return None

    return int(np.argmax(grad[5:]) + 5)


def draw_overlay(card: np.ndarray, borders: BorderMeasurements, stroke_width: int = 1) -> np.ndarray:
    overlay = card.copy()
    h, w = overlay.shape[:2]

    left_x = borders.left
    right_x = w - borders.right
    top_y = borders.top
    bottom_y = h - borders.bottom

    cv2.line(overlay, (left_x, 0), (left_x, h - 1), (0, 255, 0), stroke_width)
    cv2.line(overlay, (right_x, 0), (right_x, h - 1), (0, 255, 0), stroke_width)
    cv2.line(overlay, (0, top_y), (w - 1, top_y), (255, 0, 0), stroke_width)
    cv2.line(overlay, (0, bottom_y), (w - 1, bottom_y), (255, 0, 0), stroke_width)
    cv2.rectangle(overlay, (left_x, top_y), (right_x, bottom_y), (255, 255, 255), stroke_width)

    return overlay


def draw_manual_line_overlay(card: np.ndarray, manual_lines: dict, stroke_width: int = 1) -> np.ndarray:
    overlay = card.copy()
    h, w = overlay.shape[:2]

    line_color_green = (0, 255, 0)
    line_color_blue = (255, 180, 0)

    required_keys = [
        "left_outer",
        "left_inner",
        "right_inner",
        "right_outer",
        "top_outer",
        "top_inner",
        "bottom_inner",
        "bottom_outer",
    ]

    for key in required_keys:
        if key not in manual_lines:
            raise ValueError(f"Missing manual centering line: {key}")

    left_outer = int(manual_lines["left_outer"])
    left_inner = int(manual_lines["left_inner"])
    right_inner = int(manual_lines["right_inner"])
    right_outer = int(manual_lines["right_outer"])

    top_outer = int(manual_lines["top_outer"])
    top_inner = int(manual_lines["top_inner"])
    bottom_inner = int(manual_lines["bottom_inner"])
    bottom_outer = int(manual_lines["bottom_outer"])

    # Vertical green pair
    cv2.line(overlay, (left_outer, 0), (left_outer, h - 1), line_color_green, stroke_width)
    cv2.line(overlay, (left_inner, 0), (left_inner, h - 1), line_color_green, stroke_width)

    # Vertical blue pair
    cv2.line(overlay, (right_inner, 0), (right_inner, h - 1), line_color_blue, stroke_width)
    cv2.line(overlay, (right_outer, 0), (right_outer, h - 1), line_color_blue, stroke_width)

    # Horizontal green pair
    cv2.line(overlay, (0, top_outer), (w - 1, top_outer), line_color_green, stroke_width)
    cv2.line(overlay, (0, top_inner), (w - 1, top_inner), line_color_green, stroke_width)

    # Horizontal blue pair
    cv2.line(overlay, (0, bottom_inner), (w - 1, bottom_inner), line_color_blue, stroke_width)
    cv2.line(overlay, (0, bottom_outer), (w - 1, bottom_outer), line_color_blue, stroke_width)

    return overlay


def analyze_centering(image_bgr: np.ndarray, manual_lines: Optional[dict] = None) -> AnalysisResult:
    corners = find_card_corners(image_bgr)
    if corners is None:
        raise ValueError(
            "Could not detect the outer card edges. Try a cleaner background or better lighting."
        )

    card = four_point_transform(image_bgr, corners)
    card = resize_for_display(card)

    if manual_lines:
        h, w = card.shape[:2]
        measurements = centering_measurements_from_lines(manual_lines, w, h)

        borders = BorderMeasurements(
            left=int(measurements["left"]),
            right=int(measurements["right"]),
            top=int(measurements["top"]),
            bottom=int(measurements["bottom"]),
        )

        overlay = draw_manual_line_overlay(card, manual_lines)

        return AnalysisResult(
            card_image=card,
            overlay_image=overlay,
            borders=borders,
            horizontal_ratio=centering_ratio(borders.left, borders.right),
            vertical_ratio=centering_ratio(borders.top, borders.bottom),
            confidence_note="Manual centering lines used.",
        )

    left = estimate_border_thickness(card, "left")
    right = estimate_border_thickness(card, "right")
    top = estimate_border_thickness(card, "top")
    bottom = estimate_border_thickness(card, "bottom")

    if None in (left, right, top, bottom):
        raise ValueError("Could not estimate one or more borders.")

    borders = BorderMeasurements(
        left=int(left),
        right=int(right),
        top=int(top),
        bottom=int(bottom),
    )

    overlay = draw_overlay(card, borders)

    return AnalysisResult(
        card_image=card,
        overlay_image=overlay,
        borders=borders,
        horizontal_ratio=centering_ratio(borders.left, borders.right),
        vertical_ratio=centering_ratio(borders.top, borders.bottom),
        confidence_note="Estimated from visual border transitions.",
    )