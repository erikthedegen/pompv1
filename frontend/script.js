const socket = io(); 
const container = document.getElementById('canvas-container');

const BOX_WIDTH = 256;
const BOX_HEIGHT = 128;

// Global dictionary of bundlechunks:
// { "bundle_id": { "01": <imgurl>, "02": <imgurl>, ... "08": <imgurl> } }
let bundlechunks = {};
let currentBundleId = null;
let coinElements = {};

socket.on("clear_canvas", (data) => {
    console.log("Received clear_canvas from server:", data);

    container.innerHTML = "";
    coinElements = {};

    if (!data.bundle_id) {
        console.warn("clear_canvas event missing bundle_id. Cannot track chunks by bundle.");
        currentBundleId = null;
        return;
    }

    currentBundleId = data.bundle_id;
    bundlechunks[currentBundleId] = {};
    console.log(`Initialized bundlechunks for ${currentBundleId}`);
});

socket.on("add_coin", (data) => {
    console.log("Received add_coin from server:", data);

    if (!currentBundleId) {
        console.warn("Received add_coin but no currentBundleId set. Is clear_canvas sending a bundle_id?");
        return;
    }

    const id = data.id;
    const imageUrl = data.url;

    // Store the chunk data in bundlechunks
    bundlechunks[currentBundleId][id] = imageUrl;

    // If we've received all 8 coins for this bundle, we can display them
    if (Object.keys(bundlechunks[currentBundleId]).length === 8) {
        console.log(`All 8 coins received for bundle ${currentBundleId}, rendering now...`);
        renderCoins(currentBundleId);
    }
});

socket.on("overlay_marks", (decisions) => {
    console.log("Received overlay_marks from server:", decisions);
    decisions.forEach(d => {
        const coin = coinElements[d.id];
        if (!coin) return;
        const overlay = document.createElement('img');
        overlay.classList.add('overlay-mark');
        // Use /static prefix for overlay images
        overlay.src = d.decision === "yes" ? "/static/greenmark.png" : "/static/redcross.png";

        const index = parseInt(d.id, 10)-1;
        const row = Math.floor(index / 2);
        const col = index % 2;
        overlay.style.left = (col * BOX_WIDTH + 5) + "px";
        overlay.style.top = (row * BOX_HEIGHT + 5) + "px";

        container.appendChild(overlay);
        coin.overlayElement = overlay;
        requestAnimationFrame(() => {
            overlay.style.opacity = "1";
        });
    });
});

socket.on("fade_out", () => {
    console.log("Received fade_out from server");
    const keys = Object.keys(coinElements);
    let i = 0;
    function fadeNext() {
        if (i >= keys.length) return;
        const k = keys[i];
        const coin = coinElements[k];
        coin.imgElement.style.opacity = "0";
        if (coin.overlayElement) {
            coin.overlayElement.style.opacity = "0";
        }
        i++;
        setTimeout(fadeNext, 500);
    }
    fadeNext();
});

function renderCoins(bundle_id) {
    const chunkDict = bundlechunks[bundle_id];
    if (!chunkDict) {
        console.error(`No chunk dictionary found for bundle_id ${bundle_id}`);
        return;
    }

    // Sort keys to ensure correct order: '01','02','03', etc.
    const coinIds = Object.keys(chunkDict).sort();
    for (let coinId of coinIds) {
        const imageUrl = chunkDict[coinId];

        const img = document.createElement('img');
        img.classList.add('coin-img');
        img.src = imageUrl;

        const index = parseInt(coinId, 10) - 1;
        const row = Math.floor(index / 2);
        const col = index % 2;

        img.style.left = (col * BOX_WIDTH) + "px";
        img.style.top = (row * BOX_HEIGHT) + "px";
        img.style.opacity = "0"; // Start invisible and fade in
        container.appendChild(img);

        coinElements[coinId] = { imgElement: img, overlayElement: null };

        requestAnimationFrame(() => {
            img.style.opacity = "1";
        });
    }

    console.log(`Rendered bundle ${bundle_id} coins to the frontend.`);
}
