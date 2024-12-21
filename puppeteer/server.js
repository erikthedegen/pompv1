// File: puppeteer/server.js

import express from "express";
import dotenv from "dotenv";
import path from "path";
import { fileURLToPath } from "url";
import fs from "fs";
import validator from "validator";
import axios from "axios";
import PuppeteerController from "./controllers/puppeteerController.js";

dotenv.config();

const { isURL } = validator;

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;
const USER_DATA_DIR = process.env.USER_DATA_DIR || "./puppeteer_data";

const WATERMILL_FLASK_URL = process.env.WATERMILL_FLASK_URL || "http://localhost:5000";

app.use(express.json());
app.use(express.static(path.join(__dirname, "public")));
app.use("/screenshots", express.static(path.join(__dirname, "screenshots")));

const puppeteerController = new PuppeteerController({ userDataDir: USER_DATA_DIR });
puppeteerController.init().catch((error) => {
  console.error("Failed to initialize Puppeteer:", error);
  process.exit(1);
});

app.post("/api/process", async (req, res) => {
  const { url } = req.body;
  if (!url || typeof url !== "string" || !isURL(url, { protocols: ["http", "https"], require_protocol: true })) {
    return res.status(400).json({ success: false, message: "Invalid URL provided." });
  }

  try {
    let localScreenshotPath;
    if (url.includes("twitter.com") || url.includes("x.com")) {
      localScreenshotPath = await puppeteerController.takeTwitterScreenshot(url);
    } else {
      localScreenshotPath = await puppeteerController.searchWithImage(url);
    }

    if (!localScreenshotPath) {
      return res.status(500).json({ success: false, message: "Screenshot failed." });
    }

    return res.status(200).json({ success: true, screenshotUrl: localScreenshotPath });
  } catch (error) {
    console.error(`Error processing URL ${url}:`, error);
    return res.status(500).json({ success: false, message: error.message });
  }
});

async function uploadScreenshotLens(localFilePath, remoteFileName) {
  try {
    const fileBuffer = fs.readFileSync(localFilePath);
    const base64Data = fileBuffer.toString("base64");

    const response = await axios.post(
      `${WATERMILL_FLASK_URL}/upload_screenshot_lens`,
      {
        base64: base64Data,
        filename: remoteFileName,
      },
      { timeout: 60000 }
    );
    if (response.data && response.data.success) {
      return response.data.cloudflareUrl;
    } else {
      console.error("uploadScreenshotLens: Upload failed:", response.data);
      return null;
    }
  } catch (err) {
    console.error("Error in uploadScreenshotLens:", err);
    return null;
  }
}

app.post("/api/lens-screenshot", async (req, res) => {
  try {
    const { imageUrl } = req.body;
    if (!imageUrl || !isURL(imageUrl)) {
      return res.status(400).json({ success: false, message: "Invalid imageUrl." });
    }

    const localScreenshotPath = await puppeteerController.searchWithImage(imageUrl);
    if (!localScreenshotPath) {
      return res.status(500).json({ success: false, message: "Failed to take lens screenshot." });
    }

    const absolutePath = path.join(__dirname, localScreenshotPath);
    const remoteFileName = `lens_${Date.now()}.png`;
    const finalUrl = await uploadScreenshotLens(absolutePath, remoteFileName);
    if (!finalUrl) {
      return res.status(500).json({ success: false, message: "Cloudflare lens upload failed." });
    }

    return res.status(200).json({ success: true, cloudflareUrl: finalUrl });
  } catch (error) {
    console.error("Error in /api/lens-screenshot:", error);
    return res.status(500).json({ success: false, message: error.message });
  }
});

app.post("/api/twitter-screenshot", async (req, res) => {
  try {
    const { twitterUrl } = req.body;
    if (!twitterUrl || !isURL(twitterUrl)) {
      return res.status(400).json({ success: false, message: "Invalid twitterUrl." });
    }

    const localScreenshotPath = await puppeteerController.takeTwitterScreenshot(twitterUrl);
    if (!localScreenshotPath) {
      return res.status(500).json({ success: false, message: "Failed to take twitter screenshot." });
    }

    const absolutePath = path.join(__dirname, localScreenshotPath);
    const remoteFileName = `twitter_${Date.now()}.png`;
    const finalUrl = await uploadScreenshotLens(absolutePath, remoteFileName);
    if (!finalUrl) {
      return res.status(500).json({ success: false, message: "Cloudflare lens upload failed." });
    }

    return res.status(200).json({ success: true, cloudflareUrl: finalUrl });
  } catch (error) {
    console.error("Error in /api/twitter-screenshot:", error);
    return res.status(500).json({ success: false, message: error.message });
  }
});

// The routes below remain (but the front-end no longer uses them).
app.post("/api/start-recording", (req, res) => {
  puppeteerController.startScreenRecording();
  return res.status(200).json({ success: true, message: "Screen recording started." });
});

app.post("/api/stop-recording", (req, res) => {
  puppeteerController.stopScreenRecording();
  return res.status(200).json({ success: true, message: "Screen recording stopped." });
});

app.get("*", (req, res) => {
  res.sendFile(path.join(__dirname, "public", "index.html"));
});

const gracefulShutdown = () => {
  console.log("\nShutting down gracefully...");
  puppeteerController
    .close()
    .then(() => {
      process.exit(0);
    })
    .catch((error) => {
      console.error("Error during shutdown:", error);
      process.exit(1);
    });
};

process.on("SIGINT", gracefulShutdown);
process.on("SIGTERM", gracefulShutdown);

app.listen(PORT, () => {
  console.log(`Server is running on http://localhost:${PORT}`);
});
