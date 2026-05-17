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

    // Centering
    document.getElementById("horizontal-ratio").textContent = data.centering.horizontal_ratio;
    document.getElementById("vertical-ratio").textContent = data.centering.vertical_ratio;

    // Edges
    document.getElementById("edges-score").textContent = data.edges.overall_score;
    document.getElementById("edges-severity").textContent = summarizeSeverity(data.edges.sides);

    // Corners
    document.getElementById("corners-score").textContent = data.corners.overall_score;
    document.getElementById("corners-severity").textContent = summarizeSeverity(data.corners.corners);

    // Whitening
    document.getElementById("whitening-score").textContent = data.whitening.score;
    document.getElementById("whitening-spots").textContent = data.whitening.spot_count;

    // Surface
    document.getElementById("surface-score").textContent = data.surface.score;
    document.getElementById("surface-defects").textContent = data.surface.defect_count;
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