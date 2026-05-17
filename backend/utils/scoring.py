from dataclasses import dataclass, asdict
from typing import Dict


@dataclass
class FinalGradeResult:
    final_grade: float
    grade_label: str
    grade_bucket: str
    subgrades: Dict[str, float]
    weights: Dict[str, float]
    summary: str


def score_centering(horizontal_ratio: str, vertical_ratio: str) -> float:
    """
    Converts centering ratios like '45/55' into a 1-10 score.
    Perfect is 50/50.
    """
    def ratio_penalty(ratio: str) -> float:
        try:
            left, right = ratio.split("/")
            a = int(left)
            b = int(right)
            off_by = abs(a - b)
            return off_by
        except Exception:
            return 20

    h_penalty = ratio_penalty(horizontal_ratio)
    v_penalty = ratio_penalty(vertical_ratio)

    total_penalty = (h_penalty * 0.6) + (v_penalty * 0.4)

    score = 10 - (total_penalty * 0.12)
    return round(max(1.0, min(10.0, score)), 1)


def label_grade(score: float) -> tuple[str, str]:
    if score >= 9.5:
        return "Gem Mint", "10"
    if score >= 9.0:
        return "Mint", "9"
    if score >= 8.0:
        return "Near Mint-Mint", "8"
    if score >= 7.0:
        return "Near Mint", "7"
    if score >= 6.0:
        return "Excellent-Mint", "6"
    if score >= 5.0:
        return "Excellent", "5"
    if score >= 4.0:
        return "Very Good-Excellent", "4"
    if score >= 3.0:
        return "Very Good", "3"
    if score >= 2.0:
        return "Good", "2"
    return "Poor-Fair", "1"


def build_grade_summary(final_grade: float, subgrades: Dict[str, float]) -> str:
    weakest = min(subgrades, key=subgrades.get)
    strongest = max(subgrades, key=subgrades.get)

    return (
        f"Estimated grade is {final_grade}. "
        f"Strongest category: {strongest} ({subgrades[strongest]}). "
        f"Weakest category: {weakest} ({subgrades[weakest]})."
    )


def calculate_final_grade(
    centering_horizontal_ratio: str,
    centering_vertical_ratio: str,
    edges_score: float,
    corners_score: float,
    whitening_score: float,
    surface_score: float,
) -> FinalGradeResult:
    """
    Produces an estimated collector-style grade.

    This is not an official PSA/BGS/CGC grade.
    It is a local heuristic estimate based on detected visual signals.
    """

    centering_score = score_centering(
        centering_horizontal_ratio,
        centering_vertical_ratio,
    )

    subgrades = {
        "centering": centering_score,
        "edges": float(edges_score),
        "corners": float(corners_score),
        "whitening": float(whitening_score),
        "surface": float(surface_score),
    }

    weights = {
        "centering": 0.20,
        "edges": 0.20,
        "corners": 0.25,
        "whitening": 0.15,
        "surface": 0.20,
    }

    weighted_score = sum(
        subgrades[key] * weights[key]
        for key in subgrades
    )

    # Penalize heavily if one category is much weaker.
    weakest_score = min(subgrades.values())
    if weakest_score < 6.5:
        weighted_score = min(weighted_score, weakest_score + 1.0)
    elif weakest_score < 8.0:
        weighted_score = min(weighted_score, weakest_score + 1.3)
    elif weakest_score < 9.0:
        weighted_score = min(weighted_score, weakest_score + 1.5)

    final_grade = round(max(1.0, min(10.0, weighted_score)), 1)
    grade_label, grade_bucket = label_grade(final_grade)

    return FinalGradeResult(
        final_grade=final_grade,
        grade_label=grade_label,
        grade_bucket=grade_bucket,
        subgrades=subgrades,
        weights=weights,
        summary=build_grade_summary(final_grade, subgrades),
    )


def final_grade_to_dict(result: FinalGradeResult) -> dict:
    return asdict(result)