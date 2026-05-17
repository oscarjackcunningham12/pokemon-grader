const tools = {
    front: createCenteringTool("front-centering-canvas"),
    back: createCenteringTool("back-centering-canvas")
};

export function initManualCenteringCanvas() {
    tools.front.init();
    tools.back.init();
}

export function loadManualCenteringImage(file, side = "front") {
    if (!tools[side]) return;
    tools[side].loadImage(file);
}

export function getManualCenteringLines(side = "front") {
    if (!tools[side]) return null;
    return tools[side].getLines();
}

export function getAllManualCenteringLines() {
    return {
        front: tools.front.getLines(),
        back: tools.back.getLines()
    };
}

export function resetManualCenteringLines(side = "front") {
    if (!tools[side]) return;
    tools[side].reset();
}

function createCenteringTool(canvasId) {
    let canvas;
    let ctx;
    let image = null;
    let draggingLine = null;

    let lines = {
        left_outer: 20,
        left_inner: 70,
        right_inner: 530,
        right_outer: 580,
        top_outer: 20,
        top_inner: 70,
        bottom_inner: 730,
        bottom_outer: 780
    };

    const lineConfig = {
        left_outer: { color: "#16a34a", orientation: "vertical", label: "Left Outer" },
        left_inner: { color: "#16a34a", orientation: "vertical", label: "Left Inner" },
        right_inner: { color: "#2563eb", orientation: "vertical", label: "Right Inner" },
        right_outer: { color: "#2563eb", orientation: "vertical", label: "Right Outer" },
        top_outer: { color: "#16a34a", orientation: "horizontal", label: "Top Outer" },
        top_inner: { color: "#16a34a", orientation: "horizontal", label: "Top Inner" },
        bottom_inner: { color: "#2563eb", orientation: "horizontal", label: "Bottom Inner" },
        bottom_outer: { color: "#2563eb", orientation: "horizontal", label: "Bottom Outer" }
    };

    function init() {
        canvas = document.getElementById(canvasId);
        if (!canvas) return;

        ctx = canvas.getContext("2d");

        canvas.addEventListener("mousedown", handleMouseDown);
        window.addEventListener("mousemove", handleMouseMove);
        window.addEventListener("mouseup", stopDragging);

        canvas.addEventListener("touchstart", handleTouchStart, { passive: false });
        window.addEventListener("touchmove", handleTouchMove, { passive: false });
        window.addEventListener("touchend", stopDragging);
    }

    function loadImage(file) {
        if (!canvas) return;

        const reader = new FileReader();

        reader.onload = function (event) {
            image = new Image();

            image.onload = function () {
                const maxWidth = 900;
                const scale = Math.min(maxWidth / image.width, 1);

                canvas.width = Math.round(image.width * scale);
                canvas.height = Math.round(image.height * scale);

                resetLines();
                draw();
            };

            image.src = event.target.result;
        };

        reader.readAsDataURL(file);
    }

    function getLines() {
        return { ...lines };
    }

    function reset() {
        if (!canvas) return;
        resetLines();
        draw();
    }

    function resetLines() {
        const w = canvas.width;
        const h = canvas.height;

        lines = {
            left_outer: Math.round(w * 0.03),
            left_inner: Math.round(w * 0.12),
            right_inner: Math.round(w * 0.88),
            right_outer: Math.round(w * 0.97),
            top_outer: Math.round(h * 0.03),
            top_inner: Math.round(h * 0.12),
            bottom_inner: Math.round(h * 0.88),
            bottom_outer: Math.round(h * 0.97)
        };

        enforceLineOrder();
    }

    function draw() {
        if (!ctx || !image) return;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(image, 0, 0, canvas.width, canvas.height);

        drawShadedRegions();
        drawGuideLines();
    }

    function drawShadedRegions() {
        const leftOuter = lines.left_outer;
        const leftInner = lines.left_inner;
        const rightInner = lines.right_inner;
        const rightOuter = lines.right_outer;
        const topOuter = lines.top_outer;
        const topInner = lines.top_inner;
        const bottomInner = lines.bottom_inner;
        const bottomOuter = lines.bottom_outer;

        ctx.fillStyle = "rgba(255, 255, 255, 0.12)";
        ctx.fillRect(leftInner, topInner, rightInner - leftInner, bottomInner - topInner);

        ctx.fillStyle = "rgba(22, 163, 74, 0.10)";
        ctx.fillRect(leftOuter, topOuter, leftInner - leftOuter, bottomOuter - topOuter);
        ctx.fillRect(leftOuter, topOuter, rightOuter - leftOuter, topInner - topOuter);

        ctx.fillStyle = "rgba(37, 99, 235, 0.10)";
        ctx.fillRect(rightInner, topOuter, rightOuter - rightInner, bottomOuter - topOuter);
        ctx.fillRect(leftOuter, bottomInner, rightOuter - leftOuter, bottomOuter - bottomInner);
    }

    function drawGuideLines() {
        Object.entries(lines).forEach(([key, value]) => {
            const config = lineConfig[key];

            ctx.strokeStyle = config.color;
            ctx.lineWidth = 2;
            ctx.beginPath();

            if (config.orientation === "vertical") {
                ctx.moveTo(value, 0);
                ctx.lineTo(value, canvas.height);
            } else {
                ctx.moveTo(0, value);
                ctx.lineTo(canvas.width, value);
            }

            ctx.stroke();
            drawLineHandle(key, value);
        });
    }

    function drawLineHandle(key, value) {
        const config = lineConfig[key];

        ctx.fillStyle = config.color;
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 3;

        if (config.orientation === "vertical") {
            const y = canvas.height / 2;
            drawRoundedRect(value - 11, y - 28, 22, 56, 10);
        } else {
            const x = canvas.width / 2;
            drawRoundedRect(x - 28, value - 11, 56, 22, 10);
        }

        ctx.fill();
        ctx.stroke();
    }

    function drawRoundedRect(x, y, width, height, radius) {
        ctx.beginPath();
        ctx.roundRect(x, y, width, height, radius);
    }

    function handleMouseDown(event) {
        if (!canvas) return;

        const pos = getCanvasPos(event.clientX, event.clientY);
        startDragging(pos.x, pos.y);
    }

    function handleMouseMove(event) {
        if (!draggingLine) return;

        const pos = getCanvasPos(event.clientX, event.clientY);
        moveLine(pos.x, pos.y);
    }

    function handleTouchStart(event) {
        if (!canvas) return;

        event.preventDefault();

        const touch = event.touches[0];
        const pos = getCanvasPos(touch.clientX, touch.clientY);

        startDragging(pos.x, pos.y);
    }

    function handleTouchMove(event) {
        if (!draggingLine) return;

        event.preventDefault();

        const touch = event.touches[0];
        const pos = getCanvasPos(touch.clientX, touch.clientY);

        moveLine(pos.x, pos.y);
    }

    function startDragging(x, y) {
        draggingLine = findClosestLine(x, y);

        if (draggingLine) {
            moveLine(x, y);
        }
    }

    function findClosestLine(x, y) {
        let closest = null;
        let closestDistance = 999999;
        const hitArea = 55;

        Object.entries(lines).forEach(([key, value]) => {
            const config = lineConfig[key];

            const distance =
                config.orientation === "vertical"
                    ? Math.abs(x - value)
                    : Math.abs(y - value);

            if (distance < closestDistance && distance <= hitArea) {
                closest = key;
                closestDistance = distance;
            }
        });

        return closest;
    }

    function moveLine(x, y) {
        if (!draggingLine) return;

        const config = lineConfig[draggingLine];

        if (config.orientation === "vertical") {
            lines[draggingLine] = clamp(Math.round(x), 0, canvas.width);
        } else {
            lines[draggingLine] = clamp(Math.round(y), 0, canvas.height);
        }

        enforceLineOrder();
        draw();
    }

    function stopDragging() {
        draggingLine = null;
    }

    function enforceLineOrder() {
        const minGap = 4;

        lines.left_outer = clamp(lines.left_outer, 0, canvas.width);
        lines.left_inner = clamp(lines.left_inner, lines.left_outer + minGap, canvas.width);
        lines.right_inner = clamp(lines.right_inner, lines.left_inner + minGap, canvas.width);
        lines.right_outer = clamp(lines.right_outer, lines.right_inner + minGap, canvas.width);

        lines.top_outer = clamp(lines.top_outer, 0, canvas.height);
        lines.top_inner = clamp(lines.top_inner, lines.top_outer + minGap, canvas.height);
        lines.bottom_inner = clamp(lines.bottom_inner, lines.top_inner + minGap, canvas.height);
        lines.bottom_outer = clamp(lines.bottom_outer, lines.bottom_inner + minGap, canvas.height);
    }

    function getCanvasPos(clientX, clientY) {
        const rect = canvas.getBoundingClientRect();

        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;

        return {
            x: (clientX - rect.left) * scaleX,
            y: (clientY - rect.top) * scaleY
        };
    }

    function clamp(value, min, max) {
        return Math.max(min, Math.min(max, value));
    }

    return {
        init,
        loadImage,
        getLines,
        reset
    };
}