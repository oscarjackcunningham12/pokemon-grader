import cv2
import numpy as np

from backend.detectors.surface import detect_surface_damage, score_surface


def test_detect_surface_damage_ignores_printed_text():
    image = np.full((160, 240, 3), 210, dtype=np.uint8)

    cv2.putText(
        image,
        "HP 120",
        (18, 80),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (10, 10, 10),
        3,
        cv2.LINE_AA,
    )
    cv2.putText(
        image,
        "ATTACK",
        (22, 122),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (0, 0, 220),
        2,
        cv2.LINE_AA,
    )

    spots, _ = detect_surface_damage(image)

    assert spots == []


def test_surface_scoring_is_stricter_for_multiple_issues():
    clean_score = score_surface(0, 0, 10000)
    damaged_score = score_surface(3, 900, 10000)

    assert clean_score == 10
    assert damaged_score <= 4.7
