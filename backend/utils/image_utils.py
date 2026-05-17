import numpy as np
from PIL import Image
import cv2


def pil_to_bgr(pil_image: Image.Image) -> np.ndarray:
    rgb = np.array(pil_image.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def resize_for_display(image: np.ndarray, max_dim: int = 1000) -> np.ndarray:
    h, w = image.shape[:2]
    max_current = max(h, w)

    if max_current <= max_dim:
        return image

    scale = max_dim / max_current
    new_w = int(w * scale)
    new_h = int(h * scale)

    return cv2.resize(image, (new_w, new_h))