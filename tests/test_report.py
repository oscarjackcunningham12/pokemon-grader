from backend.utils.report import build_report_summary


def test_report_summary_uses_combined_subgrades_when_final_grade_has_none():
    full_result = {
        "final_grade": {
            "final_grade": 8.5,
            "grade_label": "Near Mint",
            "grade_bucket": "NM",
            "summary": "Good condition with some visible imperfections.",
        },
        "combined": {
            "centering": {
                "horizontal_ratio": "45/55",
                "vertical_ratio": "50/50",
            },
            "edges": {
                "overall_score": 9.0,
                "severity": "minor",
                "spot_count": 1,
            },
            "corners": {
                "overall_score": 8.0,
                "severity": "minor",
                "spot_count": 2,
            },
            "whitening": {
                "score": 9.5,
                "severity": "clean",
                "spot_count": 0,
            },
            "surface": {
                "score": 8.5,
                "severity": "minor",
                "issue_count": 1,
            },
        },
    }

    report = build_report_summary(full_result)

    assert report["subgrades"] == full_result["combined"]


def test_report_summary_keeps_legacy_final_grade_subgrades_when_present():
    full_result = {
        "final_grade": {
            "final_grade": 9.0,
            "subgrades": {
                "edges": {
                    "overall_score": 9.0,
                },
            },
        },
        "combined": {
            "edges": {
                "overall_score": 6.0,
            },
        },
    }

    report = build_report_summary(full_result)

    assert report["subgrades"] == full_result["final_grade"]["subgrades"]
