export function updateEdgesUI(data) {
    const edges = data?.combined?.edges || data?.edges;
    if (!edges) return;

    document.getElementById("edges-score").textContent = edges.overall_score;
    document.getElementById("edges-severity").textContent =
        edges.severity || summarizeSeverity(edges.sides);
}


export function resetEdgesUI() {
    const ids = ["edges-score", "edges-severity"];

    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = "-";
    });
}


function summarizeSeverity(sides) {
    if (!sides) return "-";

    const values = Object.values(sides).map(side => side.severity);

    if (values.includes("heavy")) return "heavy";
    if (values.includes("moderate")) return "moderate";
    if (values.includes("minor")) return "minor";
    return "clean";
}
