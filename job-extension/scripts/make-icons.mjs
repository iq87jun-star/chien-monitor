// 拡張アイコン(16/48/128px)をSVGからPNGに書き出す。デザインを変えたら npm run icons で再生成してコミットする
import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "icons");

// 求人票と円マークのアイコン(緑地)
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect width="128" height="128" rx="28" fill="#0f766e"/>
  <rect x="24" y="30" width="80" height="68" rx="10" fill="#fff"/>
  <rect x="36" y="44" width="36" height="7" rx="3.5" fill="#99f6e4"/>
  <rect x="36" y="58" width="56" height="7" rx="3.5" fill="#99f6e4"/>
  <rect x="36" y="72" width="44" height="7" rx="3.5" fill="#99f6e4"/>
  <circle cx="96" cy="96" r="26" fill="#fbbf24"/>
  <text x="96" y="106" font-size="30" font-weight="700" text-anchor="middle"
    font-family="Arial, sans-serif" fill="#0f766e">¥</text>
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
