const elements = {};
let selectedFile = null;
let previewObjectUrl = null;
let identifyRequestId = 0;
let regionImage = null;
let activeRegion = "name";
let dragStart = null;
let ocrRegions = null;


export function initIdentifierUI({ apiBaseUrl }) {
    const uploadInput = document.getElementById("identifier-upload");
    const identifyButton = document.getElementById("identify-button");
    const previewImage = document.getElementById("identifier-preview-image");
    const regionCanvas = document.getElementById("identifier-region-canvas");
    const status = document.getElementById("identifier-status");
    const resultPanel = document.getElementById("identifier-result");
    const nameRegionButton = document.getElementById("identifier-name-region-button");
    const numberRegionButton = document.getElementById("identifier-number-region-button");
    const illustratorRegionButton = document.getElementById("identifier-illustrator-region-button");
    const resetRegionsButton = document.getElementById("identifier-reset-regions-button");

    if (!uploadInput || !identifyButton || !previewImage || !status || !resultPanel) {
        return;
    }

    elements.uploadInput = uploadInput;
    elements.identifyButton = identifyButton;
    elements.previewImage = previewImage;
    elements.regionCanvas = regionCanvas;
    elements.status = status;
    elements.resultPanel = resultPanel;
    elements.nameRegionButton = nameRegionButton;
    elements.numberRegionButton = numberRegionButton;
    elements.illustratorRegionButton = illustratorRegionButton;
    elements.resetRegionsButton = resetRegionsButton;

    initRegionSelector();

    uploadInput.addEventListener("change", () => {
        selectedFile = uploadInput.files[0] || null;
        identifyRequestId += 1;
        updateUploadZone(uploadInput, selectedFile);
        identifyButton.disabled = !selectedFile;
        identifyButton.textContent = "Identify Card";
        resetResult(resultPanel);

        if (!selectedFile) {
            setPreviewImage(previewImage, null);
            resetOcrRegions();
            setIdentifierStatus(status, "Choose a card image to identify.");
            return;
        }

        setPreviewImage(previewImage, selectedFile);
        setIdentifierStatus(status, "Card image loaded. Ready to identify.");
    });

    identifyButton.addEventListener("click", async () => {
        if (!selectedFile) {
            setIdentifierStatus(status, "Choose a card image first.");
            return;
        }

        const requestId = identifyRequestId + 1;
        const fileToIdentify = selectedFile;
        identifyRequestId = requestId;

        const formData = new FormData();
        formData.append("image", fileToIdentify);
        formData.append("ocr_regions", JSON.stringify(getIdentifierOcrRegions()));

        identifyButton.disabled = true;
        identifyButton.textContent = "Identifying...";
        setIdentifierStatus(status, "Reading card name and checking TCGdex...");
        resetResult(resultPanel);

        try {
            const response = await fetch(`${apiBaseUrl}/api/identify`, {
                method: "POST",
                body: formData
            });
            const data = await parseJsonResponse(response);

            if (isStaleIdentifyResponse(requestId, fileToIdentify)) {
                return;
            }

            if (!response.ok || !data.success) {
                setIdentifierStatus(status, formatIdentifierError(data));
                renderIdentifierDebug(resultPanel, data.debug);
                return;
            }

            renderCardResult(resultPanel, data.card);
            setIdentifierStatus(status, "Card identified.");

        } catch (error) {
            console.error(error);
            if (!isStaleIdentifyResponse(requestId, fileToIdentify)) {
                setIdentifierStatus(status, "Could not identify card. Check the backend response.");
            }
        } finally {
            if (!isStaleIdentifyResponse(requestId, fileToIdentify)) {
                identifyButton.disabled = !selectedFile;
                identifyButton.textContent = "Identify Card";
            }
        }
    });
}


export function showIdentificationResult(identification) {
    if (!elements.status || !elements.resultPanel) return;

    resetResult(elements.resultPanel);

    if (!identification) {
        setIdentifierStatus(elements.status, "Identification was not returned with this grade.");
        return;
    }

    if (!identification.success) {
        setIdentifierStatus(elements.status, formatIdentifierError(identification));
        renderIdentifierDebug(elements.resultPanel, identification.debug);
        return;
    }

    if (!identification.card) {
        setIdentifierStatus(elements.status, "Identification did not include card details.");
        return;
    }

    renderCardResult(elements.resultPanel, identification.card);
    setIdentifierStatus(elements.status, "Card identified from grading upload.");
}


export function setIdentifierPreviewFromFile(file) {
    if (!elements.previewImage || !elements.uploadInput) return;

    selectedFile = file || null;
    identifyRequestId += 1;
    updateUploadZone(elements.uploadInput, selectedFile);
    resetResult(elements.resultPanel);

    if (!selectedFile) {
        setPreviewImage(elements.previewImage, null);
        resetOcrRegions();

        if (elements.identifyButton) {
            elements.identifyButton.disabled = true;
            elements.identifyButton.textContent = "Identify Card";
        }

        if (elements.status) {
            setIdentifierStatus(elements.status, "Choose a card image to identify.");
        }

        return;
    }

    setPreviewImage(elements.previewImage, selectedFile);

    if (elements.identifyButton) {
        elements.identifyButton.disabled = false;
        elements.identifyButton.textContent = "Identify Card";
    }

    if (elements.status) {
        setIdentifierStatus(elements.status, "Card image loaded. Ready to identify.");
    }
}


export function getIdentifierOcrRegions() {
    if (!elements.regionCanvas || !regionImage || !ocrRegions) return {};

    const scaleX = regionImage.naturalWidth / elements.regionCanvas.width;
    const scaleY = regionImage.naturalHeight / elements.regionCanvas.height;

    return Object.fromEntries(
        Object.entries(ocrRegions).map(([key, region]) => [
            key,
            {
                x: Math.round(region.x * scaleX),
                y: Math.round(region.y * scaleY),
                width: Math.round(region.width * scaleX),
                height: Math.round(region.height * scaleY)
            }
        ])
    );
}


function updateUploadZone(input, file) {
    const zone = input.closest(".upload-zone");
    const label = zone?.querySelector(".label");

    if (!zone || !label) return;

    if (!label.dataset.defaultText) {
        label.dataset.defaultText = label.textContent;
    }

    zone.classList.toggle("loaded", Boolean(file));
    label.textContent = file ? file.name : label.dataset.defaultText;
}


function initRegionSelector() {
    const canvas = elements.regionCanvas;

    if (!canvas) return;

    canvas.addEventListener("mousedown", handleRegionMouseDown);
    window.addEventListener("mousemove", handleRegionMouseMove);
    window.addEventListener("mouseup", stopRegionDrag);

    canvas.addEventListener("touchstart", handleRegionTouchStart, { passive: false });
    window.addEventListener("touchmove", handleRegionTouchMove, { passive: false });
    window.addEventListener("touchend", stopRegionDrag);

    elements.nameRegionButton?.addEventListener("click", () => setActiveRegion("name"));
    elements.numberRegionButton?.addEventListener("click", () => setActiveRegion("number"));
    elements.illustratorRegionButton?.addEventListener("click", () => setActiveRegion("illustrator"));
    elements.resetRegionsButton?.addEventListener("click", () => {
        resetOcrRegions();
        drawRegionSelector();
        setIdentifierStatus(elements.status, "OCR areas reset. Drag on the image to adjust name, number, or illustrator.");
    });
}


function setActiveRegion(regionName) {
    activeRegion = regionName;
    drawRegionSelector();
    setIdentifierStatus(
        elements.status,
        `Drag on the image to select the ${regionLabel(regionName).toLowerCase()} area.`
    );
}


function loadRegionSelectorImage(src) {
    const canvas = elements.regionCanvas;
    if (!canvas) return;

    regionImage = new Image();

    regionImage.onload = () => {
        const maxWidth = 900;
        const scale = Math.min(maxWidth / regionImage.naturalWidth, 1);

        canvas.width = Math.round(regionImage.naturalWidth * scale);
        canvas.height = Math.round(regionImage.naturalHeight * scale);
        canvas.style.display = "block";

        if (elements.previewImage) {
            elements.previewImage.style.display = "none";
        }

        resetOcrRegions();
        drawRegionSelector();
    };

    regionImage.src = src;
}


function resetOcrRegions() {
    const canvas = elements.regionCanvas;

    if (!canvas) {
        ocrRegions = null;
        return;
    }

    if (!regionImage) {
        ocrRegions = null;
        canvas.style.display = "none";

        if (elements.previewImage) {
            elements.previewImage.style.display = "";
        }

        return;
    }

    ocrRegions = {
        name: {
            x: Math.round(canvas.width * 0.04),
            y: Math.round(canvas.height * 0.03),
            width: Math.round(canvas.width * 0.78),
            height: Math.round(canvas.height * 0.15)
        },
        number: {
            x: Math.round(canvas.width * 0.08),
            y: Math.round(canvas.height * 0.72),
            width: Math.round(canvas.width * 0.84),
            height: Math.round(canvas.height * 0.24)
        },
        illustrator: {
            x: Math.round(canvas.width * 0.06),
            y: Math.round(canvas.height * 0.66),
            width: Math.round(canvas.width * 0.62),
            height: Math.round(canvas.height * 0.10)
        }
    };
}


function drawRegionSelector() {
    const canvas = elements.regionCanvas;
    if (!canvas || !regionImage || !ocrRegions) return;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(regionImage, 0, 0, canvas.width, canvas.height);

    drawOcrRegion(ctx, ocrRegions.name, "Name", "#16a34a", activeRegion === "name");
    drawOcrRegion(ctx, ocrRegions.number, "Number", "#2563eb", activeRegion === "number");
    drawOcrRegion(ctx, ocrRegions.illustrator, "Illustrator", "#f97316", activeRegion === "illustrator");
}


function drawOcrRegion(ctx, region, label, color, isActive) {
    if (!region) return;

    ctx.save();
    ctx.fillStyle = isActive ? `${color}33` : `${color}1f`;
    ctx.strokeStyle = color;
    ctx.lineWidth = isActive ? 3 : 2;
    ctx.fillRect(region.x, region.y, region.width, region.height);
    ctx.strokeRect(region.x, region.y, region.width, region.height);

    ctx.fillStyle = color;
    ctx.font = "14px sans-serif";
    ctx.fillText(label, region.x + 6, Math.max(16, region.y - 6));
    ctx.restore();
}


function regionLabel(regionName) {
    if (regionName === "name") return "Card name";
    if (regionName === "number") return "Card number";
    if (regionName === "illustrator") return "Illustrator";
    return regionName;
}


function handleRegionMouseDown(event) {
    const point = getRegionCanvasPoint(event.clientX, event.clientY);
    startRegionDrag(point);
}


function handleRegionMouseMove(event) {
    if (!dragStart) return;

    const point = getRegionCanvasPoint(event.clientX, event.clientY);
    updateActiveRegion(point);
}


function handleRegionTouchStart(event) {
    if (!elements.regionCanvas) return;

    event.preventDefault();
    const touch = event.touches[0];
    startRegionDrag(getRegionCanvasPoint(touch.clientX, touch.clientY));
}


function handleRegionTouchMove(event) {
    if (!dragStart) return;

    event.preventDefault();
    const touch = event.touches[0];
    updateActiveRegion(getRegionCanvasPoint(touch.clientX, touch.clientY));
}


function startRegionDrag(point) {
    if (!regionImage || !ocrRegions) return;

    dragStart = point;
    ocrRegions[activeRegion] = {
        x: point.x,
        y: point.y,
        width: 1,
        height: 1
    };
    drawRegionSelector();
}


function updateActiveRegion(point) {
    const canvas = elements.regionCanvas;
    if (!canvas || !dragStart || !ocrRegions) return;

    const left = clamp(Math.min(dragStart.x, point.x), 0, canvas.width);
    const top = clamp(Math.min(dragStart.y, point.y), 0, canvas.height);
    const right = clamp(Math.max(dragStart.x, point.x), 0, canvas.width);
    const bottom = clamp(Math.max(dragStart.y, point.y), 0, canvas.height);

    ocrRegions[activeRegion] = {
        x: Math.round(left),
        y: Math.round(top),
        width: Math.max(1, Math.round(right - left)),
        height: Math.max(1, Math.round(bottom - top))
    };

    drawRegionSelector();
}


function stopRegionDrag() {
    dragStart = null;
}


function getRegionCanvasPoint(clientX, clientY) {
    const canvas = elements.regionCanvas;
    const rect = canvas.getBoundingClientRect();

    return {
        x: clamp((clientX - rect.left) * (canvas.width / rect.width), 0, canvas.width),
        y: clamp((clientY - rect.top) * (canvas.height / rect.height), 0, canvas.height)
    };
}


function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}


function setIdentifierStatus(status, message) {
    status.textContent = message;
}


function formatIdentifierError(data) {
    const message = data?.error || "Could not identify card.";
    const debug = data?.debug;

    if (!debug) {
        return message;
    }

    const readName = debug.read_name || "unknown";
    const readNumber = debug.read_number || "unknown";

    return `${message} OCR read name: "${readName}", number: "${readNumber}". Check backend console for crop details.`;
}


function resetResult(resultPanel) {
    if (!resultPanel) return;

    resultPanel.hidden = true;
    resultPanel.innerHTML = "";
}


function renderIdentifierDebug(resultPanel, debug) {
    if (!resultPanel || !debug) return;

    const cropImages = Array.isArray(debug.crop_images) ? debug.crop_images : [];
    const nameReads = Array.isArray(debug.name_reads) ? debug.name_reads : [];

    if (!cropImages.length && !nameReads.length) return;

    resultPanel.hidden = false;
    resultPanel.innerHTML = `
        <div class="identifier-details">
            <div class="identifier-name">OCR Debug</div>
            <div class="identifier-meta">
                <span>Read name: <strong>${escapeHtml(debug.read_name || "-")}</strong></span>
                <span>Read number: <strong>${escapeHtml(debug.read_number || "-")}</strong></span>
                <span>Read illustrator: <strong>${escapeHtml(debug.read_illustrator || "-")}</strong></span>
            </div>
            ${cropImages.length ? `
                <div class="identifier-price">Scanned crop regions:</div>
                <div class="identifier-debug-crops">
                    ${cropImages.map(crop => renderDebugCrop(crop, nameReads)).join("")}
                </div>
            ` : ""}
        </div>
    `;
}


function renderDebugCrop(crop, nameReads) {
    const readsForCrop = nameReads
        .filter(read => read.crop === crop.name)
        .slice()
        .sort((first, second) => Number(second.score || 0) - Number(first.score || 0))
        .slice(0, 3);

    return `
        <div class="identifier-debug-crop">
            <img class="identifier-card-image" src="${escapeAttribute(crop.image || "")}" alt="${escapeAttribute(crop.name || "OCR crop")}">
            <div>
                <strong>${escapeHtml(crop.name || "crop")}</strong>
                <div>${formatCropBox(crop.box)}</div>
                ${readsForCrop.map(read => `
                    <div>${escapeHtml(read.variant || "-")}: ${escapeHtml(read.name || read.text || "-")}</div>
                `).join("")}
            </div>
        </div>
    `;
}


function formatCropBox(box) {
    if (!box) return "";

    return `x:${escapeHtml(box.x)} y:${escapeHtml(box.y)} w:${escapeHtml(box.width)} h:${escapeHtml(box.height)}`;
}


function renderCardResult(resultPanel, card) {
    if (!card) {
        resetResult(resultPanel);
        return;
    }

    resultPanel.hidden = false;
    resultPanel.innerHTML = `
        ${card.image ? `<img class="identifier-card-image" src="${escapeAttribute(card.image)}" alt="${escapeAttribute(card.name)}">` : ""}
        <div class="identifier-details">
            <div class="identifier-name">${escapeHtml(card.name || "-")}</div>
            <div class="identifier-meta">
                <span>Set: <strong>${escapeHtml(card.set || "-")}</strong></span>
                <span>Number: <strong>${escapeHtml(card.number || "-")}</strong></span>
                <span>Rarity: <strong>${escapeHtml(card.rarity || "-")}</strong></span>
                <span>Illustrator: <strong>${escapeHtml(card.illustrator || "-")}</strong></span>
            </div>
            <div class="identifier-price">
                ${formatPrice(card.price, card.currency)}
            </div>
        </div>
    `;
}


function formatPrice(price, currency) {
    if (price === "Pricing unavailable" || price === null || price === undefined || price === "") {
        return "Pricing unavailable";
    }

    const value = Number(price);

    if (!Number.isFinite(value)) {
        return escapeHtml(String(price));
    }

    if (currency === "USD") {
        return `$${value.toFixed(2)} USD`;
    }

    if (currency === "EUR") {
        return `€${value.toFixed(2)} EUR`;
    }

    return `${value.toFixed(2)} ${escapeHtml(currency || "")}`.trim();
}


function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function escapeAttribute(value) {
    return escapeHtml(value);
}


function setPreviewImage(previewImage, file) {
    if (previewObjectUrl) {
        URL.revokeObjectURL(previewObjectUrl);
        previewObjectUrl = null;
    }

    if (!file) {
        previewImage.removeAttribute("src");
        regionImage = null;
        resetOcrRegions();
        return;
    }

    previewObjectUrl = URL.createObjectURL(file);
    previewImage.src = previewObjectUrl;
    loadRegionSelectorImage(previewObjectUrl);
}


async function parseJsonResponse(response) {
    const contentType = response.headers.get("content-type") || "";

    if (!contentType.includes("application/json")) {
        return {
            success: false,
            error: response.ok
                ? "Backend returned an unexpected response."
                : `Backend returned ${response.status} ${response.statusText || "error"}.`
        };
    }

    return response.json();
}


function isStaleIdentifyResponse(requestId, file) {
    return requestId !== identifyRequestId || file !== selectedFile;
}
