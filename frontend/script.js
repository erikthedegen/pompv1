const socket = io(); 
const container = document.getElementById('canvas-container');

const BOX_WIDTH = 256;
const BOX_HEIGHT = 128;

// We'll maintain a queue of bundles waiting to be displayed
// Each entry: { bundle_id: "xxx", coins: {id: imgUrl}, decisions: [...], ready: bool }
let bundleQueue = [];
let currentBundle = null;
let coinElements = {};

socket.on("clear_canvas", (data) => {
    console.log("Received clear_canvas from server:", data);
    // Start a new bundle entry in the queue
    if (!data.bundle_id) {
        console.warn("clear_canvas event missing bundle_id.");
        return;
    }

    // Create a new bundle object
    bundleQueue.push({
        bundle_id: data.bundle_id,
        coins: {},
        decisions: [],
        ready: false
    });
});

socket.on("add_coin", (data) => {
    console.log("Received add_coin from server:", data);

    if (!data.bundle_id) {
        console.warn("add_coin event without a bundle_id");
        return;
    }

    const bundle = bundleQueue.find(b => b.bundle_id === data.bundle_id);
    if (!bundle) {
        console.warn("No corresponding bundle found for add_coin.");
        return;
    }

    const {id, url} = data;
    bundle.coins[id] = url;

    // If we have all 8 coins, mark bundle as ready to render
    if (Object.keys(bundle.coins).length === 8) {
        console.log(`All 8 coins received for bundle ${bundle.bundle_id}, bundle is ready.`);
        bundle.ready = true;
        tryToStartNextBundle();
    }
});

socket.on("overlay_marks", (decisions) => {
    console.log("Received overlay_marks from server:", decisions);
    // Store decisions in the corresponding bundle
    // The current displayed bundle is `currentBundle`
    if (!bundleQueue.length) return;
    const activeBundle = bundleQueue[bundleQueue.length - 1];
    activeBundle.decisions = decisions;
});

socket.on("fade_out", () => {
    console.log("Received fade_out from server");
    // Fade out current visible bundle
    fadeOutCoins();
});

function tryToStartNextBundle() {
    // If there is no current bundle being displayed and we have a ready bundle
    if (!currentBundle) {
        const nextBundle = bundleQueue.find(b => b.ready);
        if (nextBundle) {
            startBundleDisplay(nextBundle);
        }
    }
}

function startBundleDisplay(bundle) {
    currentBundle = bundle;
    // Clear the container and coinElements
    container.innerHTML = "";
    coinElements = {};

    const coinIds = Object.keys(bundle.coins).sort();
    let delay = 0;
    // Render coins invisible first
    for (let coinId of coinIds) {
        const imageUrl = bundle.coins[coinId];
        const img = document.createElement('img');
        img.classList.add('coin-img');
        img.src = imageUrl;

        const index = parseInt(coinId, 10) - 1;
        const row = Math.floor(index / 2);
        const col = index % 2;

        img.style.left = (col * BOX_WIDTH) + "px";
        img.style.top = (row * BOX_HEIGHT) + "px";
        img.style.opacity = "0"; 
        container.appendChild(img);

        coinElements[coinId] = { imgElement: img, overlayElement: null };
    }

    // Fade them in one by one with a small delay
    let i = 0;
    (function fadeNext() {
        if (i >= coinIds.length) {
            // Once all coins are visible, show overlay if any
            applyOverlayMarks();
            return;
        }
        const cid = coinIds[i];
        const coin = coinElements[cid];
        if (coin) {
            requestAnimationFrame(() => {
                setTimeout(() => {
                    coin.imgElement.style.opacity = "1";
                    i++;
                    fadeNext();
                }, 200); // 200ms between each coin fade in
            });
        } else {
            i++;
            fadeNext();
        }
    })();
}

function applyOverlayMarks() {
    if (!currentBundle || !currentBundle.decisions) return;
    currentBundle.decisions.forEach(d => {
        const coin = coinElements[d.id];
        if (!coin) return;
        const overlay = document.createElement('img');
        overlay.classList.add('overlay-mark');
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
}

function fadeOutCoins() {
    const keys = Object.keys(coinElements);
    let i = 0;
    function fadeNext() {
        if (i >= keys.length) {
            // Once done fading out, remove currentBundle from queue and set currentBundle = null
            const idx = bundleQueue.indexOf(currentBundle);
            if (idx !== -1) {
                bundleQueue.splice(idx, 1);
            }
            currentBundle = null;
            // Try to start next bundle immediately if ready
            tryToStartNextBundle();
            return;
        }
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
}
