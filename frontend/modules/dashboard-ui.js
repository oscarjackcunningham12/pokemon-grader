export function updateFinalGradeUI(data) {
    const finalGrade = document.getElementById("final-grade");
    const gradeLabel = document.getElementById("grade-label");
    const gradeSummary = document.getElementById("grade-summary");

    if (!data || !data.final_grade) return;

    finalGrade.textContent = data.final_grade.final_grade;
    gradeLabel.textContent = `${data.final_grade.grade_label} (${data.final_grade.grade_bucket})`;
    gradeSummary.textContent = data.final_grade.summary;
}


export function updateScoreCardsUI(data) {
    if (!data) return;

    const summary = data.combined || data;
    const centering = summary.centering || data.centering;

    // Centering
    document.getElementById("horizontal-ratio").textContent = centering.horizontal_ratio;
    document.getElementById("vertical-ratio").textContent = centering.vertical_ratio;

    // Edges
    document.getElementById("edges-score").textContent = summary.edges.overall_score;
    document.getElementById("edges-severity").textContent =
        summary.edges.severity || summarizeSeverity(summary.edges.sides);

    // Corners
    document.getElementById("corners-score").textContent = summary.corners.overall_score;
    document.getElementById("corners-severity").textContent =
        summary.corners.severity || summarizeSeverity(summary.corners.corners);

    // Whitening
    document.getElementById("whitening-score").textContent = summary.whitening.score;
    document.getElementById("whitening-spots").textContent = summary.whitening.spot_count;

    // Surface
    document.getElementById("surface-score").textContent = summary.surface.score;
    document.getElementById("surface-defects").textContent = summary.surface.issue_count;
}


export function resetDashboardUI() {
    const fields = [
        "horizontal-ratio",
        "vertical-ratio",
        "edges-score",
        "edges-severity",
        "corners-score",
        "corners-severity",
        "whitening-score",
        "whitening-spots",
        "surface-score",
        "surface-defects",
        "final-grade",
        "grade-label",
        "grade-summary"
    ];

    fields.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;

        if (id === "grade-summary") {
            el.textContent = "Upload a card to generate an estimate.";
        } else {
            el.textContent = "-";
        }
    });
}


function summarizeSeverity(items) {
    if (!items) return "-";

    const values = Object.values(items).map(item => item.severity);

    if (values.includes("heavy")) return "heavy";
    if (values.includes("moderate")) return "moderate";
    if (values.includes("minor")) return "minor";
    return "clean";
}
