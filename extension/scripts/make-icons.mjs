// 拡張アイコン(16/48/128px)をSVGからPNGに書き出す。デザインを変えたら npm run icons で再生成してコミットする
import { chromium } from "playwright";
import path from "node:path";
import { fileURLToPath } from "node:url";

const OUT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "icons");

// サイトと同じ配色: 紺地に金の地球+円マーク
const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect width="128" height="128" rx="28" fill="#0B0E17"/>
  <circle cx="64" cy="64" r="44" fill="none" stroke="#D4A843" stroke-width="8"/>
  <ellipse cx="64" cy="64" rx="18" ry="44" fill="none" stroke="#D4A843" stroke-width="6"/>
  <line x1="20" y1="64" x2="108" y2="64" stroke="#D4A843" stroke-width="6"/>
  <circle cx="96" cy="96" r="26" fill="#EBCB7A"/>
  <text x="96" y="106" font-size="30" font-weight="700" text-anchor="middle"
    font-family="Arial, sans-serif" fill="#0B0E17">¥</text>
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
