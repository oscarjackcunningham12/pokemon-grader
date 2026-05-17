import cv2
import numpy as np


def draw_regions_overlay(card: np.ndarray, regions: dict) -> np.ndarray:
    """
    Visual debug overlay showing the grading regions derived
    from manual centering selection.
    """

    overlay = card.copy()

    def fill_region(region_name, color, alpha=0.22):
        if region_name not in regions:
            return

        region = regions[region_name]

        x = region.x
        y = region.y
        w = region.width
        h = region.height

        temp = overlay.copy()

        cv2.rectangle(
            temp,
            (x, y),
            (x + w, y + h),
            color,
            -1,
        )

        cv2.addWeighted(temp, alpha, overlay, 1 - alpha, 0, overlay)

        cv2.rectangle(
            overlay,
            (x, y),
            (x + w, y + h),
            color,
            1,
        )

    # Surface
    fill_region("surface", (0, 255, 255), alpha=0.16)

    # Edge regions
    edge_color = (255, 80, 80)

    fill_region("left_edge", edge_color)
    fill_region("right_edge", edge_color)
    fill_region("top_edge", edge_color)
    fill_region("bottom_edge", edge_color)

    # Corner regions
    corner_color = (180, 80, 255)

    fill_region("top_left_corner", corner_color)
    fill_region("top_right_corner", corner_color)
    fill_region("bottom_left_corner", corner_color)
    fill_region("bottom_right_corner", corner_color)

    return overlay