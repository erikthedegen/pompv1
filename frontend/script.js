(function() {
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
        const {id, image} = data;
        const imgElem = document.createElement('img');
        imgElem.classList.add('coin-img');
        imgElem.src = image;

        const idx = parseInt(id, 10) - 1;
        const row = Math.floor(idx / 2);
        const col = idx % 2;

        imgElem.style.left = (col * BOX_WIDTH) + "px";
        imgElem.style.top = (row * BOX_HEIGHT) + "px";

        container.appendChild(imgElem);
        coinElements[id] = { imgElement: imgElem, overlayElement: null };

        requestAnimationFrame(() => {
            imgElem.style.opacity = "1";
        });
    });

    socket.on("overlay_marks", (decisions) => {
        // decisions is expected to be an array of {id: "01", decision: "yes"|"no"}
        decisions.forEach(item => {
            const coinId = item.id;
            const coinData = coinElements[coinId];
            if (!coinData) return;

            const overlay = document.createElement('img');
            overlay.classList.add('overlay-mark');
            overlay.src = item.decision === "yes" ? "greenmark.png" : "redcross.png";

            const idx = parseInt(coinId, 10) - 1;
            const row = Math.floor(idx / 2);
            const col = idx % 2;
            overlay.style.left = (col * BOX_WIDTH + 5) + "px";
            overlay.style.top = (row * BOX_HEIGHT + 5) + "px";

            container.appendChild(overlay);
            coinData.overlayElement = overlay;

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
            const currentKey = keys[i];
            const coin = coinElements[currentKey];
            if (coin && coin.imgElement) {
                coin.imgElement.style.opacity = "0";
            }
            if (coin && coin.overlayElement) {
                coin.overlayElement.style.opacity = "0";
            }
            i++;
            setTimeout(fadeNext, 500);
        }
        fadeNext();
    });
})();
