export function updateCornersUI(data) {
    const corners = data?.combined?.corners || data?.corners;
    if (!corners) return;

    document.getElementById("corners-score").textContent = corners.overall_score;
    document.getElementById("corners-severity").textContent =
        corners.severity || summarizeSeverity(corners.corners);
}


export function resetCornersUI() {
    const ids = ["corners-score", "corners-severity"];

    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = "-";
    });
}


function summarizeSeverity(corners) {
    if (!corners) return "-";

    const values = Object.values(corners).map(corner => corner.severity);

    if (values.includes("heavy")) return "heavy";
    if (values.includes("moderate")) return "moderate";
    if (values.includes("minor")) return "minor";
    return "clean";
}
