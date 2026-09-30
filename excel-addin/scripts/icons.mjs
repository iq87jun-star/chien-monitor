// アイコンを listing/ に作る(1回だけ実行して PNG を保存しておく。デザインを変える時だけ再実行)。
//   icon-16/32/64/80.png … アドインの定義・リボン用 / icon-300.png … AppSource の掲載用
// sheets-addon のアイコン(緑の表 + ¥)と同じデザインを SVG で描き、Chromium で PNG にする。
// playwright は依存に入れていない(ふだんは使わないため)。実行は `npm i --no-save playwright && node scripts/icons.mjs`
import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "listing");
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect x="4" y="4" width="120" height="120" rx="26" fill="#1d7a3e"/>
  <rect x="24" y="24" width="80" height="80" rx="8" fill="none" stroke="#fff" stroke-width="7"/>
  <path d="M24 50H104M24 76H64M50 24V104" stroke="#fff" stroke-width="7"/>
  <text x="85" y="101" font-family="Arial, sans-serif" font-weight="700" font-size="40" fill="#fff" text-anchor="middle">¥</text>
</svg>`;
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const page = await browser.newPage();
for (const size of [16, 32, 64, 80, 300]) {
  await page.setViewportSize({ width: size, height: size });
  await page.setContent(
    `<style>html,body{margin:0;background:transparent}</style><img src="data:image/svg+xml,${encodeURIComponent(svg)}" width="${size}" height="${size}">`,
  );
  await page.screenshot({ path: path.join(OUT, `icon-${size}.png`), omitBackground: true });
}
await browser.close();
console.log("icons written to listing/");
