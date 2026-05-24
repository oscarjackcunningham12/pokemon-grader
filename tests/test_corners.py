import numpy as np

from backend.detectors import corners


def test_analyze_corners_returns_result():
    card = np.zeros((400, 280, 3), dtype=np.uint8)

    result = corners.analyze_corners(card)

    assert result.overall_score is not None
    assert set(result.corners.keys()) == {
        "top_left",
        "top_right",
        "bottom_left",
        "bottom_right",
    }
    assert isinstance(result.spots, list)
    assert result.overlay_image.shape == card.shape


def test_corner_spots_include_dimensions(monkeypatch):
    card = np.zeros((400, 280, 3), dtype=np.uint8)

    def fake_detect_corner_whitening(crop):
        return [(1, 2, 3, 4, 12)], np.zeros(crop.shape[:2], dtype=np.uint8)

    monkeypatch.setattr(corners, "detect_corner_whitening", fake_detect_corner_whitening)

    result = corners.corner_result_to_dict(corners.analyze_corners(card))

    assert result["spots"][0]["width"] == 3
    assert result["spots"][0]["height"] == 4
