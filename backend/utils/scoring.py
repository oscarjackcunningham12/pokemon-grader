from dataclasses import dataclass


@dataclass
class FinalGradeResult:
    final_grade: float
    grade_label: str
    grade_bucket: str
    summary: str


def parse_ratio(ratio: str) -> tuple[int, int]:
    try:
        left, right = ratio.split("/")
        return int(left), int(right)
    except Exception:
        return 50, 50


def centering_penalty(horizontal_ratio: str, vertical_ratio: str) -> float:
    h1, h2 = parse_ratio(horizontal_ratio)
    v1, v2 = parse_ratio(vertical_ratio)

    h_off = abs(h1 - h2)
    v_off = abs(v1 - v2)

    penalty = 0

    penalty += max(0, h_off - 5) * 0.045
    penalty += max(0, v_off - 5) * 0.045

    return min(penalty, 1.25)


def detector_penalty(score: float, weight: float) -> float:
    """
    Converts a detector score into a grade penalty.

    Example:
    detector score 9.0 with weight 0.6 = small penalty
    detector score 5.0 with weight 0.6 = larger penalty

    This is intentionally softer so one small defect does not crush the grade.
    """
    score = max(1.0, min(10.0, float(score)))
    quality_loss = 10.0 - score

    return quality_loss * weight


def calculate_final_grade(
    centering_horizontal_ratio: str,
    centering_vertical_ratio: str,
    edges_score: float,
    corners_score: float,
    whitening_score: float,
    surface_score: float,
) -> FinalGradeResult:
    grade = 10.0

    grade -= centering_penalty(
        centering_horizontal_ratio,
        centering_vertical_ratio,
    )

    grade -= detector_penalty(edges_score, 0.18)
    grade -= detector_penalty(corners_score, 0.22)
    grade -= detector_penalty(whitening_score, 0.18)
    grade -= detector_penalty(surface_score, 0.14)

    grade = round(max(1.0, min(10.0, grade)), 1)

    return FinalGradeResult(
        final_grade=grade,
        grade_label=grade_to_label(grade),
        grade_bucket=grade_to_bucket(grade),
        summary=grade_summary(grade),
    )


def grade_to_label(grade: float) -> str:
    if grade >= 9.5:
        return "Gem Mint"
    if grade >= 9.0:
        return "Mint"
    if grade >= 8.0:
        return "Near Mint-Mint"
    if grade >= 7.0:
        return "Near Mint"
    if grade >= 6.0:
        return "Excellent-Mint"
    if grade >= 5.0:
        return "Excellent"
    if grade >= 4.0:
        return "Very Good-Excellent"
    if grade >= 3.0:
        return "Very Good"
    if grade >= 2.0:
        return "Good"
    return "Poor"


def grade_to_bucket(grade: float) -> str:
    if grade >= 9.5:
        return "Premium"
    if grade >= 8.0:
        return "High Grade"
    if grade >= 6.0:
        return "Mid Grade"
    if grade >= 4.0:
        return "Lower Grade"
    return "Heavily Played"


def grade_summary(grade: float) -> str:
    if grade >= 9.5:
        return "Strong condition with excellent centering and minimal visible flaws."
    if grade >= 9.0:
        return "Very strong condition with only minor flaws detected."
    if grade >= 8.0:
        return "Good condition with some visible imperfections."
    if grade >= 7.0:
        return "Moderate flaws detected, but still a solid-looking card."
    if grade >= 6.0:
        return "Noticeable condition issues were detected."
    if grade >= 4.0:
        return "Multiple visible flaws were detected across the card."
    return "Heavy wear or major flaws were detected."


def final_grade_to_dict(result: FinalGradeResult) -> dict:
    return {
        "final_grade": result.final_grade,
        "grade_label": result.grade_label,
        "grade_bucket": result.grade_bucket,
        "summary": result.summary,
    }