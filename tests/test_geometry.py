import numpy as np

from tests.test_geometry import order_points, four_point_transform


def test_order_points_returns_expected_order():
    pts = np.array([
        [100, 100],  # bottom-right
        [0, 0],      # top-left
        [100, 0],    # top-right
        [0, 100],    # bottom-left
    ], dtype="float32")

    ordered = order_points(pts)

    assert ordered[0].tolist() == [0, 0]
    assert ordered[1].tolist() == [100, 0]
    assert ordered[2].tolist() == [100, 100]
    assert ordered[3].tolist() == [0, 100]


def test_four_point_transform_returns_image():
    image = np.zeros((120, 120, 3), dtype=np.uint8)

    pts = np.array([
        [10, 10],
        [100, 10],
        [100, 100],
        [10, 100],
    ], dtype="float32")

    warped = four_point_transform(image, pts)

    assert warped is not None
    assert warped.shape[0] > 0
    assert warped.shape[1] > 0
    assert warped.shape[2] == 3