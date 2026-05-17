import base64
import io
import json

import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image

from detectors.centering import analyze_centering
from detectors.edges import analyze_edges, edge_result_to_dict
from detectors.corners import analyze_corners, corner_result_to_dict
from detectors.whitening import analyze_whitening, whitening_result_to_dict
from detectors.surface import analyze_surface, surface_result_to_dict
from utils.image_utils import pil_to_bgr, bgr_to_rgb
from utils.scoring import calculate_final_grade, final_grade_to_dict
from utils.regions import build_regions_from_centering_lines, regions_to_dict
from utils.regions_overlay import draw_regions_overlay


app = Flask(__name__)
CORS(app)


def image_to_base64(image: np.ndarray) -> str:
    rgb = bgr_to_rgb(image) if len(image.shape) == 3 and image.shape[2] == 3 else image
    pil_image = Image.fromarray(rgb)

    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")

    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def get_json_field(field_name: str):
    if field_name not in request.form:
        return None

    try:
        return json.loads(request.form[field_name])
    except Exception:
        return None


def load_image_from_request(file_key: str) -> np.ndarray:
    if file_key not in request.files:
        raise ValueError(f"Missing required image: {file_key}")

    file = request.files[file_key]
    pil_image = Image.open(file.stream)
    return pil_to_bgr(pil_image)


def analyze_one_side(image_bgr: np.ndarray, manual_lines=None) -> dict:
    centering = analyze_centering(
        image_bgr,
        manual_lines=manual_lines
    )

    card = centering.card_image
    h, w = card.shape[:2]

    regions = None
    if manual_lines:
        regions = build_regions_from_centering_lines(
            manual_lines,
            image_width=w,
            image_height=h,
        )

    edges = analyze_edges(card, regions=regions)
    corners = analyze_corners(card, regions=regions)
    whitening = analyze_whitening(card, regions=regions)
    surface = analyze_surface(card, regions=regions)

    regions_overlay = (
        draw_regions_overlay(card, regions)
        if regions
        else card
    )

    return {
        "centering": centering,
        "card": card,
        "regions": regions,
        "regions_overlay": regions_overlay,
        "edges": edges,
        "corners": corners,
        "whitening": whitening,
        "surface": surface,
    }
def ratio_off_center_amount(ratio: str) -> int:
    try:
        a, b = ratio.split("/")
        return abs(int(a) - int(b))
    except Exception:
        return 999


def worse_centering_ratio(front_ratio: str, back_ratio: str) -> str:
    """
    Uses the worse of the front/back centering ratios.
    Example:
    front = 48/52
    back = 42/58

    Result = 42/58
    """
    front_off = ratio_off_center_amount(front_ratio)
    back_off = ratio_off_center_amount(back_ratio)

    return back_ratio if back_off > front_off else front_ratio

def combine_side_scores(front_result: dict, back_result: dict):
    front_centering = front_result["centering"]
    back_centering = back_result["centering"]

    front_edges = front_result["edges"]
    front_corners = front_result["corners"]
    front_whitening = front_result["whitening"]
    front_surface = front_result["surface"]

    back_edges = back_result["edges"]
    back_corners = back_result["corners"]
    back_whitening = back_result["whitening"]

    combined_centering_horizontal = worse_centering_ratio(
        front_centering.horizontal_ratio,
        back_centering.horizontal_ratio,
    )

    combined_centering_vertical = worse_centering_ratio(
        front_centering.vertical_ratio,
        back_centering.vertical_ratio,
    )

    combined_edges_score = round(
        (front_edges.overall_score * 0.45) + (back_edges.overall_score * 0.55),
        1,
    )

    combined_corners_score = round(
        (front_corners.overall_score * 0.45) + (back_corners.overall_score * 0.55),
        1,
    )

    combined_whitening_score = round(
        (front_whitening.score * 0.35) + (back_whitening.score * 0.65),
        1,
    )

    # For now, surface is mostly front-weighted.
    # Back logo/text creates false positives, so we do not heavily use back surface.
    combined_surface_score = round(front_surface.score, 1)

    return calculate_final_grade(
        centering_horizontal_ratio=combined_centering_horizontal,
        centering_vertical_ratio=combined_centering_vertical,
        edges_score=combined_edges_score,
        corners_score=combined_corners_score,
        whitening_score=combined_whitening_score,
        surface_score=combined_surface_score,
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/analyze/full", methods=["POST"])
def analyze_full_route():
    try:
        front_manual_lines = get_json_field("front_manual_lines")
        back_manual_lines = get_json_field("back_manual_lines")

        # Backwards compatibility with older frontend
        old_manual_lines = get_json_field("manual_lines")
        if old_manual_lines and not front_manual_lines:
            front_manual_lines = old_manual_lines

        if "front_image" in request.files and "back_image" in request.files:
            front_bgr = load_image_from_request("front_image")
            back_bgr = load_image_from_request("back_image")

            front = analyze_one_side(front_bgr, manual_lines=front_manual_lines)
            back = analyze_one_side(back_bgr, manual_lines=back_manual_lines)

            final_grade = combine_side_scores(front, back)

            response = {
                "mode": "front_back",
                "final_grade": final_grade_to_dict(final_grade),
                "centering": {
                    "borders": {
                        "left": front["centering"].borders.left,
                        "right": front["centering"].borders.right,
                        "top": front["centering"].borders.top,
                        "bottom": front["centering"].borders.bottom,
                    },
                    "horizontal_ratio": front["centering"].horizontal_ratio,
                    "vertical_ratio": front["centering"].vertical_ratio,
                    "confidence_note": front["centering"].confidence_note,
                },
                "back_centering": {
                    "borders": {
                        "left": back["centering"].borders.left,
                        "right": back["centering"].borders.right,
                        "top": back["centering"].borders.top,
                        "bottom": back["centering"].borders.bottom,
                    },
                    "horizontal_ratio": back["centering"].horizontal_ratio,
                    "vertical_ratio": back["centering"].vertical_ratio,
                    "confidence_note": back["centering"].confidence_note,
                },
                "regions": {
                    "front": regions_to_dict(front["regions"]) if front["regions"] else None,
                    "back": regions_to_dict(back["regions"]) if back["regions"] else None,
                },
                "edges": edge_result_to_dict(front["edges"]),
                "corners": corner_result_to_dict(front["corners"]),
                "whitening": whitening_result_to_dict(front["whitening"]),
                "surface": surface_result_to_dict(front["surface"]),
                "back": {
                    "edges": edge_result_to_dict(back["edges"]),
                    "corners": corner_result_to_dict(back["corners"]),
                    "whitening": whitening_result_to_dict(back["whitening"]),
                    "surface": surface_result_to_dict(back["surface"]),
                },
                "images": {
                    "card": image_to_base64(front["card"]),
                    "centering_overlay": image_to_base64(front["centering"].overlay_image),
                    "regions_overlay": image_to_base64(front["regions_overlay"]),
                    "edges_overlay": image_to_base64(front["edges"].overlay_image),
                    "corners_overlay": image_to_base64(front["corners"].overlay_image),
                    "whitening_overlay": image_to_base64(front["whitening"].overlay_image),
                    "surface_overlay": image_to_base64(front["surface"].overlay_image),

                    "back_card": image_to_base64(back["card"]),
                    "back_centering_overlay": image_to_base64(back["centering"].overlay_image),
                    "back_regions_overlay": image_to_base64(back["regions_overlay"]),
                    "back_edges_overlay": image_to_base64(back["edges"].overlay_image),
                    "back_corners_overlay": image_to_base64(back["corners"].overlay_image),
                    "back_whitening_overlay": image_to_base64(back["whitening"].overlay_image),
                    "back_surface_overlay": image_to_base64(back["surface"].overlay_image),
                },
            }

            return jsonify(response)

        if "image" in request.files:
            image_bgr = load_image_from_request("image")
            result = analyze_one_side(image_bgr, manual_lines=front_manual_lines)

            final_grade = calculate_final_grade(
                centering_horizontal_ratio=result["centering"].horizontal_ratio,
                centering_vertical_ratio=result["centering"].vertical_ratio,
                edges_score=result["edges"].overall_score,
                corners_score=result["corners"].overall_score,
                whitening_score=result["whitening"].score,
                surface_score=result["surface"].score,
            )

            response = {
                "mode": "single",
                "final_grade": final_grade_to_dict(final_grade),
                "centering": {
                    "borders": {
                        "left": result["centering"].borders.left,
                        "right": result["centering"].borders.right,
                        "top": result["centering"].borders.top,
                        "bottom": result["centering"].borders.bottom,
                    },
                    "horizontal_ratio": result["centering"].horizontal_ratio,
                    "vertical_ratio": result["centering"].vertical_ratio,
                    "confidence_note": result["centering"].confidence_note,
                },
                "regions": regions_to_dict(result["regions"]) if result["regions"] else None,
                "edges": edge_result_to_dict(result["edges"]),
                "corners": corner_result_to_dict(result["corners"]),
                "whitening": whitening_result_to_dict(result["whitening"]),
                "surface": surface_result_to_dict(result["surface"]),
                "images": {
                    "card": image_to_base64(result["card"]),
                    "centering_overlay": image_to_base64(result["centering"].overlay_image),
                    "regions_overlay": image_to_base64(result["regions_overlay"]),
                    "edges_overlay": image_to_base64(result["edges"].overlay_image),
                    "corners_overlay": image_to_base64(result["corners"].overlay_image),
                    "whitening_overlay": image_to_base64(result["whitening"].overlay_image),
                    "surface_overlay": image_to_base64(result["surface"].overlay_image),
                },
            }

            return jsonify(response)

        return jsonify({"error": "No image uploaded."}), 400

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/analyze/centering", methods=["POST"])
def analyze_centering_route():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded."}), 400

    try:
        image_bgr = load_image_from_request("image")
        manual_lines = get_json_field("manual_lines")

        centering = analyze_centering(
            image_bgr,
            manual_lines=manual_lines
        )

        return jsonify({
            "borders": {
                "left": centering.borders.left,
                "right": centering.borders.right,
                "top": centering.borders.top,
                "bottom": centering.borders.bottom,
            },
            "horizontal_ratio": centering.horizontal_ratio,
            "vertical_ratio": centering.vertical_ratio,
            "confidence_note": centering.confidence_note,
            "card_image_base64": image_to_base64(centering.card_image),
            "overlay_image_base64": image_to_base64(centering.overlay_image),
        })

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(debug=True) 