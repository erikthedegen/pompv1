const socket = io(); 
const container = document.getElementById('canvas-container');

const BOX_WIDTH = 256;
const BOX_HEIGHT = 128;

let coinElements = {};

socket.on("clear_canvas", () => {
    container.innerHTML = "";
    coinElements = {};
});

socket.on("add_coin", (data) => {
    const id = data.id;
    const img = document.createElement('img');
    img.classList.add('coin-img');
    img.src = data.image;

    const index = parseInt(id, 10) - 1;
    const row = Math.floor(index / 2);
    const col = index % 2;

    img.style.left = (col * BOX_WIDTH) + "px";
    img.style.top = (row * BOX_HEIGHT) + "px";

    container.appendChild(img);
    coinElements[id] = { imgElement: img, overlayElement: null };

    requestAnimationFrame(() => {
        img.style.opacity = "1";
    });
});

socket.on("overlay_marks", (decisions) => {
    decisions.forEach(d => {
        const coin = coinElements[d.id];
        if (!coin) return;
        const overlay = document.createElement('img');
        overlay.classList.add('overlay-mark');
        overlay.src = d.decision === "yes" ? "greenmark.png" : "redcross.png";

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
