export function updateCenteringUI(data) {
    if (!data || !data.centering) return;

    const borders = data.centering.borders;
    const combinedCentering = data.combined?.centering || data.centering;

    document.getElementById("left").textContent = borders.left;
    document.getElementById("right").textContent = borders.right;
    document.getElementById("top").textContent = borders.top;
    document.getElementById("bottom").textContent = borders.bottom;

    document.getElementById("horizontal-ratio").textContent = combinedCentering.horizontal_ratio;
    document.getElementById("vertical-ratio").textContent = combinedCentering.vertical_ratio;
}


export function resetCenteringUI() {
    const ids = [
        "left",
        "right",
        "top",
        "bottom",
        "horizontal-ratio",
        "vertical-ratio"
    ];

    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = "-";
    });
}
