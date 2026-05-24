from types import SimpleNamespace

from backend.app import (
    app,
    combine_side_scores,
    combined_centering_ratio,
    combined_score,
)
from backend.detectors.corners import score_corner
from backend.detectors.edges import score_edge
from backend.detectors.surface import score_surface
from backend.detectors.whitening import score_whitening
from backend.utils.scoring import calculate_final_grade


def make_side_result(
    horizontal_ratio: str,
    vertical_ratio: str,
    edges_score: float,
    corners_score: float,
    whitening_score: float,
    surface_score: float,
) -> dict:
    return {
        "centering": SimpleNamespace(
            horizontal_ratio=horizontal_ratio,
            vertical_ratio=vertical_ratio,
        ),
        "edges": SimpleNamespace(overall_score=edges_score),
        "corners": SimpleNamespace(overall_score=corners_score),
        "whitening": SimpleNamespace(score=whitening_score),
        "surface": SimpleNamespace(score=surface_score),
    }


def edge_detector(spots: list[dict]) -> dict:
    analyzed_area = 1000
    total_area = sum(spot["area"] for spot in spots)
    score = score_edge(len(spots), total_area, analyzed_area)

    return {
        "overall_score": score,
        "sides": {
            "left": {
                "side": "left",
                "score": score,
                "spot_count": len(spots),
                "total_spot_area": total_area,
                "analyzed_area": analyzed_area,
                "severity": "minor",
            }
        },
        "spots": spots,
    }


def corner_detector(spots: list[dict]) -> dict:
    analyzed_area = 1000
    total_area = sum(spot["area"] for spot in spots)
    score = score_corner(len(spots), total_area, analyzed_area)

    return {
        "overall_score": score,
        "corners": {
            "top_left": {
                "corner": "top_left",
                "score": score,
                "spot_count": len(spots),
                "total_spot_area": total_area,
                "analyzed_area": analyzed_area,
                "severity": "minor",
            }
        },
        "spots": spots,
    }


def whitening_detector(spots: list[dict]) -> dict:
    analyzed_area = 1000
    total_area = sum(spot["area"] for spot in spots)

    return {
        "score": score_whitening(len(spots), total_area, analyzed_area),
        "spot_count": len(spots),
        "total_spot_area": total_area,
        "analyzed_area": analyzed_area,
        "severity": "minor",
        "spots": spots,
    }


def surface_detector(spots: list[dict]) -> dict:
    analyzed_area = 1000
    total_area = sum(spot["area"] for spot in spots)

    return {
        "score": score_surface(len(spots), total_area, analyzed_area),
        "issue_count": len(spots),
        "total_issue_area": total_area,
        "analyzed_area": analyzed_area,
        "severity": "minor",
        "spots": spots,
    }


def test_combined_score_is_equal_front_back_average():
    assert combined_score(10, 6) == 8.0


def test_combined_centering_ratio_averages_off_center_amounts():
    assert combined_centering_ratio("40/60", "50/50") == "45/55"


def test_combine_side_scores_uses_equal_front_back_weights():
    front = make_side_result("40/60", "50/50", 10, 8, 6, 4)
    back = make_side_result("50/50", "40/60", 2, 4, 8, 10)

    result = combine_side_scores(front, back)

    expected = calculate_final_grade(
        centering_horizontal_ratio="45/55",
        centering_vertical_ratio="45/55",
        edges_score=6,
        corners_score=6,
        whitening_score=7,
        surface_score=7,
    )

    assert result.final_grade == expected.final_grade
    assert result.grade_label == expected.grade_label
    assert result.grade_bucket == expected.grade_bucket


def test_recalculate_endpoint_returns_combined_subgrades_after_ignored_spots():
    front_edge_spot = {
        "side": "left",
        "x": 1,
        "y": 2,
        "width": 3,
        "height": 4,
        "area": 100,
        "severity": "heavy",
    }

    analysis = {
        "mode": "front_back",
        "centering": {
            "horizontal_ratio": "40/60",
            "vertical_ratio": "50/50",
        },
        "back_centering": {
            "horizontal_ratio": "50/50",
            "vertical_ratio": "40/60",
        },
        "edges": edge_detector([front_edge_spot]),
        "corners": corner_detector([]),
        "whitening": whitening_detector([]),
        "surface": surface_detector([]),
        "back": {
            "edges": edge_detector([]),
            "corners": corner_detector([]),
            "whitening": whitening_detector([]),
            "surface": surface_detector([]),
        },
    }

    client = app.test_client()
    response = client.post(
        "/corrections/recalculate",
        json={
            "analysis": analysis,
            "ignored_spot_ids": ["front:edges:0:1:2"],
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["final_grade"]["final_grade"] is not None
    assert data["combined"]["centering"]["horizontal_ratio"] == "45/55"
    assert data["combined"]["centering"]["vertical_ratio"] == "45/55"
    assert data["combined"]["edges"]["overall_score"] == 10
    assert data["combined"]["edges"]["spot_count"] == 0
