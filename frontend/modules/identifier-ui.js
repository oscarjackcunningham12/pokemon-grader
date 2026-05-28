const elements = {};
let selectedFile = null;
let previewObjectUrl = null;
let identifyRequestId = 0;


export function initIdentifierUI({ apiBaseUrl }) {
    const uploadInput = document.getElementById("identifier-upload");
    const identifyButton = document.getElementById("identify-button");
    const previewImage = document.getElementById("identifier-preview-image");
    const status = document.getElementById("identifier-status");
    const resultPanel = document.getElementById("identifier-result");

    if (!uploadInput || !identifyButton || !previewImage || !status || !resultPanel) {
        return;
    }

    elements.uploadInput = uploadInput;
    elements.identifyButton = identifyButton;
    elements.previewImage = previewImage;
    elements.status = status;
    elements.resultPanel = resultPanel;

    uploadInput.addEventListener("change", () => {
        selectedFile = uploadInput.files[0] || null;
        identifyRequestId += 1;
        updateUploadZone(uploadInput, selectedFile);
        identifyButton.disabled = !selectedFile;
        identifyButton.textContent = "Identify Card";
        resetResult(resultPanel);

        if (!selectedFile) {
            setPreviewImage(previewImage, null);
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
                setIdentifierStatus(status, data.error || "Could not identify card.");
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
        setIdentifierStatus(elements.status, identification.error || "Could not identify card.");
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


function setIdentifierStatus(status, message) {
    status.textContent = message;
}


function resetResult(resultPanel) {
    if (!resultPanel) return;

    resultPanel.hidden = true;
    resultPanel.innerHTML = "";
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
        return;
    }

    previewObjectUrl = URL.createObjectURL(file);
    previewImage.src = previewObjectUrl;
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
