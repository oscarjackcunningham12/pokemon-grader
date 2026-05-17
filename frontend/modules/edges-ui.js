export function updateEdgesUI(data) {
    if (!data || !data.edges) return;

    document.getElementById("edges-score").textContent = data.edges.overall_score;
    document.getElementById("edges-severity").textContent = summarizeSeverity(data.edges.sides);
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