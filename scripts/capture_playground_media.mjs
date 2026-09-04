import { chromium } from 'playwright';
import fs from 'node:fs/promises';
import path from 'node:path';

const SITE = 'https://bytetoken-playground-kcwc.vercel.app/';
const OUT = path.resolve('docs/media');
const TMP = path.resolve('.capture-video');
const VIEWPORT = { width: 1364, height: 680 };
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

await fs.mkdir(OUT, { recursive: true });
await fs.rm(TMP, { recursive: true, force: true });
await fs.mkdir(TMP, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: VIEWPORT,
  recordVideo: { dir: TMP, size: VIEWPORT },
  colorScheme: 'dark',
});
const page = await context.newPage();
const video = page.video();

try {
  await page.goto(SITE, { waitUntil: 'networkidle', timeout: 120_000 });
  await page.waitForSelector('#analyzeButton', { state: 'visible', timeout: 30_000 });
  await sleep(2500);

  // Shot 1: live hero, scope chips, and public GitHub/Paper links.
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(700);
  await page.screenshot({ path: path.join(OUT, '01_hero_and_paper_links.png') });

  // Reproduce the same public JSON/o200k_base path used by the launch demo.
  await page.click('[data-example="json"]');
  await page.selectOption('#tokenizer', 'o200k_base');
  await sleep(1800);
  await page.click('#analyzeButton');
  await page.waitForFunction(
    () => document.querySelector('#status')?.textContent?.includes('Measured'),
    { timeout: 120_000 },
  );
  await page.waitForFunction(
    () => !document.querySelector('#results')?.classList.contains('hidden'),
    { timeout: 30_000 },
  );
  await sleep(3500);

  // Shot 2: measured transport cards and byte-for-byte verification state.
  await page.locator('#results').scrollIntoViewIfNeeded();
  await sleep(1200);
  await page.screenshot({ path: path.join(OUT, '02_measured_transport_comparison.png') });
  await sleep(3500);

  // Shot 3: compression is deliberately displayed as a separate layer.
  await page.locator('.compression-grid').scrollIntoViewIfNeeded();
  await sleep(1200);
  await page.screenshot({ path: path.join(OUT, '03_compression_and_scope.png') });
  await sleep(3500);

  // Finish the recording back at the public GitHub/Paper links.
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'smooth' }));
  await sleep(3500);
} finally {
  await page.close();
  await context.close();
  await browser.close();
}

if (!video) throw new Error('Playwright did not create a video recording.');
const recorded = await video.path();
await fs.copyFile(recorded, path.join(OUT, 'bytetoken-playground-demo.webm'));

console.log(`Captured ByteToken Playground at ${VIEWPORT.width}x${VIEWPORT.height}`);
console.log('Screenshots and browser recording written to docs/media/.');
