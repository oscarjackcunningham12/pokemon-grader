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
    setScoreBar("horizontal-score-bar", getRatioScore(centering.horizontal_ratio));
    setScoreBar("vertical-score-bar", getRatioScore(centering.vertical_ratio));

    // Edges
    document.getElementById("edges-score").textContent = summary.edges.overall_score;
    document.getElementById("edges-severity").textContent =
        summary.edges.severity || summarizeSeverity(summary.edges.sides);
    setScoreBar("edges-score-bar", summary.edges.overall_score);

    // Corners
    document.getElementById("corners-score").textContent = summary.corners.overall_score;
    document.getElementById("corners-severity").textContent =
        summary.corners.severity || summarizeSeverity(summary.corners.corners);
    setScoreBar("corners-score-bar", summary.corners.overall_score);

    // Whitening
    document.getElementById("whitening-score").textContent = summary.whitening.score;
    document.getElementById("whitening-spots").textContent = summary.whitening.spot_count;
    setScoreBar("whitening-score-bar", summary.whitening.score);

    // Surface
    document.getElementById("surface-score").textContent = summary.surface.score;
    document.getElementById("surface-defects").textContent = summary.surface.issue_count;
    setScoreBar("surface-score-bar", summary.surface.score);
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

    [
        "horizontal-score-bar",
        "vertical-score-bar",
        "edges-score-bar",
        "corners-score-bar",
        "whitening-score-bar",
        "surface-score-bar"
    ].forEach(id => setScoreBar(id, null));
}


function summarizeSeverity(items) {
    if (!items) return "-";

    const values = Object.values(items).map(item => item.severity);

    if (values.includes("heavy")) return "heavy";
    if (values.includes("moderate")) return "moderate";
    if (values.includes("minor")) return "minor";
    return "clean";
}


export function setScoreBar(id, rawValue) {
    const bar = document.getElementById(id);
    const value = Number(rawValue);

    if (!bar || !Number.isFinite(value)) {
        if (bar) {
            bar.style.width = "0%";
            bar.classList.remove("good", "mid", "bad");
        }

        return;
    }

    const score = Math.max(0, Math.min(10, value));

    bar.style.width = `${score * 10}%`;
    bar.classList.remove("good", "mid", "bad");

    if (score >= 8) {
        bar.classList.add("good");
    } else if (score >= 5) {
        bar.classList.add("mid");
    } else {
        bar.classList.add("bad");
    }
}


function getRatioScore(rawRatio) {
    if (typeof rawRatio === "number") {
        return rawRatio;
    }

    const ratioText = String(rawRatio || "");
    const numbers = ratioText.match(/\d+(\.\d+)?/g)?.map(Number);

    if (!numbers || numbers.length < 2) return null;

    const lowerSide = Math.min(numbers[0], numbers[1]);
    const higherSide = Math.max(numbers[0], numbers[1]);

    if (!higherSide) return null;

    return (lowerSide / higherSide) * 10;
}
