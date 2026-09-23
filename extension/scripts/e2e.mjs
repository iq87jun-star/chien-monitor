// E2Eテスト: 実際のChromiumに拡張を読み込み、フリマサイト風の商品ページ(モック)で
// 相場バッジが出ることを確認する。あわせてストア掲載用スクリーンショット(1280x800)を
// store/screenshots/ に書き出す。外部サイトには接続しない(全リクエストをモックで応答)。
//   node scripts/e2e.mjs            … テストのみ
//   node scripts/e2e.mjs --shots    … テスト+スクリーンショット更新
import { chromium } from "playwright";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SHOTS_DIR = path.join(ROOT, "store", "screenshots");
const takeShots = process.argv.includes("--shots");
const fixture = await fs.readFile(path.join(ROOT, "test", "fixtures", "cards.json"), "utf8");

// 実サイトの構造に依存しない最小のモック(商品名は h1 から取る実装のため h1 だけ再現)
const mockPage = (title, price) => `<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<title>${title}</title>
<style>
  body{margin:0;font-family:'Noto Sans JP',system-ui,sans-serif;background:#fff;color:#333}
  header{height:64px;border-bottom:1px solid #eee;display:flex;align-items:center;padding:0 32px;
    font-weight:700;color:#555;font-size:18px}
  main{display:flex;gap:40px;padding:32px 64px}
  .img{width:440px;height:560px;background:linear-gradient(135deg,#e9edf5,#cfd6e6);border-radius:8px;
    display:flex;align-items:center;justify-content:center;color:#8a93a8;font-size:14px}
  h1{font-size:22px;margin:0 0 12px;max-width:520px}
  .price{font-size:30px;color:#333;margin:8px 0 24px}
  .buy{background:#4a5568;color:#fff;border-radius:6px;padding:14px;width:360px;text-align:center;font-weight:700}
</style></head><body>
<header>フリマサイトの商品ページ(イメージ)</header>
<main><div class="img">商品画像</div>
<div><h1>${title}</h1><div class="price">¥${price.toLocaleString()}</div><div class="buy">購入手続きへ</div></div></main>
</body></html>`;

const PAGES = {
  "https://jp.mercari.com/item/m10000000001": mockPage(
    "【美品】メガゲッコウガex SAR 120/080 ニンジャスピナー ポケモンカード",
    98000,
  ),
  "https://jp.mercari.com/item/m10000000002": mockPage(
    "ポケカ メガゲッコウガex まとめてお得",
    45000,
  ),
  "https://jp.mercari.com/item/m10000000003": mockPage(
    "イーブイ ぬいぐるみ ポケモンセンター",
    2800,
  ),
};

// 拡張の service worker の fetch を context.route でモックするのに必要(Playwright 1.56 時点で実験的機能)
process.env.PW_EXPERIMENTAL_SERVICE_WORKER_NETWORK_EVENTS = "1";

const userDataDir = await fs.mkdtemp(path.join(os.tmpdir(), "pokeca-ext-"));
const context = await chromium.launchPersistentContext(userDataDir, {
  channel: "chromium", // 拡張の読み込みには headless shell ではなく通常の Chromium が必要
  headless: true,
  viewport: { width: 1280, height: 800 },
  args: [`--disable-extensions-except=${ROOT}`, `--load-extension=${ROOT}`],
});

let failed = false;
try {
  // 価格データ(service worker の fetch)と商品ページをモックで返す
  await context.route("https://pokeca-kaigai.com/api/cards.json", (route) =>
    route.fulfill({ contentType: "application/json", body: fixture }),
  );
  await context.route("https://jp.mercari.com/**", (route) => {
    const body = PAGES[route.request().url()];
    return body
      ? route.fulfill({ contentType: "text/html; charset=utf-8", body })
      : route.fulfill({ status: 404, body: "" });
  });
  // service worker の起動を待ってから開く(起動前の fetch がモックを素通りしないように)
  if (context.serviceWorkers().length === 0) await context.waitForEvent("serviceworker");

  const page = await context.newPage();
  const badge = page.locator("#pokeca-kaigai-checker");

  // 1) 型番つき: 1枚に特定され円換算価格が出る
  await page.goto("https://jp.mercari.com/item/m10000000001");
  await badge.locator(".card").waitFor({ timeout: 10000 });
  const text1 = await badge.locator(".card").innerText();
  const data = JSON.parse(fixture);
  const eur = data.cards.find(([set, no]) => set === "M4" && no === "120")[3];
  const expectedYen = `¥${Math.round(eur * data.eurJpy).toLocaleString("ja-JP")}`;
  assert.match(text1, /メガゲッコウガex/);
  assert.ok(text1.includes(expectedYen), `円換算価格 ${expectedYen} が表示されること:\n${text1}`);
  assert.match(text1, /ニンジャスピナー 120/);
  console.log("ok - 型番つきタイトルで1枚の相場を表示");
  if (takeShots) {
    await fs.mkdir(SHOTS_DIR, { recursive: true });
    await page.screenshot({ path: path.join(SHOTS_DIR, "1-exact.png") });
  }

  // 2) 型番なし: 価格幅と候補一覧
  await page.goto("https://jp.mercari.com/item/m10000000002");
  await badge.locator(".card").waitFor({ timeout: 10000 });
  const text2 = await badge.locator(".card").innerText();
  assert.match(text2, /同名カード4種/);
  console.log("ok - 型番なしタイトルで価格幅と候補を表示");
  if (takeShots) await page.screenshot({ path: path.join(SHOTS_DIR, "2-candidates.png") });

  // 3) ポケカ以外: 表示しない
  await page.goto("https://jp.mercari.com/item/m10000000003");
  await page.waitForTimeout(1500);
  assert.equal(await badge.count(), 0, "グッズの出品にはバッジを出さないこと");
  console.log("ok - ポケカ以外の出品には表示しない");

  // 4) 閉じるボタン
  await page.goto("https://jp.mercari.com/item/m10000000001");
  await badge.locator(".card").waitFor({ timeout: 10000 });
  await badge.locator("button").click();
  assert.equal(await badge.count(), 0, "閉じるボタンで消えること");
  console.log("ok - 閉じるボタンで非表示");
} catch (err) {
  failed = true;
  console.error("not ok -", err.message);
} finally {
  await context.close();
  await fs.rm(userDataDir, { recursive: true, force: true });
}
process.exit(failed ? 1 : 0);
