from typing import Tuple

import cv2
import numpy as np


Color = Tuple[int, int, int]

GREEN: Color = (0, 255, 0)
BLUE: Color = (255, 180, 0)
RED: Color = (0, 0, 255)
YELLOW: Color = (0, 255, 255)
MAGENTA: Color = (255, 0, 255)
WHITE: Color = (255, 255, 255)


def draw_box(
    image: np.ndarray,
    x: int,
    y: int,
    width: int,
    height: int,
    color: Color = RED,
    thickness: int = 1,
) -> np.ndarray:
    overlay = image.copy()
    cv2.rectangle(
        overlay,
        (int(x), int(y)),
        (int(x + width), int(y + height)),
        color,
        thickness,
    )
    return overlay


def draw_line(
    image: np.ndarray,
    start: tuple[int, int],
    end: tuple[int, int],
    color: Color = GREEN,
    thickness: int = 1,
) -> np.ndarray:
    overlay = image.copy()
    cv2.line(overlay, start, end, color, thickness)
    return overlay


def draw_label(
    image: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: Color = WHITE,
    font_scale: float = 0.45,
    thickness: int = 1,
) -> np.ndarray:
    overlay = image.copy()
    cv2.putText(
        overlay,
        text,
        (int(x), int(y)),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        color,
        thickness,
        cv2.LINE_AA,
    )
    return overlay


def draw_labeled_box(
    image: np.ndarray,
    x: int,
    y: int,
    width: int,
    height: int,
    label: str,
    color: Color = RED,
    thickness: int = 1,
) -> np.ndarray:
    overlay = draw_box(image, x, y, width, height, color, thickness)
    label_y = max(12, int(y) - 4)
    overlay = draw_label(overlay, label, int(x), label_y, color)
    return overlay


def blend_overlay(
    base: np.ndarray,
    overlay: np.ndarray,
    alpha: float = 0.7,
) -> np.ndarray:
    return cv2.addWeighted(overlay, alpha, base, 1 - alpha, 0)