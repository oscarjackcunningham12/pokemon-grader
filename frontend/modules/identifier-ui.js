export function initIdentifierUI({ apiBaseUrl }) {
    const uploadInput = document.getElementById("identifier-upload");
    const identifyButton = document.getElementById("identify-button");
    const previewImage = document.getElementById("identifier-preview-image");
    const status = document.getElementById("identifier-status");
    const resultPanel = document.getElementById("identifier-result");

    let selectedFile = null;

    if (!uploadInput || !identifyButton || !previewImage || !status || !resultPanel) {
        return;
    }

    uploadInput.addEventListener("change", () => {
        selectedFile = uploadInput.files[0] || null;
        updateUploadZone(uploadInput, selectedFile);
        identifyButton.disabled = !selectedFile;
        resetResult(resultPanel);

        if (!selectedFile) {
            previewImage.removeAttribute("src");
            setIdentifierStatus(status, "Choose a card image to identify.");
            return;
        }

        previewImage.src = URL.createObjectURL(selectedFile);
        setIdentifierStatus(status, "Card image loaded. Ready to identify.");
    });

    identifyButton.addEventListener("click", async () => {
        if (!selectedFile) {
            setIdentifierStatus(status, "Choose a card image first.");
            return;
        }

        const formData = new FormData();
        formData.append("image", selectedFile);

        identifyButton.disabled = true;
        identifyButton.textContent = "Identifying...";
        setIdentifierStatus(status, "Reading card name and checking TCGdex...");
        resetResult(resultPanel);

        try {
            const response = await fetch(`${apiBaseUrl}/api/identify`, {
                method: "POST",
                body: formData
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                setIdentifierStatus(status, data.error || "Could not identify card.");
                return;
            }

            renderCardResult(resultPanel, data.card);
            setIdentifierStatus(status, "Card identified.");

        } catch (error) {
            console.error(error);
            setIdentifierStatus(status, "Could not connect to backend. Make sure Flask is running.");
        } finally {
            identifyButton.disabled = !selectedFile;
            identifyButton.textContent = "Identify Card";
        }
    });
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
    resultPanel.hidden = true;
    resultPanel.innerHTML = "";
}


function renderCardResult(resultPanel, card) {
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
