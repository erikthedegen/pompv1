// File: puppeteer/controllers/puppeteerController.js

import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { spawn } from 'child_process';

// For __dirname in ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

puppeteer.use(StealthPlugin());

class PuppeteerController {
  constructor(options) {
    this.userDataDir = options.userDataDir;
    this.browser = null;
    this.page = null;
    this.ffmpegProcess = null;
  }

  async init() {
    this.browser = await puppeteer.launch({
      headless: false,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--window-position=3440,0',
        '--window-size=1920,1080'
      ],
      userDataDir: this.userDataDir
    });

    const context = this.browser.defaultBrowserContext();
    await context.overridePermissions('https://lens.google.com', [
      'clipboard-read',
      'clipboard-write',
    ]);

    const pages = await this.browser.pages();
    this.page = pages.length > 0 ? pages[0] : await this.browser.newPage();
    await this.page.setViewport({ width: 1920, height: 1080 });

    // Set a user-agent
    await this.page.setUserAgent(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    );

    console.log(
      'Puppeteer initialized. Please log into Twitter (X) if you plan to screenshot tweets.'
    );

    try {
      await this.waitForLogin();
      console.log('Twitter login confirmed.');
    } catch (err) {
      console.log('Twitter login not detected; you can still do image-based tasks.');
    }

    // Automatically start screen recording on startup
    this.startScreenRecording();
  }

  async waitForLogin(timeout = 60000) {
    console.log('Attempting to verify Twitter login...');
    await this.page.goto('https://twitter.com/home', { waitUntil: 'networkidle2' });
    await this.page.waitForSelector('div[data-testid="primaryColumn"]', { timeout });
    console.log('Twitter login confirmed.');
  }

  async takeTwitterScreenshot(url) {
    console.log(`Processing Twitter URL: ${url}`);

    const newPage = await this.browser.newPage();
    await newPage.setViewport({ width: 1920, height: 1080 });
    await newPage.setUserAgent(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    );
    await newPage.goto(url, { waitUntil: 'networkidle2' });

    // Wait a bit for the page to stabilize
    await new Promise((resolve) => setTimeout(resolve, 3000));

    const screenshotsDir = path.join(__dirname, '..', 'screenshots');
    if (!fs.existsSync(screenshotsDir)) {
      fs.mkdirSync(screenshotsDir);
    }

    const filename = `screenshot_twitter_${Date.now()}.png`;
    const filepath = path.join(screenshotsDir, filename);
    await newPage.screenshot({ path: filepath, fullPage: false });
    await newPage.close();

    console.log(`Twitter screenshot saved as ${filepath}`);
    // Return the relative path for convenience
    return `/screenshots/${filename}`;
  }

  async searchWithImage(imageUrl) {
    console.log(`Processing image URL for Google Lens: ${imageUrl}`);

    // Open the image URL in a new tab
    const imagePage = await this.browser.newPage();
    await imagePage.goto(imageUrl, { waitUntil: 'networkidle2' });

    // Copy the image to clipboard
    await imagePage.click('body');
    await imagePage.keyboard.down('Control');
    await imagePage.keyboard.press('C');
    await imagePage.keyboard.up('Control');
    console.log('Image copied to clipboard.');

    await imagePage.close();

    // Open Google Lens
    await this.page.goto('https://lens.google.com/search?p', { waitUntil: 'networkidle2' });
    await new Promise((resolve) => setTimeout(resolve, 200));

    // Paste the image
    await this.page.click('body');
    await this.page.keyboard.down('Control');
    await this.page.keyboard.press('V');
    await this.page.keyboard.up('Control');
    console.log('Image pasted into Google Lens. Waiting for results...');

    // Wait for results
    await new Promise((resolve) => setTimeout(resolve, 3000));

    const screenshotDir = path.join(__dirname, '..', 'screenshots');
    if (!fs.existsSync(screenshotDir)) {
      fs.mkdirSync(screenshotDir);
    }

    const filename = `screenshot_lens_${Date.now()}.png`;
    const screenshotPath = path.join(screenshotDir, filename);
    await this.page.screenshot({ path: screenshotPath });
    console.log(`Google Lens screenshot saved: ${screenshotPath}`);

    return `/screenshots/${filename}`;
  }

  startScreenRecording() {
    if (this.ffmpegProcess) {
      console.log('Screen recording is already in progress.');
      return;
    }

    // Example ffmpeg command for Windows entire desktop
    const ffmpegArgs = [
      '-f', 'gdigrab',
      '-framerate', '30',
      '-offset_x', '3440',
      '-offset_y', '0',
      '-video_size', '1920x1080',
      '-i', 'desktop',
      '-vcodec', 'libx264',
      '-preset', 'veryfast',
      '-tune', 'zerolatency',
      '-pix_fmt', 'yuv420p',
      '-f', 'flv',
      'rtmp://localhost:1935/live/streamkey'
    ];

    this.ffmpegProcess = spawn('ffmpeg', ffmpegArgs, { stdio: 'pipe' });

    this.ffmpegProcess.on('error', (err) => {
      console.error('Failed to start ffmpeg:', err);
      this.ffmpegProcess = null;
    });

    this.ffmpegProcess.stderr.on('data', (data) => {
      console.log(`ffmpeg: ${data}`);
    });

    this.ffmpegProcess.on('close', (code) => {
      console.log(`ffmpeg exited with code ${code}`);
      this.ffmpegProcess = null;
    });

    console.log('Screen recording started.');
  }

  stopScreenRecording() {
    if (this.ffmpegProcess) {
      this.ffmpegProcess.stdin.write('q');
      this.ffmpegProcess.kill('SIGINT');
      this.ffmpegProcess = null;
      console.log('Screen recording stopped.');
    } else {
      console.log('No screen recording is active.');
    }
  }

  async close() {
    if (this.browser) {
      await this.browser.close();
      console.log('Browser closed.');
    }
  }
}

// This is crucial for ES module default import:
export default PuppeteerController;
