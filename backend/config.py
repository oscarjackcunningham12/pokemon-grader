# Scoring weights (used in scoring.py)
SCORING_WEIGHTS = {
    "centering": 0.20,
    "edges": 0.20,
    "corners": 0.25,
    "whitening": 0.15,
    "surface": 0.20,
}


# Thresholds for whitening detection
WHITENING_CONFIG = {
    "brightness_threshold": 210,
    "saturation_threshold": 75,
    "min_area": 5,
}


# Thresholds for edge detection
EDGE_CONFIG = {
    "brightness_threshold": 205,
    "saturation_threshold": 80,
    "min_area": 4,
}


# Thresholds for corner detection
CORNER_CONFIG = {
    "brightness_threshold": 205,
    "saturation_threshold": 80,
    "min_area": 4,
}


# Surface detection tuning
SURFACE_CONFIG = {
    "canny_low": 40,
    "canny_high": 120,
    "min_area": 6,
}