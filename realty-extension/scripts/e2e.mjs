// E2Eテスト: 実際のChromiumに拡張を読み込み、不動産ポータル風のモックページでバッジを確認する。
// 物件ページでよくあるレイアウト(表 th/td・定義リスト dt/dd・見出し+本文)と一覧ページを再現する。
// あわせてストア掲載用スクリーンショット(1280x800)を store/screenshots/ に書き出す。
//   node scripts/e2e.mjs            … テストのみ
//   node scripts/e2e.mjs --shots    … テスト+スクリーンショット更新
import { chromium } from "playwright";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SHOTS_DIR = path.join(ROOT, "store", "screenshots");
const takeShots = process.argv.includes("--shots");

const page = (title, body) => `<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<title>${title}</title>
<style>
  body{margin:0;font-family:'Noto Sans JP',system-ui,sans-serif;background:#f5f5f4;color:#333}
  header{height:60px;background:#fff;border-bottom:1px solid #e5e5e5;display:flex;align-items:center;
    padding:0 32px;font-weight:700;color:#555}
  main{max-width:760px;margin:24px 48px;background:#fff;padding:24px 32px;border-radius:8px}
  h1{font-size:22px;margin:0 0 18px}
  table{border-collapse:collapse;width:100%} th,td{border:1px solid #e5e5e5;padding:10px;text-align:left;
    font-size:14px} th{width:140px;background:#fafaf9}
  dt{font-weight:700;margin-top:12px} dd{margin:4px 0 0}
  .imgs{height:220px;background:linear-gradient(135deg,#e0e7ff,#c7d2fe);border-radius:8px;margin-bottom:18px}
</style></head><body><header>不動産ポータルの物件詳細(イメージ)</header><main><h1>${title}</h1>
<div class="imgs"></div>${body}</main></body></html>`;

const PAGES = {
  // 賃貸(表レイアウト・敷金/礼金が1欄)
  "https://suumo.jp/chintai/bc_1/": page(
    "1LDK・駅徒歩6分・2019年築",
    `<table>
      <tr><th>賃料</th><td>12.5万円</td></tr>
      <tr><th>管理費・共益費</th><td>8000円</td></tr>
      <tr><th>敷金/礼金</th><td>1ヶ月 / 1ヶ月</td></tr>
      <tr><th>専有面積</th><td>40.5m2</td></tr>
    </table>`,
  ),
  // 中古マンション(定義リスト・管理費と修繕積立金が別欄)
  "https://www.homes.co.jp/mansion/b-1/": page(
    "中古マンション 3LDK",
    `<dl>
      <dt>価格</dt><dd>4,980万円</dd>
      <dt>専有面積</dt><dd>70.12㎡（壁芯）</dd>
      <dt>管理費</dt><dd>1万2000円／月</dd>
      <dt>修繕積立金</dt><dd>1万5000円／月</dd>
    </dl>`,
  ),
  // 投資物件(表・利回りと管理費/修繕積立が1欄)+用語解説の表(値として拾わないこと)
  "https://www.kenbiya.com/pp1/s/tokyo/re_1/": page(
    "区分マンション 1K",
    `<table>
      <tr><th>価格</th><td>1,850万円</td></tr>
      <tr><th>満室時利回り</th><td>5.8％</td></tr>
      <tr><th>管理費/修繕積立</th><td>9,000円 / 6,500円</td></tr>
      <tr><th>専有面積</th><td>25.2m²</td></tr>
    </table>
    <h2>用語の説明</h2>
    <table>
      <tr><th>価格</th><td>単位は「万円」。消費税がかかる場合は、税込み価格を表示。［値下げ］マークは価格変更1週間以内。</td></tr>
    </table>`,
  ),
  // Yahoo!不動産: 管理費の見出しが「管理費・共益費等」
  "https://realestate.yahoo.co.jp/rent/detail/1/": page(
    "落合駅 5階建 築1年未満",
    `<dl><dt>賃料</dt><dd>14.5万円</dd><dt>管理費・共益費等</dt><dd>15,000円</dd>
      <dt>専有面積</dt><dd>30.33m²</dd></dl>`,
  ),
  // CHINTAI: 賃料に見出しがなく span.rent にある。敷金・礼金の見出しが「敷金 / 保証金」「礼金 / 償却」
  "https://www.chintai.net/detail/bk-1/": page(
    "レックスガーデン神楽坂北町 7階",
    `<table>
      <tr><td><span class="rent">15.4万円</span></td></tr>
      <tr><th>管理費等</th><td>20,000円</td></tr>
      <tr><th>敷金 / 保証金</th><td>1ヶ月 / -</td></tr>
      <tr><th>礼金 / 償却</th><td>1ヶ月 / -</td></tr>
      <tr><th>専有面積</th><td>29.15m²</td></tr>
    </table>`,
  ),
  // CHINTAI の一覧(span.rent が多数)=表示しない
  "https://www.chintai.net/list/": page(
    "賃貸物件一覧",
    Array.from({ length: 6 }, (_, i) => `<p><span class="rent">${8 + i}万円</span></p>`).join(""),
  ),
  // 一覧ページ(検索条件の欄と、複数の物件の価格)=表示しない
  "https://suumo.jp/chintai/tokyo/": page(
    "賃貸物件一覧",
    `<dl><dt>賃料</dt><dd>3万円以下 3～4万円 4～5万円 10万円以上</dd>
      <dt>専有面積</dt><dd>下限なし 20m2 25m2 30m2</dd></dl>` +
      Array.from(
        { length: 6 },
        (_, i) =>
          `<table><tr><th>賃料</th><td>${8 + i}万円</td></tr><tr><th>専有面積</th><td>2${i}m2</td></tr></table>`,
      ).join(""),
  ),
};

// パッケージ化されていない拡張のIDは、フォルダの絶対パスの SHA-256 から決まる
// (先頭32桁の16進数を a〜p に置き換えたもの)
function extensionId(dir) {
  const hex = crypto.createHash("sha256").update(path.resolve(dir)).digest("hex").slice(0, 32);
  return [...hex].map((c) => String.fromCharCode(97 + parseInt(c, 16))).join("");
}

const userDataDir = await fs.mkdtemp(path.join(os.tmpdir(), "realty-ext-"));
const context = await chromium.launchPersistentContext(userDataDir, {
  channel: "chromium", // 拡張の読み込みには headless shell ではなく通常の Chromium が必要
  headless: true,
  viewport: { width: 1280, height: 800 },
  args: [`--disable-extensions-except=${ROOT}`, `--load-extension=${ROOT}`],
});

let failed = false;
try {
  await context.route(
    (url) => Object.keys(PAGES).some((p) => url.origin === new URL(p).origin),
    (route) => {
      const body = PAGES[route.request().url()];
      return body
        ? route.fulfill({ contentType: "text/html; charset=utf-8", body })
        : route.fulfill({ status: 404, body: "" });
    },
  );
  const tab = await context.newPage();
  const badge = tab.locator("#realty-price-checker .card");
  const open = async (url) => {
    await tab.goto(url);
    await badge.waitFor({ timeout: 10000 });
    return badge.innerText();
  };

  // 1) 賃貸: 実質月額・単価・初期費用(敷金・礼金は「1ヶ月」表記)
  const t1 = await open("https://suumo.jp/chintai/bc_1/");
  assert.match(t1, /13.3万円/); // 12.5万+8000円
  assert.match(t1, /1㎡あたり 3,284円/); // 133000/40.5
  assert.match(t1, /初期費用の目安[\s\S]*約52.1万円/); // 12.5万×2+13.75万+13.3万=52.05万
  console.log("ok - 賃貸: 実質月額・単価・初期費用を表示");
  if (takeShots) {
    await fs.mkdir(SHOTS_DIR, { recursive: true });
    await tab.screenshot({ path: path.join(SHOTS_DIR, "1-rent.png") });
  }

  // 2) 中古マンション: 単価と月々の支払い(既定の金利1%・35年)
  const t2 = await open("https://www.homes.co.jp/mansion/b-1/");
  assert.match(t2, /1㎡あたり 71万円/); // 4980万/70.12
  assert.match(t2, /管理費・修繕積立金 27,000円/);
  assert.match(t2, /金利1%・35年/);
  console.log("ok - 中古マンション: 単価と月々の支払いを表示");
  if (takeShots) await tab.screenshot({ path: path.join(SHOTS_DIR, "2-sale.png") });

  // 3) 投資物件: 利回り・年間収入・簡易実質(用語解説の表は拾わない)
  const t3 = await open("https://www.kenbiya.com/pp1/s/tokyo/re_1/");
  assert.match(t3, /表面 5.8%・簡易実質 4.79%/); // (107.3万-18.6万)/1850万
  assert.match(t3, /年間収入 107万円/); // 1850万×5.8%=107.3万(100万以上は万円単位で表示)
  console.log("ok - 投資物件: 利回り・年間収入・簡易実質利回りを表示");
  if (takeShots) await tab.screenshot({ path: path.join(SHOTS_DIR, "3-investment.png") });

  // 3b) Yahoo!不動産: 「管理費・共益費等」を月額に足す
  const t3b = await open("https://realestate.yahoo.co.jp/rent/detail/1/");
  assert.match(t3b, /16万円/); // 14.5万+15,000円
  console.log("ok - Yahoo!不動産: 管理費・共益費等を月額に含める");

  // 3c) CHINTAI: 見出しのない賃料と「敷金 / 保証金」「礼金 / 償却」
  const t3c = await open("https://www.chintai.net/detail/bk-1/");
  assert.match(t3c, /17.4万円/); // 15.4万+2万
  assert.match(t3c, /初期費用の目安[\s\S]*約65.1万円/); // 15.4万×2+16.94万+17.4万=65.14万
  console.log("ok - CHINTAI: 見出しのない賃料・敷金/保証金・礼金/償却を読む");

  await tab.goto("https://www.chintai.net/list/");
  await tab.waitForTimeout(1500);
  assert.equal(await badge.count(), 0, "CHINTAI の一覧ページにはバッジを出さないこと");
  console.log("ok - CHINTAI の一覧ページには表示しない");

  // 4) 一覧ページ: 表示しない
  await tab.goto("https://suumo.jp/chintai/tokyo/");
  await tab.waitForTimeout(1500);
  assert.equal(await badge.count(), 0, "一覧ページにはバッジを出さないこと");
  console.log("ok - 一覧ページ(検索条件・複数物件)には表示しない");

  // 5) ポップアップで変えたローン条件が反映される(実際のポップアップ画面で金利を2%にする)
  const popup = await context.newPage();
  await popup.goto(`chrome-extension://${extensionId(ROOT)}/src/popup.html`);
  await popup.fill("#loanRate", "2");
  await popup.locator("#loanRate").dispatchEvent("change");
  await popup.close();
  const t5 = await open("https://www.homes.co.jp/mansion/b-1/");
  assert.match(t5, /金利2%・35年/);
  console.log("ok - ポップアップで変えたローン金利が反映される");

  // 6) 閉じるボタン
  await open("https://suumo.jp/chintai/bc_1/");
  await tab.locator("#realty-price-checker button").click();
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
