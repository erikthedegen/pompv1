// File: /pompv1/frontend/script.js

/****************************************************
 * Socket.io + Bundles/Decisions (Watermill Feed)
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

// NEW listener for disqualified (or "pass") coins
socket.on("disqualified_coin", (data) => {
  console.log("Received disqualified_coin:", data);

  // Interpret "disqualified_coin" as a "PASS" scenario
  createPassOverlay(); 
  // For "buy" scenarios, you can emit a different event and handle similarly
});

/****************************************************
 * NEW: "active_investigation" logic - separate canvas
 ****************************************************/

// Grab the investigation canvas and context
const investigationCanvas = document.getElementById('investigationCanvas');
const invCtx = investigationCanvas.getContext('2d');

// We'll keep an in-memory image that we draw into this canvas.
let investigationImage = null;
// We'll track if a fade-out is in progress for the overlay
let overlayAlpha = 0;
let overlayAnimating = false;
let overlayType = null; // "pass" or "buy"

socket.on("start_investigation", (data) => {
  console.log("start_investigation =>", data);
  const { image_url } = data;
  if (image_url) {
    // Load image
    investigationImage = new Image();
    investigationImage.src = image_url;
    investigationImage.onload = () => {
      // Make the canvas visible
      investigationCanvas.style.display = 'block';
      // Reset any overlays
      overlayAlpha = 0;
      overlayAnimating = false;
      overlayType = null;
      // Draw the coin
      drawInvestigation();
    };
  }
});

socket.on("stop_investigation", () => {
  console.log("stop_investigation");
  // Fade out the overlay and then hide the canvas
  if (overlayType) {
    overlayAnimating = true;
  } else {
    // No overlay to fade out, simply hide
    investigationCanvas.style.display = 'none';
    invCtx.clearRect(0, 0, investigationCanvas.width, investigationCanvas.height);
    investigationImage = null;
  }
});

/**
 * Render loop for the investigation canvas.
 */
function drawInvestigation() {
  // Clear
  invCtx.clearRect(0, 0, investigationCanvas.width, investigationCanvas.height);

  if (investigationImage) {
    // Draw the coin image at its natural size
    invCtx.drawImage(investigationImage, 0, 0, 256, 128);
  }

  // If there's a pass/buy overlay in progress, draw it
  if (overlayType && overlayAlpha < 1) {
    overlayAlpha += 0.02; // speed of fade in
    if (overlayAlpha > 1) {
      overlayAlpha = 1;
    }
  }

  if (overlayType) {
    invCtx.save();
    invCtx.globalAlpha = overlayAlpha;

    if (overlayType === "pass") {
      // Dim black overlay
      invCtx.fillStyle = "rgba(0,0,0,0.7)";
      invCtx.fillRect(0, 0, investigationCanvas.width, investigationCanvas.height);
      // "PASS" in red
      invCtx.font = "bold 24px sans-serif";
      invCtx.fillStyle = "red";
      const text = "PASS";
      const textWidth = invCtx.measureText(text).width;
      const textX = (investigationCanvas.width - textWidth) / 2;
      const textY = (investigationCanvas.height / 2) + 8; 
      invCtx.fillText(text, textX, textY);

    } else if (overlayType === "buy") {
      // Green overlay
      invCtx.fillStyle = "rgba(0,128,0,0.8)";
      invCtx.fillRect(0, 0, investigationCanvas.width, investigationCanvas.height);
      // "BOUGHT" in white
      invCtx.font = "bold 24px sans-serif";
      invCtx.fillStyle = "white";
      const text = "BOUGHT";
      const textWidth = invCtx.measureText(text).width;
      const textX = (investigationCanvas.width - textWidth) / 2;
      const textY = (investigationCanvas.height / 2) + 8; 
      invCtx.fillText(text, textX, textY);
    }

    invCtx.restore();
  }

  // If overlay is animating (fading out)
  if (overlayAnimating) {
    if (overlayAlpha > 0) {
      overlayAlpha -= 0.02; // speed of fade out
      if (overlayAlpha < 0) {
        overlayAlpha = 0;
      }
      // Redraw with updated alpha
      if (investigationImage) {
        invCtx.drawImage(investigationImage, 0, 0, 256, 128);
      }
      if (overlayAlpha > 0) {
        invCtx.save();
        invCtx.globalAlpha = overlayAlpha;

        if (overlayType === "pass") {
          // Dim black overlay
          invCtx.fillStyle = "rgba(0,0,0,0.7)";
          invCtx.fillRect(0, 0, investigationCanvas.width, investigationCanvas.height);
          // "PASS" in red
          invCtx.font = "bold 24px sans-serif";
          invCtx.fillStyle = "red";
          const text = "PASS";
          const textWidth = invCtx.measureText(text).width;
          const textX = (investigationCanvas.width - textWidth) / 2;
          const textY = (investigationCanvas.height / 2) + 8; 
          invCtx.fillText(text, textX, textY);

        } else if (overlayType === "buy") {
          // Green overlay
          invCtx.fillStyle = "rgba(0,128,0,0.8)";
          invCtx.fillRect(0, 0, investigationCanvas.width, investigationCanvas.height);
          // "BOUGHT" in white
          invCtx.font = "bold 24px sans-serif";
          invCtx.fillStyle = "white";
          const text = "BOUGHT";
          const textWidth = invCtx.measureText(text).width;
          const textX = (investigationCanvas.width - textWidth) / 2;
          const textY = (investigationCanvas.height / 2) + 8; 
          invCtx.fillText(text, textX, textY);
        }

        invCtx.restore();
      }
    } else {
      // Overlay fully faded out, hide canvas
      overlayAnimating = false;
      overlayType = null;
      investigationCanvas.style.display = 'none';
      invCtx.clearRect(0, 0, investigationCanvas.width, investigationCanvas.height);
      investigationImage = null;
    }
  }

  requestAnimationFrame(drawInvestigation);
}

requestAnimationFrame(drawInvestigation);

/**
 * Called when we want a "PASS" overlay on the investigation canvas.
 */
function createPassOverlay() {
  overlayType = "pass";
  overlayAlpha = 0;
  overlayAnimating = false;
  // Overlay will fade in and then fade out after a delay
  setTimeout(() => {
    overlayAnimating = true;
  }, 3000);
}

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

      // Fade in
      if (coin.y > -coin.fadeInDistance && coin.y < 0) {
        const ratio = 1 - Math.abs(coin.y / coin.fadeInDistance);
        coin.opacity = Math.max(0, Math.min(1, ratio));
      } else if (coin.y >= 0) {
        coin.opacity = 1;
      }

      // Fade out near bottom
      const bottomEdge = coin.y + IMAGE_HEIGHT;
      if (bottomEdge > (canvas.height - coin.fadeOutDistance)) {
        const distFromTrigger = (canvas.height - bottomEdge);
        const ratio = 1 + (distFromTrigger / coin.fadeOutDistance);
        coin.opacity = Math.max(0, Math.min(coin.opacity, ratio));
      }

      // Strobing / final overlay logic
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

    // Remove coins that have scrolled fully off
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


/****************************************************
 * NEW: Balance Bar Logic
 ****************************************************/
const balanceBarCanvas = document.getElementById('balanceBarCanvas');
const balanceCtx = balanceBarCanvas.getContext('2d');

// We'll store the netBalance from the server here:
let currentNetBalance = 0.0;

// Listen for 'update_balance_bar' event from server
socket.on("update_balance_bar", (data) => {
  const { netbalance } = data;
  currentNetBalance = parseFloat(netbalance) || 0.0;
  drawBalanceBar();
});

function drawBalanceBar() {
  // Clear the entire canvas
  balanceCtx.clearRect(0, 0, balanceBarCanvas.width, balanceBarCanvas.height);

  const w = balanceBarCanvas.width;
  const h = balanceBarCanvas.height;

  // Outer black rectangle is the canvas itself (with a CSS border).
  // We'll define an "inner" bar area
  const barWidth = w * 0.8; // 80% of width for the "shell"
  const barHeight = 20;
  const barX = (w - barWidth) / 2;
  const barY = (h - barHeight) / 2;

  // Draw a black shell for the bar
  balanceCtx.strokeStyle = "black";
  balanceCtx.lineWidth = 2;
  balanceCtx.strokeRect(barX, barY, barWidth, barHeight);

  // Now compute fill length
  // 1 px = 1$ difference, and the center is barX for zero
  // If netBalance>0 => fill to the right in green
  // If netBalance<0 => fill to the left in red

  let fillLength = currentNetBalance; 
  // 1 px = $1, so if netBalance = 100 => fill 100 px to the right
  // if netBalance = -40 => fill 40 px to the left
  const maxFill = barWidth; // we won't clamp, but it can go beyond
  const fillHeight = barHeight;

  balanceCtx.save();

  if (fillLength > 0) {
    // Green fill to the right
    balanceCtx.fillStyle = "green";
    if (fillLength > maxFill) {
      fillLength = maxFill; // you can clamp if you'd like
    }
    balanceCtx.fillRect(barX, barY, fillLength, fillHeight);
  } else if (fillLength < 0) {
    // Red fill to the left
    balanceCtx.fillStyle = "red";
    const absLen = Math.abs(fillLength);
    let startX = barX; // left boundary of the bar
    if (absLen > barWidth) {
      fillLength = -barWidth; // clamp if you'd like
    }
    // We'll subtract from barX (the bar's left)
    startX = barX - absLen;
    balanceCtx.fillRect(startX, barY, absLen, fillHeight);
  }

  balanceCtx.restore();

  // Draw text in black in the middle
  balanceCtx.fillStyle = "black";
  balanceCtx.font = "14px Arial";
  let displayText = `Balance: ${currentNetBalance.toFixed(2)}$`;
  // Alternatively show percentage if you prefer
  // let displayText = currentNetBalance >= 0 
  //   ? `Balance: +${currentNetBalance.toFixed(2)}$` 
  //   : `Balance: ${currentNetBalance.toFixed(2)}$`;
  const textMetrics = balanceCtx.measureText(displayText);
  const textX = (w - textMetrics.width) / 2;
  const textY = barY + barHeight - 5; // near inside the bar
  balanceCtx.fillText(displayText, textX, textY);
}
