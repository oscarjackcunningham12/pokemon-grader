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

let latestImages = null;
let frontFile = null;
let backFile = null;

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


overlayButtons.forEach(button => {
    button.addEventListener("click", () => {
        setOverlay(button.dataset.overlay);
    });
});


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

        setStatus("Done");

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