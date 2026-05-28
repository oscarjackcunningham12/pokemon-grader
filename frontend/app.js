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
    resetDashboardUI,
    setScoreBar
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

import {
    initIdentifierUI
} from "./modules/identifier-ui.js";


const frontUpload = document.getElementById("front-upload");
const backUpload = document.getElementById("back-upload");
const analyzeButton = document.getElementById("analyze-button");

const overlayImage = document.getElementById("overlay-image");
const overlayTitle = document.getElementById("overlay-title");
const overlayButtons = document.querySelectorAll("[data-overlay]");
const correctionCanvas = document.getElementById("correction-canvas");
const correctionCtx = correctionCanvas ? correctionCanvas.getContext("2d") : null;
const resetCorrectionsButton = document.getElementById("reset-corrections-button");
const LOCAL_API_BASE_URL = "http://127.0.0.1:5000";
const PRODUCTION_API_BASE_URL = "https://pokemon-grader-t1ky.onrender.com";
const API_BASE_URL = window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost"
    ? LOCAL_API_BASE_URL
    : PRODUCTION_API_BASE_URL;

let latestImages = null;
let latestData = null;

let frontFile = null;
let backFile = null;

let currentOverlayKey = "centering_overlay";
let ignoredSpots = [];
let ignoredHistory = [];
let correctionRequestId = 0;


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
    correctionRequestId += 1;
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

    updateUploadZone(frontUpload, frontFile);
    updateUploadZone(backUpload, backFile);
}


function updateAnalyzeButtonState() {
    if (!analyzeButton) return;

    analyzeButton.disabled = !(frontFile && backFile);
}


function updateUploadZone(input, file) {
    const zone = input?.closest(".upload-zone");
    const label = zone?.querySelector(".label");

    if (!zone || !label) return;

    zone.classList.toggle("loaded", Boolean(file));
    label.textContent = file ? file.name : label.dataset.defaultText || label.textContent;
}


function initUploadZones() {
    [frontUpload, backUpload].forEach(input => {
        const label = input?.closest(".upload-zone")?.querySelector(".label");
        if (label && !label.dataset.defaultText) {
            label.dataset.defaultText = label.textContent;
        }
    });
}


function setOverlay(overlayKey) {
    if (!latestImages) return;

    currentOverlayKey = overlayKey;

    const clickableSource = getCurrentSpotSource();

    let imageKey = overlayKey;

    if (clickableSource) {
        imageKey = clickableSource.side === "back" ? "back_card" : "card";
    }

    if (!latestImages[imageKey]) return;

    overlayImage.onload = () => {
        syncCorrectionCanvas();

        requestAnimationFrame(() => {
            drawCorrectionOverlay();
        });
    };

    overlayImage.src = `data:image/png;base64,${latestImages[imageKey]}`;

    if (overlayTitle) {
        overlayTitle.textContent = overlayLabels[overlayKey] || "Overlay";
    }

    overlayButtons.forEach(button => {
        button.classList.toggle("active", button.dataset.overlay === overlayKey);
    });

    updateFindingSummary();
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
    if (typeof spot.grade_penalty === "number") {
        return spot.grade_penalty;
    }

    return 0;
}
function showSpotDetails(source, clicked) {
    const detailsPanel = document.getElementById("finding-details");

    if (!detailsPanel) return;

    const spot = clicked.spot;
    const impact = estimateSpotImpact(source, spot);

    detailsPanel.innerHTML = `
        <h4>Finding Details</h4>
        <p><strong>Side:</strong> ${source.side}</p>
        <p><strong>Type:</strong> ${source.type}</p>
        <p><strong>Severity:</strong> ${spot.severity || "unknown"}</p>
        <p><strong>Area:</strong> ${spot.area || "unknown"} px</p>
        <p><strong>Estimated Grade Impact:</strong> -${impact}</p>
        <p class="hint">Shift-click this finding to ignore it.</p>
    `;
}


async function ignoreSpot(spotId) {
    if (!ignoredSpots.includes(spotId)) {
        ignoredSpots.push(spotId);
        ignoredHistory.push(spotId);
    }

    drawCorrectionOverlay();
    updateFindingSummary();
    showCorrectionSummary();

    setStatus("Finding ignored. Recalculating grade...");

    if (await recalculateCorrections()) {
        setStatus("Finding ignored and grade adjusted.");
    }
}

async function undoLastIgnoredSpot() {
    const lastIgnored = ignoredHistory.pop();

    if (!lastIgnored) {
        setStatus("No ignored findings to undo.");
        return;
    }

    ignoredSpots = ignoredSpots.filter(id => id !== lastIgnored);

    drawCorrectionOverlay();

    const detailsPanel = document.getElementById("finding-details");

    if (detailsPanel) {
        detailsPanel.innerHTML = `
            <h4>Ignore Undone</h4>
            <p>The last ignored finding was restored.</p>
            <p><strong>Ignored findings:</strong> ${ignoredSpots.length}</p>
        `;
    }

    setStatus("Finding restored. Recalculating grade...");

    if (await recalculateCorrections()) {
        setStatus("Last ignored finding restored.");
    }
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
        void ignoreSpot(clicked.id);
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


if (resetCorrectionsButton) {
    resetCorrectionsButton.addEventListener("click", resetCorrections);
}


initManualCenteringCanvas();
initUploadZones();
initIdentifierUI({ apiBaseUrl: API_BASE_URL });
resetAllUI();
updateAnalyzeButtonState();


frontUpload.addEventListener("change", (event) => {
    const file = getFileFromInput(event);

    if (!file) return;

    frontFile = file;

    resetAllUI();
    ignoredHistory = [];
    loadManualCenteringImage(file, "front");
    updateUploadZone(frontUpload, frontFile);

    setStatus("Front image loaded. Adjust the front guide lines, then upload the back image.");
    updateAnalyzeButtonState();
});


backUpload.addEventListener("change", (event) => {
    const file = getFileFromInput(event);

    if (!file) return;

    backFile = file;

    loadManualCenteringImage(file, "back");
    updateUploadZone(backUpload, backFile);

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
        const response = await fetch(`${API_BASE_URL}/api/analyze/full`, {
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

   drawCorrectionOverlay();
}


function drawCorrectionOverlay() {
    if (!correctionCtx || !correctionCanvas || !overlayImage) return;

    correctionCtx.clearRect(0, 0, correctionCanvas.width, correctionCanvas.height);

    const source = getCurrentSpotSource();
    if (!source) return;

    const rect = overlayImage.getBoundingClientRect();

    const scaleX = rect.width / overlayImage.naturalWidth;
    const scaleY = rect.height / overlayImage.naturalHeight;

    source.spots.forEach((spot, index) => {
        const id = getSpotId(source, spot, index);

        if (isIgnored(id)) return;

        const box = getSpotBox(spot);

        const x = box.x * scaleX;
        const y = box.y * scaleY;
        const w = box.width * scaleX;
        const h = box.height * scaleY;

        const color = getFindingColor(spot.severity);

        correctionCtx.fillStyle = color.fill;
        correctionCtx.strokeStyle = color.stroke;
        correctionCtx.lineWidth = 2;

        correctionCtx.fillRect(x, y, w, h);
        correctionCtx.strokeRect(x, y, w, h);
    });
}

function buildCorrectionAnalysisPayload() {
    if (!latestData) return null;

    return {
        mode: latestData.mode,
        centering: latestData.centering,
        back_centering: latestData.back_centering,
        edges: latestData.edges,
        corners: latestData.corners,
        whitening: latestData.whitening,
        surface: latestData.surface,
        back: latestData.back
    };
}

function applyCorrectedFinalGrade(adjustedData) {
    const finalGrade = adjustedData.final_grade;
    if (!finalGrade) return;

    document.getElementById("final-grade").textContent = finalGrade.final_grade;
    document.getElementById("grade-label").textContent =
        `${finalGrade.grade_label} (${finalGrade.grade_bucket})`;
    document.getElementById("grade-summary").textContent =
        `Adjusted after ignoring ${ignoredSpots.length} finding(s).`;
}

function applyCorrectedScoreCards(adjustedData) {
    const summary = adjustedData.combined || adjustedData.front;
    if (!summary) return;

    document.getElementById("horizontal-ratio").textContent =
        summary.centering?.horizontal_ratio || "-";
    document.getElementById("vertical-ratio").textContent =
        summary.centering?.vertical_ratio || "-";
    setScoreBar("horizontal-score-bar", getRatioScore(summary.centering?.horizontal_ratio));
    setScoreBar("vertical-score-bar", getRatioScore(summary.centering?.vertical_ratio));

    document.getElementById("edges-score").textContent = summary.edges.overall_score;
    document.getElementById("edges-severity").textContent = summary.edges.severity;
    setScoreBar("edges-score-bar", summary.edges.overall_score);

    document.getElementById("corners-score").textContent = summary.corners.overall_score;
    document.getElementById("corners-severity").textContent = summary.corners.severity;
    setScoreBar("corners-score-bar", summary.corners.overall_score);

    document.getElementById("whitening-score").textContent = summary.whitening.score;
    document.getElementById("whitening-spots").textContent = summary.whitening.spot_count;
    setScoreBar("whitening-score-bar", summary.whitening.score);

    document.getElementById("surface-score").textContent = summary.surface.score;
    document.getElementById("surface-defects").textContent = summary.surface.issue_count;
    setScoreBar("surface-score-bar", summary.surface.score);
}

function getRatioScore(rawRatio) {
    const ratioText = String(rawRatio || "");
    const numbers = ratioText.match(/\d+(\.\d+)?/g)?.map(Number);

    if (!numbers || numbers.length < 2) return null;

    const lowerSide = Math.min(numbers[0], numbers[1]);
    const higherSide = Math.max(numbers[0], numbers[1]);

    if (!higherSide) return null;

    return (lowerSide / higherSide) * 10;
}

async function recalculateCorrections() {
    if (!latestData) return false;

    const analysis = buildCorrectionAnalysisPayload();
    const requestId = correctionRequestId + 1;
    correctionRequestId = requestId;

    try {
        const response = await fetch(`${API_BASE_URL}/api/corrections/recalculate`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                analysis,
                ignored_spot_ids: ignoredSpots
            })
        });

        const adjustedData = await response.json();

        if (requestId !== correctionRequestId) {
            return false;
        }

        if (!response.ok || adjustedData.error) {
            setStatus(`Error: ${adjustedData.error || "Could not recalculate corrections."}`);
            return false;
        }

        applyCorrectedFinalGrade(adjustedData);
        applyCorrectedScoreCards(adjustedData);

        return true;

    } catch (error) {
        console.error(error);

        if (requestId === correctionRequestId) {
            setStatus("Could not recalculate corrections. Make sure Flask is running.");
        }

        return false;
    }
}

function resetCorrections() {
    ignoredSpots = [];
    ignoredHistory = [];
    correctionRequestId += 1;

    drawCorrectionOverlay();

    if (latestData) {
        updateFinalGradeUI(latestData);
        updateScoreCardsUI(latestData);
    }

    const detailsPanel = document.getElementById("finding-details");

    if (detailsPanel) {
        detailsPanel.innerHTML = `
            <h4>Finding Details</h4>
            <p>All corrections were reset.</p>
            <button id="reset-corrections-button" class="secondary-button">
                Reset Corrections
            </button>
        `;

        document
            .getElementById("reset-corrections-button")
            .addEventListener("click", resetCorrections);
    }

    setStatus("Corrections reset.");
}
function updateFindingSummary() {
    const detailsPanel = document.getElementById("finding-details");
    if (!detailsPanel || !latestData) return;

    const source = getCurrentSpotSource();

    if (!source) {
        detailsPanel.innerHTML = `
            <h4>Finding Details</h4>
            <p>This overlay has no clickable findings.</p>
        `;
        return;
    }

    detailsPanel.innerHTML = `
        <h4>Finding Details</h4>
        <p><strong>Overlay:</strong> ${source.side} ${source.type}</p>
        <p><strong>Detected findings:</strong> ${source.spots.length}</p>
        <p><strong>Ignored findings:</strong> ${ignoredSpots.length}</p>
        <p class="hint">Click a box to inspect it. Shift-click to ignore it.</p>
    `;
}

function getFindingColor(severity) {
    if (severity === "heavy") {
        return {
            fill: "rgba(239, 68, 68, 0.22)",
            stroke: "#ef4444"
        };
    }

    if (severity === "moderate") {
        return {
            fill: "rgba(249, 115, 22, 0.22)",
            stroke: "#f97316"
        };
    }

    return {
        fill: "rgba(234, 179, 8, 0.22)",
        stroke: "#eab308"
    };
}
function showCorrectionSummary() {
    const detailsPanel = document.getElementById("finding-details");
    if (!detailsPanel) return;

    detailsPanel.innerHTML = `
        <h4>Correction Applied</h4>
        <p><strong>Ignored findings:</strong> ${ignoredSpots.length}</p>
        <p>The visible grade and subgrades have been adjusted.</p>
        <button id="undo-ignore-button" class="secondary-button">
            Undo Last Ignore
        </button>
        <button id="reset-corrections-button" class="secondary-button">
            Reset Corrections
        </button>
    `;

    document
        .getElementById("undo-ignore-button")
        .addEventListener("click", undoLastIgnoredSpot);

    document
        .getElementById("reset-corrections-button")
        .addEventListener("click", resetCorrections);
}
