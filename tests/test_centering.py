import numpy as np

from backend.detectors.centering import centering_ratio


def test_centering_ratio_even():
    assert centering_ratio(50, 50) == "50/50"


def test_centering_ratio_uneven():
    assert centering_ratio(40, 60) == "40/60"


def test_centering_ratio_zero_total():
    assert centering_ratio(0, 0) == "N/A"