import numpy as np

from backend.detectors.corners import analyze_corners


def test_analyze_corners_returns_result():
    card = np.zeros((400, 280, 3), dtype=np.uint8)

    result = analyze_corners(card)

    assert result.overall_score is not None
    assert set(result.corners.keys()) == {
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
    }
    assert isinstance(result.spots, list)
    assert result.overlay_image.shape == card.shape