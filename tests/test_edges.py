import numpy as np

from backend.detectors.edges import analyze_edges


def test_analyze_edges_returns_result():
    card = np.zeros((400, 280, 3), dtype=np.uint8)

    result = analyze_edges(card)

    assert result.overall_score is not None
    assert set(result.sides.keys()) == {"left", "right", "top", "bottom"}
    assert isinstance(result.spots, list)
    assert result.overlay_image.shape == card.shape