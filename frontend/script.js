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

/**
 * Attempt to start the next bundle if we're not currently displaying one.
 */
function tryToStartNextBundle() {
  if (!currentBundleId) {
    const next = bundleQueue.find(b => b.ready);
    if (next) {
      currentBundleId = next.bundle_id;
      startBundleDisplay(next);
    }
  }
}

/**
 * Once a bundle is fully scrolled off, remove it from queue and reset current.
 */
function finishCurrentBundle() {
  const idx = bundleQueue.findIndex(b => b.bundle_id === currentBundleId);
  if (idx !== -1) {
    bundleQueue.splice(idx, 1);
  }
  currentBundleId = null;
  tryToStartNextBundle();
}

/****************************************************
 * Watermill Scrolling Logic
 ****************************************************/

const canvas = document.getElementById("feedCanvas");
const ctx = canvas.getContext("2d");

// Basic constants (mimicking your reference sweriko-watermill)
const IMAGE_WIDTH = 256;
const IMAGE_HEIGHT = 128;
const RECT_SPACING = 5; // gap between images if we spawn them rapidly
const SPEED = 1;        // vertical speed (px per frame)
const STROBE_DURATION = 700;  // ms
const STROBE_FREQUENCY = 20;  // times per second
const STROBE_OPACITY = 0.5;
const FINAL_OPACITY = 0.8;

// The vertical line where strobe triggers (like in reference code)
const MARKING_LINE_POSITION = canvas.height - 90;

// We'll store loaded images in a cache: { url: HTMLImageElement }
const imageCache = {};

// The active images on screen at any one time
let activeCoins = [];

// Where the next coin spawns (so we can space them out a bit)
let nextSpawnY = -(IMAGE_HEIGHT + RECT_SPACING);

/**
 * Called once a bundle is ready: we spawn its coins into our scroller.
 */
function startBundleDisplay(bundle) {
  console.log("Starting bundle display:", bundle.bundle_id);

  // If we haven't stored decisions for this bundle yet, create a blank object
  if (!decisionsStore[bundle.bundle_id]) {
    decisionsStore[bundle.bundle_id] = {};
  }

  // Preload images
  let loadCount = 0;
  const totalToLoad = bundle.coins.length;

  function spawnCoins() {
    bundle.coins.forEach((coin, index) => {
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
      // Already loaded or attempted load
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

/**
 * Create a coin instance to animate. 
 * Y position is spaced so they appear one after another.
 */
function createCoinInstance(url, coinId, bundleId, decision) {
  const instance = {
    bundleId,
    coinId,
    url,
    x: (canvas.width - IMAGE_WIDTH) / 2, // center
    y: nextSpawnY,
    opacity: 0,
    isStrobing: false,
    strobeStart: 0,
    finalOverlay: null,
    decision: decision, // "yes" or "no" or null

    // We'll fade in from top region
    fadeInDistance: IMAGE_HEIGHT * 1.5,
    // We'll fade out near the bottom
    fadeOutDistance: IMAGE_HEIGHT * 1.5
  };
  
  // Update nextSpawnY so the next coin spawns a bit above the current
  nextSpawnY -= (IMAGE_HEIGHT + RECT_SPACING);

  return instance;
}

/**
 * Main animation loop: updates positions, handles strobe logic, draws coins.
 */
function animate(time) {
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (activeCoins.length > 0) {
    activeCoins.forEach((coin) => {
      // Move downward
      coin.y += SPEED;

      // Possibly refresh coin.decision if server data arrived after creation
      if (!coin.decision) {
        const d = decisionsStore[coin.bundleId][coin.coinId];
        if (d) coin.decision = d;
      }

      // Fade in at top
      if (coin.y > -coin.fadeInDistance && coin.y < 0) {
        // e.g. if coin.y = -coin.fadeInDistance => opacity=0
        // coin.y=0 => opacity=1
        const ratio = 1 - Math.abs(coin.y / coin.fadeInDistance);
        coin.opacity = Math.max(0, Math.min(1, ratio));
      } else if (coin.y >= 0) {
        // fully visible until we start fade out
        coin.opacity = 1;
      }

      // Fade out near bottom
      const bottomEdge = coin.y + IMAGE_HEIGHT;
      if (bottomEdge > (canvas.height - coin.fadeOutDistance)) {
        const distFromTrigger = (canvas.height - bottomEdge);
        // e.g. bottomEdge=canvas.height => distFromTrigger=0 => opacity=0
        // bottomEdge=canvas.height - coin.fadeOutDistance => distFromTrigger= -fadeOutDistance => opacity=1
        const ratio = 1 + (distFromTrigger / coin.fadeOutDistance);
        coin.opacity = Math.max(0, Math.min(coin.opacity, ratio));
      }

      // Strobe trigger
      if (!coin.isStrobing && (coin.y + IMAGE_HEIGHT) >= MARKING_LINE_POSITION) {
        coin.isStrobing = true;
        coin.strobeStart = time;
      }

      // If strobing, handle strobe
      if (coin.isStrobing && !coin.finalOverlay) {
        const elapsed = time - coin.strobeStart;
        if (elapsed < STROBE_DURATION) {
          // strobe
          const freqPhase = Math.floor((elapsed / 1000) * STROBE_FREQUENCY) % 2;
          coin.currentOverlay = freqPhase === 0
            ? `rgba(255,0,0,${STROBE_OPACITY})`
            : `rgba(0,255,0,${STROBE_OPACITY})`;
        } else {
          // end strobe -> fix final color
          if (coin.decision === "yes") {
            coin.finalOverlay = `rgba(0,255,0,${FINAL_OPACITY})`;
          } else if (coin.decision === "no") {
            coin.finalOverlay = `rgba(255,0,0,${FINAL_OPACITY})`;
          } else {
            // If still no decision, default red
            coin.finalOverlay = `rgba(255,0,0,${FINAL_OPACITY})`;
          }
          coin.currentOverlay = coin.finalOverlay;
        }
      } else if (coin.finalOverlay) {
        // maintain final color after strobe
        coin.currentOverlay = coin.finalOverlay;
      } else {
        coin.currentOverlay = null;
      }
    });

    // Draw coins in front -> back order
    activeCoins.forEach((coin) => {
      if (!imageCache[coin.url]) return; // skip if not loaded

      ctx.save();
      ctx.globalAlpha = coin.opacity;
      ctx.drawImage(imageCache[coin.url], coin.x, coin.y, IMAGE_WIDTH, IMAGE_HEIGHT);

      if (coin.currentOverlay) {
        ctx.fillStyle = coin.currentOverlay;
        ctx.fillRect(coin.x, coin.y, IMAGE_WIDTH, IMAGE_HEIGHT);
      }
      ctx.restore();
    });

    // Remove coins that have fully passed the bottom or are at opacity 0
    while (activeCoins.length && activeCoins[0].y > canvas.height) {
      activeCoins.shift();
    }

    // If no coin from the currentBundleId is left on screen => done
    const anyActiveFromCurrentBundle = activeCoins.some(c => c.bundleId === currentBundleId);
    if (!anyActiveFromCurrentBundle && currentBundleId) {
      console.log("All coins from bundle", currentBundleId, "scrolled away. Finishing bundle.");
      finishCurrentBundle();
    }
  }

  requestAnimationFrame(animate);
}

// Start the animation loop
requestAnimationFrame(animate);
