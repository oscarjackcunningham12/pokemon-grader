import numpy as np

from backend.detectors import edges


def test_analyze_edges_returns_result():
    card = np.zeros((400, 280, 3), dtype=np.uint8)

    result = edges.analyze_edges(card)

    assert result.overall_score is not None
    assert set(result.sides.keys()) == {"left", "right", "top", "bottom"}
    assert isinstance(result.spots, list)
    assert result.overlay_image.shape == card.shape


def test_edge_spots_include_dimensions(monkeypatch):
    card = np.zeros((400, 280, 3), dtype=np.uint8)

    def fake_detect_edge_whitening(strip):
        return [(1, 2, 3, 4, 12)], np.zeros(strip.shape[:2], dtype=np.uint8)

    monkeypatch.setattr(edges, "detect_edge_whitening", fake_detect_edge_whitening)

    result = edges.edge_result_to_dict(edges.analyze_edges(card))

    assert result["spots"][0]["width"] == 3
    assert result["spots"][0]["height"] == 4
