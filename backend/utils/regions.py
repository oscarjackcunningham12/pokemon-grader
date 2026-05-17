from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class CenteringLines:
    left_outer: int
    left_inner: int
    right_inner: int
    right_outer: int
    top_outer: int
    top_inner: int
    bottom_inner: int
    bottom_outer: int


@dataclass
class RegionBox:
    x: int
    y: int
    width: int
    height: int


def normalize_centering_lines(lines: Dict[str, int], image_width: int, image_height: int) -> CenteringLines:
    """
    Ensures all centering lines are inside the image and in the correct order.
    """

    left_outer = clamp(lines["left_outer"], 0, image_width - 1)
    left_inner = clamp(lines["left_inner"], 0, image_width - 1)
    right_inner = clamp(lines["right_inner"], 0, image_width - 1)
    right_outer = clamp(lines["right_outer"], 0, image_width - 1)

    top_outer = clamp(lines["top_outer"], 0, image_height - 1)
    top_inner = clamp(lines["top_inner"], 0, image_height - 1)
    bottom_inner = clamp(lines["bottom_inner"], 0, image_height - 1)
    bottom_outer = clamp(lines["bottom_outer"], 0, image_height - 1)

    x_values = sorted([left_outer, left_inner, right_inner, right_outer])
    y_values = sorted([top_outer, top_inner, bottom_inner, bottom_outer])

    return CenteringLines(
        left_outer=x_values[0],
        left_inner=x_values[1],
        right_inner=x_values[2],
        right_outer=x_values[3],
        top_outer=y_values[0],
        top_inner=y_values[1],
        bottom_inner=y_values[2],
        bottom_outer=y_values[3],
    )


def build_regions_from_centering_lines(
    lines: Dict[str, int],
    image_width: int,
    image_height: int,
) -> Dict[str, RegionBox]:
    """
    Converts manual centering guide lines into usable grading regions.

    These regions become the source of truth for:
    - edges
    - corners
    - whitening
    - surface
    """

    normalized = normalize_centering_lines(lines, image_width, image_height)

    left_outer = normalized.left_outer
    left_inner = normalized.left_inner
    right_inner = normalized.right_inner
    right_outer = normalized.right_outer

    top_outer = normalized.top_outer
    top_inner = normalized.top_inner
    bottom_inner = normalized.bottom_inner
    bottom_outer = normalized.bottom_outer

    card_width = right_outer - left_outer
    card_height = bottom_outer - top_outer

    corner_w = max(12, int(card_width * 0.12))
    corner_h = max(12, int(card_height * 0.12))

    edge_thickness_x = max(6, int(card_width * 0.035))
    edge_thickness_y = max(6, int(card_height * 0.035))

    return {
        # Full selected card
        "card": box(
            left_outer,
            top_outer,
            right_outer - left_outer,
            bottom_outer - top_outer,
        ),

        # Inner art / surface zone
        "surface": box(
            left_inner,
            top_inner,
            right_inner - left_inner,
            bottom_inner - top_inner,
        ),

        # Border zones
        "left_border": box(
            left_outer,
            top_outer,
            left_inner - left_outer,
            bottom_outer - top_outer,
        ),
        "right_border": box(
            right_inner,
            top_outer,
            right_outer - right_inner,
            bottom_outer - top_outer,
        ),
        "top_border": box(
            left_outer,
            top_outer,
            right_outer - left_outer,
            top_inner - top_outer,
        ),
        "bottom_border": box(
            left_outer,
            bottom_inner,
            right_outer - left_outer,
            bottom_outer - bottom_inner,
        ),

        # Thin outer edge zones
        "left_edge": box(
            left_outer,
            top_outer,
            edge_thickness_x,
            bottom_outer - top_outer,
        ),
        "right_edge": box(
            right_outer - edge_thickness_x,
            top_outer,
            edge_thickness_x,
            bottom_outer - top_outer,
        ),
        "top_edge": box(
            left_outer,
            top_outer,
            right_outer - left_outer,
            edge_thickness_y,
        ),
        "bottom_edge": box(
            left_outer,
            bottom_outer - edge_thickness_y,
            right_outer - left_outer,
            edge_thickness_y,
        ),

        # Corner zones
        "top_left_corner": box(
            left_outer,
            top_outer,
            corner_w,
            corner_h,
        ),
        "top_right_corner": box(
            right_outer - corner_w,
            top_outer,
            corner_w,
            corner_h,
        ),
        "bottom_left_corner": box(
            left_outer,
            bottom_outer - corner_h,
            corner_w,
            corner_h,
        ),
        "bottom_right_corner": box(
            right_outer - corner_w,
            bottom_outer - corner_h,
            corner_w,
            corner_h,
        ),
    }


def centering_measurements_from_lines(lines: Dict[str, int], image_width: int, image_height: int) -> Dict[str, int]:
    normalized = normalize_centering_lines(lines, image_width, image_height)

    return {
        "left": max(0, normalized.left_inner - normalized.left_outer),
        "right": max(0, normalized.right_outer - normalized.right_inner),
        "top": max(0, normalized.top_inner - normalized.top_outer),
        "bottom": max(0, normalized.bottom_outer - normalized.bottom_inner),
    }


def crop_region(image, region: RegionBox):
    return image[
        region.y:region.y + region.height,
        region.x:region.x + region.width
    ]


def box(x: int, y: int, width: int, height: int) -> RegionBox:
    return RegionBox(
        x=max(0, int(x)),
        y=max(0, int(y)),
        width=max(1, int(width)),
        height=max(1, int(height)),
    )


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(int(value), maximum))


def region_to_dict(region: RegionBox) -> dict:
    return {
        "x": region.x,
        "y": region.y,
        "width": region.width,
        "height": region.height,
    }


def regions_to_dict(regions: Dict[str, RegionBox]) -> dict:
    return {
        name: region_to_dict(region)
        for name, region in regions.items()
    }