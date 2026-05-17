import numpy as np
from PIL import Image

from backend.utils.image_utils import pil_to_bgr, bgr_to_rgb, resize_for_display


def test_pil_to_bgr_returns_numpy_image():
    pil_image = Image.new("RGB", (100, 100), color=(255, 0, 0))

    bgr = pil_to_bgr(pil_image)

    assert isinstance(bgr, np.ndarray)
    assert bgr.shape == (100, 100, 3)


def test_bgr_to_rgb_returns_numpy_image():
    bgr = np.zeros((100, 100, 3), dtype=np.uint8)

    rgb = bgr_to_rgb(bgr)

    assert isinstance(rgb, np.ndarray)
    assert rgb.shape == (100, 100, 3)


def test_resize_for_display_scales_large_image_down():
    image = np.zeros((2000, 1000, 3), dtype=np.uint8)

    resized = resize_for_display(image, max_dim=1000)

    assert max(resized.shape[:2]) == 1000


def test_resize_for_display_does_not_scale_small_image_up():
    image = np.zeros((500, 300, 3), dtype=np.uint8)

    resized = resize_for_display(image, max_dim=1000)

    assert resized.shape == image.shape