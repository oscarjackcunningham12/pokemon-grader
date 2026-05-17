export function getUploadedFile(event) {
    const file = event.target.files[0];
    return file || null;
}


export function buildFormData(file) {
    const formData = new FormData();
    formData.append("image", file);
    return formData;
}


export function setStatus(message) {
    const status = document.getElementById("status");
    if (status) status.textContent = message;
}


export function clearImages() {
    const previewImage = document.getElementById("preview-image");
    const overlayImage = document.getElementById("overlay-image");

    if (previewImage) previewImage.src = "";
    if (overlayImage) overlayImage.src = "";
}


export function setBaseImages(images) {
    if (!images) return;

    const previewImage = document.getElementById("preview-image");
    const overlayImage = document.getElementById("overlay-image");

    if (previewImage && images.card) {
        previewImage.src = `data:image/png;base64,${images.card}`;
    }

    if (overlayImage && images.centering_overlay) {
        overlayImage.src = `data:image/png;base64,${images.centering_overlay}`;
    }
}