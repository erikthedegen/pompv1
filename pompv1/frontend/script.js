/****************************************************
 * Socket.io + Bundles/Decisions
 ****************************************************/

const socket = io();

// We keep track of bundles + decisions
let bundleQueue = [];
let decisionsStore = {};    // { [bundleId]: { [coinId]: "yes"|"no" } }
let currentBundleId = null; // Which bundle is currently being displayed?

socket.on("clear_canvas", (data) => {
  console.log("Received clear_canvas:", data);
  const { bundle_id } = data;
  if (!bundle_id) return console.warn("clear_canvas missing bundle_id.");

  bundleQueue.push({
    bundle_id,
    coins: [],
    ready: false
  });
  tryToStartNextBundle();
});

socket.on("add_coin", (data) => {
  console.log("Received add_coin:", data);
  const { bundle_id, id, url } = data;
  if (!bundle_id || !id || !url) {
    return console.warn("add_coin event missing data.");
  }

  const bundle = bundleQueue.find(b => b.bundle_id === bundle_id);
  if (!bundle) {
    return console.warn("No matching bundle for add_coin.");
  }

  bundle.coins.push({ id, url });
  // If we have 8 coins, mark ready
  if (bundle.coins.length === 8) {
    console.log(`All 8 coins for bundle ${bundle_id} received; marking ready.`);
    bundle.ready = true;
    tryToStartNextBundle();
  }
});

socket.on("overlay_marks", (marks) => {
  console.log("Received overlay_marks:", marks);
  if (!currentBundleId) {
    console.warn("No currentBundleId, storing decisions anyway.");
  }
  if (!decisionsStore[currentBundleId]) {
    decisionsStore[currentBundleId] = {};
  }
  marks.forEach(m => {
    decisionsStore[currentBundleId][m.id] = m.decision; // "yes" or "no"
  });
});

socket.on("fade_out", () => {
  console.log("Received fade_out (unused in watermill approach).");
});

// NEW listener for disqualified coins
socket.on("disqualified_coin", (data) => {
  console.log("Received disqualified_coin:", data);
  // Show a big red "DISQUALIFIED" overlay
  const msgDiv = document.createElement("div");
  msgDiv.style.position = "fixed";
  msgDiv.style.top = "50%";
  msgDiv.style.left = "50%";
  msgDiv.style.transform = "translate(-50%, -50%)";
  msgDiv.style.backgroundColor = "rgba(255,0,0,0.8)";
  msgDiv.style.color = "#fff";
  msgDiv.style.padding = "20px";
  msgDiv.style.fontSize = "30px";
  msgDiv.style.zIndex = 9999;
  msgDiv.textContent = "DISQUALIFIED";
  document.body.appendChild(msgDiv);

  // Remove after 5 seconds (optional)
  setTimeout(() => {
    msgDiv.remove();
  }, 5000);
});

/****************************************************
 * NEW: "active_investigation" overlay
 ****************************************************/
const investigationImg = document.getElementById('investigationImage');

// Show an image in the center until told to stop
socket.on("start_investigation", (data) => {
  console.log("start_investigation =>", data);
  const { image_url } = data;
  if (image_url) {
    investigationImg.src = image_url;
    investigationImg.style.display = 'block';
  }
});

// Fade out / remove that image
socket.on("stop_investigation", () => {
  console.log("stop_investigation");
  if (investigationImg.style.display !== 'none') {
    investigationImg.style.display = 'none';
    investigationImg.src = '';
  }
});

/****************************************************
 * Watermill Scrolling Logic
 ****************************************************/

const canvas = document.getElementById("feedCanvas");
const ctx = canvas.getContext("2d");

const IMAGE_WIDTH = 256;
const IMAGE_HEIGHT = 128;
const RECT_SPACING = 5; 
const SPEED = 1;
const STROBE_DURATION = 700;
const STROBE_FREQUENCY = 20;
const STROBE_OPACITY = 0.5;
const FINAL_OPACITY = 0.8;

const MARKING_LINE_POSITION = canvas.height - 90;

const imageCache = {};
let activeCoins = [];
let nextSpawnY = -(IMAGE_HEIGHT + RECT_SPACING);

function tryToStartNextBundle() {
  if (!currentBundleId) {
    const next = bundleQueue.find(b => b.ready);
    if (next) {
      currentBundleId = next.bundle_id;
      startBundleDisplay(next);
    }
  }
}

function finishCurrentBundle() {
  const idx = bundleQueue.findIndex(b => b.bundle_id === currentBundleId);
  if (idx !== -1) {
    bundleQueue.splice(idx, 1);
  }
  currentBundleId = null;
  tryToStartNextBundle();
}

function startBundleDisplay(bundle) {
  console.log("Starting bundle display:", bundle.bundle_id);

  if (!decisionsStore[bundle.bundle_id]) {
    decisionsStore[bundle.bundle_id] = {};
  }

  let loadCount = 0;
  const totalToLoad = bundle.coins.length;

  function spawnCoins() {
    bundle.coins.forEach((coin) => {
      const localDecision = decisionsStore[bundle.bundle_id][coin.id] || null;
      activeCoins.push(createCoinInstance(
        coin.url,
        coin.id,
        bundle.bundle_id,
        localDecision
      ));
    });
  }

  bundle.coins.forEach(coin => {
    if (imageCache[coin.url]) {
      loadCount++;
      if (loadCount === totalToLoad) spawnCoins();
    } else {
      const img = new Image();
      img.src = coin.url;
      img.onload = () => {
        imageCache[coin.url] = img;
        loadCount++;
        if (loadCount === totalToLoad) spawnCoins();
      };
      img.onerror = () => {
        console.error("Failed to load image:", coin.url);
        imageCache[coin.url] = null;
        loadCount++;
        if (loadCount === totalToLoad) spawnCoins();
      };
    }
  });
}

function createCoinInstance(url, coinId, bundleId, decision) {
  const instance = {
    bundleId,
    coinId,
    url,
    x: (canvas.width - IMAGE_WIDTH) / 2,
    y: nextSpawnY,
    opacity: 0,
    isStrobing: false,
    strobeStart: 0,
    finalOverlay: null,
    decision,

    fadeInDistance: IMAGE_HEIGHT * 1.5,
    fadeOutDistance: IMAGE_HEIGHT * 1.5
  };
  
  nextSpawnY -= (IMAGE_HEIGHT + RECT_SPACING);
  return instance;
}

function animate(time) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (activeCoins.length > 0) {
    activeCoins.forEach((coin) => {
      coin.y += SPEED;

      if (!coin.decision) {
        const d = decisionsStore[coin.bundleId][coin.coinId];
        if (d) coin.decision = d;
      }

      if (coin.y > -coin.fadeInDistance && coin.y < 0) {
        const ratio = 1 - Math.abs(coin.y / coin.fadeInDistance);
        coin.opacity = Math.max(0, Math.min(1, ratio));
      } else if (coin.y >= 0) {
        coin.opacity = 1;
      }

      const bottomEdge = coin.y + IMAGE_HEIGHT;
      if (bottomEdge > (canvas.height - coin.fadeOutDistance)) {
        const distFromTrigger = (canvas.height - bottomEdge);
        const ratio = 1 + (distFromTrigger / coin.fadeOutDistance);
        coin.opacity = Math.max(0, Math.min(coin.opacity, ratio));
      }

      if (!coin.isStrobing && (coin.y + IMAGE_HEIGHT) >= MARKING_LINE_POSITION) {
        coin.isStrobing = true;
        coin.strobeStart = time;
      }

      if (coin.isStrobing && !coin.finalOverlay) {
        const elapsed = time - coin.strobeStart;
        if (elapsed < STROBE_DURATION) {
          const freqPhase = Math.floor((elapsed / 1000) * STROBE_FREQUENCY) % 2;
          coin.currentOverlay = freqPhase === 0
            ? `rgba(255,0,0,${STROBE_OPACITY})`
            : `rgba(0,255,0,${STROBE_OPACITY})`;
        } else {
          if (coin.decision === "yes") {
            coin.finalOverlay = `rgba(0,255,0,${FINAL_OPACITY})`;
          } else if (coin.decision === "no") {
            coin.finalOverlay = `rgba(255,0,0,${FINAL_OPACITY})`;
          } else {
            coin.finalOverlay = `rgba(255,0,0,${FINAL_OPACITY})`;
          }
          coin.currentOverlay = coin.finalOverlay;
        }
      } else if (coin.finalOverlay) {
        coin.currentOverlay = coin.finalOverlay;
      } else {
        coin.currentOverlay = null;
      }
    });

    activeCoins.forEach((coin) => {
      if (!imageCache[coin.url]) return;

      ctx.save();
      ctx.globalAlpha = coin.opacity;
      ctx.drawImage(imageCache[coin.url], coin.x, coin.y, IMAGE_WIDTH, IMAGE_HEIGHT);

      if (coin.currentOverlay) {
        ctx.fillStyle = coin.currentOverlay;
        ctx.fillRect(coin.x, coin.y, IMAGE_WIDTH, IMAGE_HEIGHT);
      }
      ctx.restore();
    });

    while (activeCoins.length && activeCoins[0].y > canvas.height) {
      activeCoins.shift();
    }

    const anyActiveFromCurrentBundle = activeCoins.some(c => c.bundleId === currentBundleId);
    if (!anyActiveFromCurrentBundle && currentBundleId) {
      console.log("All coins from bundle", currentBundleId, "scrolled away. Finishing bundle.");
      finishCurrentBundle();
    }
  }

  requestAnimationFrame(animate);
}

requestAnimationFrame(animate);
