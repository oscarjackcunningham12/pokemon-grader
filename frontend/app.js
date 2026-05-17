import {
    initManualCenteringCanvas,
    loadManualCenteringImage,
    getManualCenteringLines
} from "./modules/manual-centering-ui.js";

import {
    setStatus,
    clearImages,
    setBaseImages
} from "./modules/upload-ui.js";

import {
    updateFinalGradeUI,
    updateScoreCardsUI,
    resetDashboardUI
} from "./modules/dashboard-ui.js";

import {
    updateCenteringUI,
    resetCenteringUI
} from "./modules/centering-ui.js";

import {
    updateEdgesUI,
    resetEdgesUI
} from "./modules/edges-ui.js";

import {
    updateCornersUI,
    resetCornersUI
} from "./modules/corners-ui.js";


const frontUpload = document.getElementById("front-upload");
const backUpload = document.getElementById("back-upload");
const analyzeButton = document.getElementById("analyze-button");

const overlayImage = document.getElementById("overlay-image");
const overlayTitle = document.getElementById("overlay-title");
const overlayButtons = document.querySelectorAll("[data-overlay]");
const correctionCanvas = document.getElementById("correction-canvas");
const correctionCtx = correctionCanvas ? correctionCanvas.getContext("2d") : null;

let baseGrade = null;

let latestImages = null;
let latestData = null;

let frontFile = null;
let backFile = null;

let currentOverlayKey = "centering_overlay";
let ignoredSpots = [];


const overlayLabels = {
    centering_overlay: "Front Centering Overlay",
    regions_overlay: "Front Grading Regions Overlay",
    edges_overlay: "Front Edges Overlay",
    corners_overlay: "Front Corners Overlay",
    whitening_overlay: "Front Whitening Overlay",
    surface_overlay: "Front Surface Overlay",

    back_card: "Back Card",
    back_centering_overlay: "Back Centering Overlay",
    back_regions_overlay: "Back Grading Regions Overlay",
    back_edges_overlay: "Back Edges Overlay",
    back_corners_overlay: "Back Corners Overlay",
    back_whitening_overlay: "Back Whitening Overlay",
    back_surface_overlay: "Back Surface Overlay"
};


function resetAllUI() {
    clearImages();
    resetDashboardUI();
    resetCenteringUI();
    resetEdgesUI();
    resetCornersUI();

    latestImages = null;
    latestData = null;
    ignoredSpots = [];
    currentOverlayKey = "centering_overlay";

    if (overlayTitle) {
        overlayTitle.textContent = "Front Centering Overlay";
    }

    overlayButtons.forEach(button => {
        button.classList.toggle(
            "active",
            button.dataset.overlay === "centering_overlay"
        );
    });
}


function updateAnalyzeButtonState() {
    if (!analyzeButton) return;

    analyzeButton.disabled = !(frontFile && backFile);
}


function setOverlay(overlayKey) {
    if (!latestImages || !latestImages[overlayKey]) return;

    currentOverlayKey = overlayKey;

    overlayImage.onload = () => {
        syncCorrectionCanvas();
    };

    overlayImage.src = `data:image/png;base64,${latestImages[overlayKey]}`;

    if (overlayTitle) {
        overlayTitle.textContent = overlayLabels[overlayKey] || "Overlay";
    }

    overlayButtons.forEach(button => {
        button.classList.toggle("active", button.dataset.overlay === overlayKey);
    });
}



function getFileFromInput(event) {
    return event.target.files[0] || null;
}


function getCurrentSpotSource() {
    if (!latestData) return null;

    const sourceMap = {
        edges_overlay: {
            side: "front",
            type: "edges",
            spots: latestData.edges?.spots || []
        },
        corners_overlay: {
            side: "front",
            type: "corners",
            spots: latestData.corners?.spots || []
        },
        whitening_overlay: {
            side: "front",
            type: "whitening",
            spots: latestData.whitening?.spots || []
        },
        surface_overlay: {
            side: "front",
            type: "surface",
            spots: latestData.surface?.spots || []
        },

        back_edges_overlay: {
            side: "back",
            type: "edges",
            spots: latestData.back?.edges?.spots || []
        },
        back_corners_overlay: {
            side: "back",
            type: "corners",
            spots: latestData.back?.corners?.spots || []
        },
        back_whitening_overlay: {
            side: "back",
            type: "whitening",
            spots: latestData.back?.whitening?.spots || []
        },
        back_surface_overlay: {
            side: "back",
            type: "surface",
            spots: latestData.back?.surface?.spots || []
        }
    };

    return sourceMap[currentOverlayKey] || null;
}


function getSpotBox(spot) {
    const width = spot.width || 14;
    const height = spot.height || 14;

    return {
        x: spot.x,
        y: spot.y,
        width,
        height
    };
}


function getImageClickPosition(event) {
    const rect = overlayImage.getBoundingClientRect();

    const naturalWidth = overlayImage.naturalWidth;
    const naturalHeight = overlayImage.naturalHeight;

    const scaleX = naturalWidth / rect.width;
    const scaleY = naturalHeight / rect.height;

    return {
        x: (event.clientX - rect.left) * scaleX,
        y: (event.clientY - rect.top) * scaleY
    };
}


function getSpotId(source, spot, index) {
    return `${source.side}:${source.type}:${index}:${spot.x}:${spot.y}`;
}


function isIgnored(spotId) {
    return ignoredSpots.includes(spotId);
}


function findClickedSpot(x, y, source) {
    if (!source) return null;

    for (let i = source.spots.length - 1; i >= 0; i--) {
        const spot = source.spots[i];
        const id = getSpotId(source, spot, i);

        if (isIgnored(id)) continue;

        const box = getSpotBox(spot);

        if (
            x >= box.x &&
            x <= box.x + box.width &&
            y >= box.y &&
            y <= box.y + box.height
        ) {
            return {
                spot,
                index: i,
                id
            };
        }
    }

    return null;
}


function estimateSpotImpact(source, spot) {
    const severityImpact = {
        minor: 0.05,
        moderate: 0.15,
        heavy: 0.35,
        clean: 0
    };

    const typeMultiplier = {
        edges: 1.0,
        corners: 1.15,
        whitening: 0.9,
        surface: 0.75
    };

    const area = spot.area || 0;
    const areaImpact = Math.min(area / 500, 0.35);

    const severity = spot.severity || "minor";

    const impact =
        (severityImpact[severity] || 0.08) *
        (typeMultiplier[source.type] || 1) +
        areaImpact;

    return Math.round(impact * 100) / 100;
}


function showSpotDetails(source, clicked) {
    const spot = clicked.spot;
    const impact = estimateSpotImpact(source, spot);

    const message = [
        `${source.side.toUpperCase()} ${source.type.toUpperCase()} finding`,
        `Severity: ${spot.severity || "unknown"}`,
        `Area: ${spot.area || "unknown"} px`,
        `Estimated grade impact: -${impact}`,
        "",
        "Shift-click this box to ignore it as a false positive."
    ].join("\n");

    alert(message);
}


function ignoreSpot(spotId) {
    if (!ignoredSpots.includes(spotId)) {
        ignoredSpots.push(spotId);
    }

    drawIgnoredSpotMarkers();
    recalculateDisplayedGrade();

    setStatus("Finding ignored visually and grade estimate adjusted.");
}


function handleOverlayClick(event) {
    if (!latestData || !overlayImage || !overlayImage.src) return;

    const source = getCurrentSpotSource();

    if (!source) {
        setStatus("This overlay does not have clickable findings.");
        return;
    }

    const pos = getImageClickPosition(event);
    const clicked = findClickedSpot(pos.x, pos.y, source);

    if (!clicked) {
        setStatus("No finding selected.");
        return;
    }

    if (event.shiftKey) {
        ignoreSpot(clicked.id);
        return;
    }

    showSpotDetails(source, clicked);
}


overlayButtons.forEach(button => {
    button.addEventListener("click", () => {
        setOverlay(button.dataset.overlay);
    });
});


if (overlayImage) {
    overlayImage.addEventListener("click", handleOverlayClick);
}


initManualCenteringCanvas();
resetAllUI();
updateAnalyzeButtonState();


frontUpload.addEventListener("change", (event) => {
    const file = getFileFromInput(event);

    if (!file) return;

    frontFile = file;

    resetAllUI();
    loadManualCenteringImage(file, "front");

    setStatus("Front image loaded. Adjust the front guide lines, then upload the back image.");
    updateAnalyzeButtonState();
});


backUpload.addEventListener("change", (event) => {
    const file = getFileFromInput(event);

    if (!file) return;

    backFile = file;

    loadManualCenteringImage(file, "back");

    setStatus("Back image loaded. Adjust the back guide lines, then click Analyze Card.");
    updateAnalyzeButtonState();
});


analyzeButton.addEventListener("click", async () => {
    if (!frontFile || !backFile) {
        setStatus("Upload both the front and back images first.");
        return;
    }

    resetAllUI();
    setStatus("Processing front and back grading analysis...");

    const formData = new FormData();

    formData.append("front_image", frontFile);
    formData.append("back_image", backFile);

    formData.append(
        "front_manual_lines",
        JSON.stringify(getManualCenteringLines("front"))
    );

    formData.append(
        "back_manual_lines",
        JSON.stringify(getManualCenteringLines("back"))
    );

    try {
        const response = await fetch("http://127.0.0.1:5000/analyze/full", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (data.error) {
            setStatus(`Error: ${data.error}`);
            return;
        }

        setStatus("Done. Click a finding box for details. Shift-click to ignore visually.");

        latestData = data;
        baseGrade = data.final_grade.final_grade;
        latestImages = data.images;

        setBaseImages(data.images);
        setOverlay("centering_overlay");

        updateFinalGradeUI(data);
        updateScoreCardsUI(data);
        updateCenteringUI(data);
        updateEdgesUI(data);
        updateCornersUI(data);

        console.log("Full grading result:", data);

    } catch (error) {
        console.error(error);
        setStatus("Could not connect to backend. Make sure Flask is running.");
    }
});

function syncCorrectionCanvas() {
    if (!correctionCanvas || !overlayImage) return;

    const rect = overlayImage.getBoundingClientRect();

    correctionCanvas.width = rect.width;
    correctionCanvas.height = rect.height;
    correctionCanvas.style.width = `${rect.width}px`;
    correctionCanvas.style.height = `${rect.height}px`;

    drawIgnoredSpotMarkers();
}


function drawIgnoredSpotMarkers() {
    if (!correctionCtx || !correctionCanvas || !overlayImage) return;

    correctionCtx.clearRect(0, 0, correctionCanvas.width, correctionCanvas.height);

    const source = getCurrentSpotSource();
    if (!source) return;

    const rect = overlayImage.getBoundingClientRect();
    const scaleX = rect.width / overlayImage.naturalWidth;
    const scaleY = rect.height / overlayImage.naturalHeight;

    source.spots.forEach((spot, index) => {
        const id = getSpotId(source, spot, index);
        if (!isIgnored(id)) return;

        const box = getSpotBox(spot);

        const x = box.x * scaleX;
        const y = box.y * scaleY;
        const w = box.width * scaleX;
        const h = box.height * scaleY;

        correctionCtx.fillStyle = "rgba(255,255,255,0.65)";
        correctionCtx.fillRect(x, y, w, h);

        correctionCtx.strokeStyle = "#ef4444";
        correctionCtx.lineWidth = 3;
        correctionCtx.strokeRect(x, y, w, h);

        correctionCtx.beginPath();
        correctionCtx.moveTo(x, y);
        correctionCtx.lineTo(x + w, y + h);
        correctionCtx.moveTo(x + w, y);
        correctionCtx.lineTo(x, y + h);
        correctionCtx.stroke();
    });
}


function recalculateDisplayedGrade() {
    if (!latestData || baseGrade === null) return;

    let restoredPoints = 0;

    Object.keys(overlayLabels).forEach(() => {});

    const sources = [
        { side: "front", type: "edges", spots: latestData.edges?.spots || [] },
        { side: "front", type: "corners", spots: latestData.corners?.spots || [] },
        { side: "front", type: "whitening", spots: latestData.whitening?.spots || [] },
        { side: "front", type: "surface", spots: latestData.surface?.spots || [] },
        { side: "back", type: "edges", spots: latestData.back?.edges?.spots || [] },
        { side: "back", type: "corners", spots: latestData.back?.corners?.spots || [] },
        { side: "back", type: "whitening", spots: latestData.back?.whitening?.spots || [] },
        { side: "back", type: "surface", spots: latestData.back?.surface?.spots || [] }
    ];

    sources.forEach(source => {
        source.spots.forEach((spot, index) => {
            const id = getSpotId(source, spot, index);

            if (isIgnored(id)) {
                restoredPoints += estimateSpotImpact(source, spot);
            }
        });
    });

    const adjustedGrade = Math.min(10, Math.round((baseGrade + restoredPoints) * 10) / 10);

    document.getElementById("final-grade").textContent = adjustedGrade;
    document.getElementById("grade-summary").textContent =
        `Adjusted after ignoring ${ignoredSpots.length} false-positive finding(s).`;
}