// 拡張アイコン(16/48/128px)をSVGからPNGに書き出す。デザインを変えたら npm run icons で再生成してコミットする
import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "icons");

// 家と円マークのアイコン(青地)
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect width="128" height="128" rx="28" fill="#1d4ed8"/>
  <path d="M24 62 L64 28 L104 62 L104 100 L24 100 Z" fill="#fff"/>
  <rect x="52" y="72" width="24" height="28" rx="3" fill="#93c5fd"/>
  <circle cx="96" cy="96" r="26" fill="#fbbf24"/>
  <text x="96" y="106" font-size="30" font-weight="700" text-anchor="middle"
    font-family="Arial, sans-serif" fill="#1d4ed8">¥</text>
</svg>`;

const browser = await chromium.launch();
const page = await browser.newPage();
for (const size of [16, 48, 128]) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(
    `<style>html,body{margin:0;background:transparent}</style>` +
      svg.replace("<svg ", `<svg width="${size}" height="${size}" `),
  );
  await page.screenshot({ path: path.join(OUT, `icon${size}.png`), omitBackground: true });
}
await browser.close();
console.log("icons written to", OUT);
