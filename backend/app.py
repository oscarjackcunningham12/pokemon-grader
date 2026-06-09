import base64
import io
import json

import numpy as np
from flask import Flask, jsonify, request
from flask_cors import CORS
from PIL import Image

from backend.detectors.centering import analyze_centering
from backend.detectors.edges import (
    analyze_edges,
    edge_result_to_dict,
    score_edge,
    classify_severity as classify_edge_severity,
)
from backend.detectors.corners import (
    analyze_corners,
    corner_result_to_dict,
    score_corner,
    classify_severity as classify_corner_severity,
)
from backend.detectors.whitening import (
    analyze_whitening,
    whitening_result_to_dict,
    score_whitening,
    classify_severity as classify_whitening_severity,
)
from backend.detectors.surface import (
    analyze_surface,
    surface_result_to_dict,
    score_surface,
    classify_severity as classify_surface_severity,
)
from backend.detectors.identifier import CardIdentificationDebugError, CardIdentificationError, identify_card
from backend.utils.image_utils import pil_to_bgr, bgr_to_rgb
from backend.utils.scoring import (
    calculate_final_grade,
    final_grade_to_dict,
    finding_grade_penalty,
)
from backend.utils.regions import build_regions_from_centering_lines, regions_to_dict
from backend.utils.regions_overlay import draw_regions_overlay


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


def get_json_form_field(field_name: str):
    return get_json_field(field_name)


def load_image_from_request(file_key: str) -> np.ndarray:
    if file_key not in request.files:
        raise ValueError(f"Missing required image: {file_key}")

    file = request.files[file_key]
    pil_image = Image.open(file.stream)
    return pil_to_bgr(pil_image)


def load_pil_image_from_request(file_key: str) -> Image.Image:
    if file_key not in request.files:
        raise ValueError(f"Missing required image: {file_key}")

    image = Image.open(request.files[file_key].stream)
    return image.copy()


def identify_card_safely(image: Image.Image, ocr_regions: dict | None = None) -> dict:
    try:
        return {
            "success": True,
            "card": identify_card(image, ocr_regions=ocr_regions),
        }
    except CardIdentificationDebugError as exc:
        app.logger.info("Card identification debug: %s", exc.debug)
        return {
            "success": False,
            "error": str(exc),
            "debug": exc.debug,
        }
    except CardIdentificationError as exc:
        return {
            "success": False,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
        }


def ratio_off_center_amount(ratio: str) -> int:
    try:
        a, b = ratio.split("/")
        return abs(int(a) - int(b))
    except Exception:
        return 999


def combined_score(front_score: float, back_score: float) -> float:
    return round((float(front_score) + float(back_score)) / 2, 1)


def combined_centering_ratio(front_ratio: str, back_ratio: str) -> str:
    front_off = ratio_off_center_amount(front_ratio)
    back_off = ratio_off_center_amount(back_ratio)

    if front_off == 999 and back_off == 999:
        return "50/50"
    if front_off == 999:
        return back_ratio
    if back_off == 999:
        return front_ratio

    average_off = round((front_off + back_off) / 2)
    smaller = round((100 - average_off) / 2)
    smaller = max(0, min(50, smaller))
    larger = 100 - smaller

    return f"{smaller}/{larger}"


def add_penalties_to_spots(result_dict: dict, finding_type: str) -> dict:
    spots = result_dict.get("spots", [])

    for spot in spots:
        spot["grade_penalty"] = finding_grade_penalty(
            finding_type=finding_type,
            severity=spot.get("severity", "minor"),
            area=int(spot.get("area", 0)),
        )

    return result_dict


def detector_to_dicts(result: dict) -> dict:
    return {
        "edges": add_penalties_to_spots(
            edge_result_to_dict(result["edges"]),
            "edges",
        ),
        "corners": add_penalties_to_spots(
            corner_result_to_dict(result["corners"]),
            "corners",
        ),
        "whitening": add_penalties_to_spots(
            whitening_result_to_dict(result["whitening"]),
            "whitening",
        ),
        "surface": add_penalties_to_spots(
            surface_result_to_dict(result["surface"]),
            "surface",
        ),
    }


def spot_id(side: str, finding_type: str, index: int, spot: dict) -> str:
    return f"{side}:{finding_type}:{index}:{spot.get('x')}:{spot.get('y')}"


def active_spots(
    spots: list,
    side: str,
    finding_type: str,
    ignored_spot_ids: set,
) -> list:
    return [
        spot
        for index, spot in enumerate(spots)
        if spot_id(side, finding_type, index, spot) not in ignored_spot_ids
    ]


def spot_area_total(spots: list) -> int:
    return sum(int(spot.get("area", 0)) for spot in spots)


def strongest_severity(severities: list) -> str:
    if "heavy" in severities:
        return "heavy"
    if "moderate" in severities:
        return "moderate"
    if "minor" in severities:
        return "minor"
    return "clean"


def detector_spot_count(detector: dict) -> int:
    return int(detector.get("spot_count", len(detector.get("spots", []))))


def detector_issue_count(detector: dict) -> int:
    return int(detector.get("issue_count", len(detector.get("spots", []))))


def adjusted_edges_result(detector: dict, side: str, ignored_spot_ids: set) -> dict:
    active = active_spots(detector.get("spots", []), side, "edges", ignored_spot_ids)
    active_by_side = {}

    for spot in active:
        active_by_side.setdefault(spot.get("side"), []).append(spot)

    adjusted_sides = {}

    for side_name, side_result in detector.get("sides", {}).items():
        side_spots = active_by_side.get(side_name, [])
        total_area = spot_area_total(side_spots)
        analyzed_area = int(side_result.get("analyzed_area", 0))

        score = (
            score_edge(len(side_spots), total_area, analyzed_area)
            if analyzed_area > 0
            else float(side_result.get("score", 10.0))
        )

        adjusted_sides[side_name] = {
            "side": side_name,
            "score": score,
            "spot_count": len(side_spots),
            "total_spot_area": total_area,
            "analyzed_area": analyzed_area,
            "severity": classify_edge_severity(score),
        }

    overall_score = round(
        sum(result["score"] for result in adjusted_sides.values()) / len(adjusted_sides),
        1,
    ) if adjusted_sides else float(detector.get("overall_score", 10.0))

    return {
        "overall_score": overall_score,
        "sides": adjusted_sides,
        "spot_count": len(active),
        "severity": strongest_severity(
            [result["severity"] for result in adjusted_sides.values()]
        ),
    }


def adjusted_corners_result(detector: dict, side: str, ignored_spot_ids: set) -> dict:
    active = active_spots(detector.get("spots", []), side, "corners", ignored_spot_ids)
    active_by_corner = {}

    for spot in active:
        active_by_corner.setdefault(spot.get("corner"), []).append(spot)

    adjusted_corners = {}

    for corner_name, corner_result in detector.get("corners", {}).items():
        corner_spots = active_by_corner.get(corner_name, [])
        total_area = spot_area_total(corner_spots)
        analyzed_area = int(corner_result.get("analyzed_area", 0))

        score = (
            score_corner(len(corner_spots), total_area, analyzed_area)
            if analyzed_area > 0
            else float(corner_result.get("score", 10.0))
        )

        adjusted_corners[corner_name] = {
            "corner": corner_name,
            "score": score,
            "spot_count": len(corner_spots),
            "total_spot_area": total_area,
            "analyzed_area": analyzed_area,
            "severity": classify_corner_severity(score),
        }

    overall_score = round(
        sum(result["score"] for result in adjusted_corners.values()) / len(adjusted_corners),
        1,
    ) if adjusted_corners else float(detector.get("overall_score", 10.0))

    return {
        "overall_score": overall_score,
        "corners": adjusted_corners,
        "spot_count": len(active),
        "severity": strongest_severity(
            [result["severity"] for result in adjusted_corners.values()]
        ),
    }


def adjusted_whitening_result(detector: dict, side: str, ignored_spot_ids: set) -> dict:
    active = active_spots(detector.get("spots", []), side, "whitening", ignored_spot_ids)
    total_area = spot_area_total(active)
    analyzed_area = int(detector.get("analyzed_area", 0))

    score = (
        score_whitening(len(active), total_area, analyzed_area)
        if analyzed_area > 0
        else float(detector.get("score", 10.0))
    )

    return {
        "score": score,
        "spot_count": len(active),
        "total_spot_area": total_area,
        "analyzed_area": analyzed_area,
        "severity": classify_whitening_severity(score),
    }


def adjusted_surface_result(detector: dict, side: str, ignored_spot_ids: set) -> dict:
    active = active_spots(detector.get("spots", []), side, "surface", ignored_spot_ids)
    total_area = spot_area_total(active)
    analyzed_area = int(detector.get("analyzed_area", 0))

    score = (
        score_surface(len(active), total_area, analyzed_area)
        if analyzed_area > 0
        else float(detector.get("score", 10.0))
    )

    return {
        "score": score,
        "issue_count": len(active),
        "total_issue_area": total_area,
        "analyzed_area": analyzed_area,
        "severity": classify_surface_severity(score),
    }


def adjusted_side_results(analysis: dict, side: str, ignored_spot_ids: set) -> dict:
    source = analysis.get("back", {}) if side == "back" else analysis

    return {
        "edges": adjusted_edges_result(source.get("edges", {}), side, ignored_spot_ids),
        "corners": adjusted_corners_result(source.get("corners", {}), side, ignored_spot_ids),
        "whitening": adjusted_whitening_result(source.get("whitening", {}), side, ignored_spot_ids),
        "surface": adjusted_surface_result(source.get("surface", {}), side, ignored_spot_ids),
    }


def combined_subgrades_from_sides(
    front: dict,
    back: dict,
    front_centering: dict,
    back_centering: dict,
) -> dict:
    edges_score = combined_score(
        front["edges"]["overall_score"],
        back["edges"]["overall_score"],
    )
    corners_score = combined_score(
        front["corners"]["overall_score"],
        back["corners"]["overall_score"],
    )
    whitening_score = combined_score(
        front["whitening"]["score"],
        back["whitening"]["score"],
    )
    surface_score = combined_score(
        front["surface"]["score"],
        back["surface"]["score"],
    )

    return {
        "centering": {
            "horizontal_ratio": combined_centering_ratio(
                front_centering.get("horizontal_ratio", "50/50"),
                back_centering.get("horizontal_ratio", "50/50"),
            ),
            "vertical_ratio": combined_centering_ratio(
                front_centering.get("vertical_ratio", "50/50"),
                back_centering.get("vertical_ratio", "50/50"),
            ),
        },
        "edges": {
            "overall_score": edges_score,
            "severity": classify_edge_severity(edges_score),
            "spot_count": detector_spot_count(front["edges"])
            + detector_spot_count(back["edges"]),
            "front_score": front["edges"]["overall_score"],
            "back_score": back["edges"]["overall_score"],
        },
        "corners": {
            "overall_score": corners_score,
            "severity": classify_corner_severity(corners_score),
            "spot_count": detector_spot_count(front["corners"])
            + detector_spot_count(back["corners"]),
            "front_score": front["corners"]["overall_score"],
            "back_score": back["corners"]["overall_score"],
        },
        "whitening": {
            "score": whitening_score,
            "severity": classify_whitening_severity(whitening_score),
            "spot_count": int(front["whitening"].get("spot_count", 0))
            + int(back["whitening"].get("spot_count", 0)),
            "front_score": front["whitening"]["score"],
            "back_score": back["whitening"]["score"],
        },
        "surface": {
            "score": surface_score,
            "severity": classify_surface_severity(surface_score),
            "issue_count": detector_issue_count(front["surface"])
            + detector_issue_count(back["surface"]),
            "front_score": front["surface"]["score"],
            "back_score": back["surface"]["score"],
        },
    }


def combined_subgrades_for_single(side_result: dict, centering: dict) -> dict:
    return {
        "centering": {
            "horizontal_ratio": centering.get("horizontal_ratio", "50/50"),
            "vertical_ratio": centering.get("vertical_ratio", "50/50"),
        },
        "edges": {
            "overall_score": side_result["edges"]["overall_score"],
            "severity": classify_edge_severity(side_result["edges"]["overall_score"]),
            "spot_count": detector_spot_count(side_result["edges"]),
        },
        "corners": {
            "overall_score": side_result["corners"]["overall_score"],
            "severity": classify_corner_severity(side_result["corners"]["overall_score"]),
            "spot_count": detector_spot_count(side_result["corners"]),
        },
        "whitening": {
            "score": side_result["whitening"]["score"],
            "severity": classify_whitening_severity(side_result["whitening"]["score"]),
            "spot_count": side_result["whitening"].get("spot_count", 0),
        },
        "surface": {
            "score": side_result["surface"]["score"],
            "severity": classify_surface_severity(side_result["surface"]["score"]),
            "issue_count": detector_issue_count(side_result["surface"]),
        },
    }


def recalculate_with_ignored_spots(analysis: dict, ignored_spot_ids: set) -> dict:
    front = adjusted_side_results(analysis, "front", ignored_spot_ids)
    mode = analysis.get("mode", "single")

    if mode == "front_back" and analysis.get("back"):
        back = adjusted_side_results(analysis, "back", ignored_spot_ids)
        combined = combined_subgrades_from_sides(
            front,
            back,
            analysis.get("centering", {}),
            analysis.get("back_centering", {}),
        )

        final_grade = calculate_final_grade(
            centering_horizontal_ratio=combined["centering"]["horizontal_ratio"],
            centering_vertical_ratio=combined["centering"]["vertical_ratio"],
            edges_score=combined["edges"]["overall_score"],
            corners_score=combined["corners"]["overall_score"],
            whitening_score=combined["whitening"]["score"],
            surface_score=combined["surface"]["score"],
        )

        return {
            "mode": mode,
            "final_grade": final_grade_to_dict(final_grade),
            "combined": combined,
            "front": front,
            "back": back,
        }

    final_grade = calculate_final_grade(
        centering_horizontal_ratio=analysis.get("centering", {}).get("horizontal_ratio", "50/50"),
        centering_vertical_ratio=analysis.get("centering", {}).get("vertical_ratio", "50/50"),
        edges_score=front["edges"]["overall_score"],
        corners_score=front["corners"]["overall_score"],
        whitening_score=front["whitening"]["score"],
        surface_score=front["surface"]["score"],
    )

    return {
        "mode": "single",
        "final_grade": final_grade_to_dict(final_grade),
        "combined": combined_subgrades_for_single(
            front,
            analysis.get("centering", {}),
        ),
        "front": front,
        "back": None,
    }


def analyze_one_side(image_bgr: np.ndarray, manual_lines=None) -> dict:
    centering = analyze_centering(
        image_bgr,
        manual_lines=manual_lines,
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
    back_surface = back_result["surface"]

    combined_centering_horizontal = combined_centering_ratio(
        front_centering.horizontal_ratio,
        back_centering.horizontal_ratio,
    )

    combined_centering_vertical = combined_centering_ratio(
        front_centering.vertical_ratio,
        back_centering.vertical_ratio,
    )

    combined_edges_score = combined_score(
        front_edges.overall_score,
        back_edges.overall_score,
    )

    combined_corners_score = combined_score(
        front_corners.overall_score,
        back_corners.overall_score,
    )

    combined_whitening_score = combined_score(
        front_whitening.score,
        back_whitening.score,
    )

    combined_surface_score = combined_score(
        front_surface.score,
        back_surface.score,
    )

    return calculate_final_grade(
        centering_horizontal_ratio=combined_centering_horizontal,
        centering_vertical_ratio=combined_centering_vertical,
        edges_score=combined_edges_score,
        corners_score=combined_corners_score,
        whitening_score=combined_whitening_score,
        surface_score=combined_surface_score,
    )


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/corrections/recalculate", methods=["POST"])
@app.route("/api/corrections/recalculate", methods=["POST"])
def recalculate_corrections_route():
    try:
        data = request.get_json(silent=True) or {}
        analysis = data.get("analysis")

        if not isinstance(analysis, dict):
            return jsonify({"error": "Missing analysis payload."}), 400

        ignored_spot_ids = set(data.get("ignored_spot_ids") or [])
        return jsonify(recalculate_with_ignored_spots(analysis, ignored_spot_ids))

    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/identify", methods=["POST"])
def identify_card_route():
    if "image" not in request.files:
        return jsonify({
            "success": False,
            "error": "No image uploaded.",
        }), 400

    try:
        image = Image.open(request.files["image"].stream)
        ocr_regions = get_json_form_field("ocr_regions")
        card = identify_card(image, ocr_regions=ocr_regions)

        return jsonify({
            "success": True,
            "card": card,
        })

    except CardIdentificationDebugError as exc:
        message = str(exc)
        status_code = 404 if message == "No matching card found" else 400
        app.logger.info("Card identification debug: %s", exc.debug)

        return jsonify({
            "success": False,
            "error": message,
            "debug": exc.debug,
        }), status_code

    except CardIdentificationError as exc:
        message = str(exc)
        status_code = 404 if message == "No matching card found" else 400

        return jsonify({
            "success": False,
            "error": message,
        }), status_code

    except Exception as exc:
        return jsonify({
            "success": False,
            "error": str(exc),
        }), 500


@app.route("/api/analyze/full", methods=["POST"])
def analyze_full_route():
    try:
        front_manual_lines = get_json_field("front_manual_lines")
        back_manual_lines = get_json_field("back_manual_lines")
        ocr_regions = get_json_field("ocr_regions")

        old_manual_lines = get_json_field("manual_lines")
        if old_manual_lines and not front_manual_lines:
            front_manual_lines = old_manual_lines

        if "front_image" in request.files and "back_image" in request.files:
            front_image = load_pil_image_from_request("front_image")
            back_image = load_pil_image_from_request("back_image")
            identification = identify_card_safely(front_image, ocr_regions=ocr_regions)
            front_bgr = pil_to_bgr(front_image)
            back_bgr = pil_to_bgr(back_image)

            front = analyze_one_side(front_bgr, manual_lines=front_manual_lines)
            back = analyze_one_side(back_bgr, manual_lines=back_manual_lines)

            front_dicts = detector_to_dicts(front)
            back_dicts = detector_to_dicts(back)

            final_grade = combine_side_scores(front, back)
            front_centering_dict = {
                "borders": {
                    "left": front["centering"].borders.left,
                    "right": front["centering"].borders.right,
                    "top": front["centering"].borders.top,
                    "bottom": front["centering"].borders.bottom,
                },
                "horizontal_ratio": front["centering"].horizontal_ratio,
                "vertical_ratio": front["centering"].vertical_ratio,
                "confidence_note": front["centering"].confidence_note,
            }
            back_centering_dict = {
                "borders": {
                    "left": back["centering"].borders.left,
                    "right": back["centering"].borders.right,
                    "top": back["centering"].borders.top,
                    "bottom": back["centering"].borders.bottom,
                },
                "horizontal_ratio": back["centering"].horizontal_ratio,
                "vertical_ratio": back["centering"].vertical_ratio,
                "confidence_note": back["centering"].confidence_note,
            }
            combined = combined_subgrades_from_sides(
                front_dicts,
                back_dicts,
                front_centering_dict,
                back_centering_dict,
            )

            response = {
                "mode": "front_back",
                "final_grade": final_grade_to_dict(final_grade),
                "identification": identification,
                "combined": combined,
                "centering": front_centering_dict,
                "back_centering": back_centering_dict,
                "regions": {
                    "front": regions_to_dict(front["regions"]) if front["regions"] else None,
                    "back": regions_to_dict(back["regions"]) if back["regions"] else None,
                },
                "edges": front_dicts["edges"],
                "corners": front_dicts["corners"],
                "whitening": front_dicts["whitening"],
                "surface": front_dicts["surface"],
                "back": {
                    "edges": back_dicts["edges"],
                    "corners": back_dicts["corners"],
                    "whitening": back_dicts["whitening"],
                    "surface": back_dicts["surface"],
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
            image = load_pil_image_from_request("image")
            identification = identify_card_safely(image, ocr_regions=ocr_regions)
            image_bgr = pil_to_bgr(image)
            result = analyze_one_side(image_bgr, manual_lines=front_manual_lines)
            result_dicts = detector_to_dicts(result)

            final_grade = calculate_final_grade(
                centering_horizontal_ratio=result["centering"].horizontal_ratio,
                centering_vertical_ratio=result["centering"].vertical_ratio,
                edges_score=result["edges"].overall_score,
                corners_score=result["corners"].overall_score,
                whitening_score=result["whitening"].score,
                surface_score=result["surface"].score,
            )
            centering_dict = {
                "borders": {
                    "left": result["centering"].borders.left,
                    "right": result["centering"].borders.right,
                    "top": result["centering"].borders.top,
                    "bottom": result["centering"].borders.bottom,
                },
                "horizontal_ratio": result["centering"].horizontal_ratio,
                "vertical_ratio": result["centering"].vertical_ratio,
                "confidence_note": result["centering"].confidence_note,
            }

            response = {
                "mode": "single",
                "final_grade": final_grade_to_dict(final_grade),
                "identification": identification,
                "combined": combined_subgrades_for_single(result_dicts, centering_dict),
                "centering": centering_dict,
                "regions": regions_to_dict(result["regions"]) if result["regions"] else None,
                "edges": result_dicts["edges"],
                "corners": result_dicts["corners"],
                "whitening": result_dicts["whitening"],
                "surface": result_dicts["surface"],
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


@app.route("/api/analyze/centering", methods=["POST"])
def analyze_centering_route():
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded."}), 400

    try:
        image_bgr = load_image_from_request("image")
        manual_lines = get_json_field("manual_lines")

        centering = analyze_centering(
            image_bgr,
            manual_lines=manual_lines,
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
