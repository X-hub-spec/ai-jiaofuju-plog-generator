#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

function usage() {
  console.error("Usage: export_pages.mjs <index.html|url> <output-dir>");
  process.exit(2);
}

const input = process.argv[2];
const outputDir = process.argv[3];
if (!input || !outputDir) usage();

const target = /^https?:\/\//.test(input) || input.startsWith("file://")
  ? input
  : pathToFileURL(path.resolve(input)).href;

fs.mkdirSync(outputDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1400, height: 2300 }, deviceScaleFactor: 1 });
await page.goto(target, { waitUntil: "load" });
await page.evaluate(() => document.fonts && document.fonts.ready);

const pages = await page.locator(".page").count();
if (pages === 0) {
  await browser.close();
  throw new Error("No .page elements found.");
}

for (let i = 0; i < pages; i += 1) {
  const locator = page.locator(".page").nth(i);
  await locator.screenshot({
    path: path.join(outputDir, `page-${String(i + 1).padStart(2, "0")}.png`)
  });
}

const result = await page.evaluate(() => ({
  pageCount: document.querySelectorAll(".page").length,
  images: [...document.images].map((img) => ({
    src: img.getAttribute("src"),
    ok: img.complete && img.naturalWidth > 0
  }))
}));

await browser.close();
console.log(JSON.stringify({
  outputDir: path.resolve(outputDir),
  ...result
}, null, 2));
