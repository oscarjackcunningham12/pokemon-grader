from datetime import datetime


def build_report_summary(full_result: dict) -> dict:
    """
    Builds a clean report object from the full grading response.
    This is useful for future export/download features.
    """

    final_grade = full_result.get("final_grade", {})
    centering = full_result.get("centering", {})
    edges = full_result.get("edges", {})
    corners = full_result.get("corners", {})
    whitening = full_result.get("whitening", {})
    surface = full_result.get("surface", {})

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "final_grade": {
            "score": final_grade.get("final_grade"),
            "label": final_grade.get("grade_label"),
            "bucket": final_grade.get("grade_bucket"),
            "summary": final_grade.get("summary"),
        },
        "subgrades": final_grade.get("subgrades", {}),
        "centering": {
            "horizontal_ratio": centering.get("horizontal_ratio"),
            "vertical_ratio": centering.get("vertical_ratio"),
            "borders": centering.get("borders", {}),
        },
        "condition": {
            "edges": {
                "score": edges.get("overall_score"),
                "sides": edges.get("sides", {}),
                "spot_count": len(edges.get("spots", [])),
            },
            "corners": {
                "score": corners.get("overall_score"),
                "corners": corners.get("corners", {}),
                "spot_count": len(corners.get("spots", [])),
            },
            "whitening": {
                "score": whitening.get("score"),
                "severity": whitening.get("severity"),
                "spot_count": whitening.get("spot_count"),
                "total_spot_area": whitening.get("total_spot_area"),
            },
            "surface": {
                "score": surface.get("score"),
                "severity": surface.get("severity"),
                "defect_count": surface.get("defect_count"),
                "total_defect_area": surface.get("total_defect_area"),
            },
        },
    }