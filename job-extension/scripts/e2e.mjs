// E2Eテスト: 実際のChromiumに拡張を読み込み、求人サイト風のモックページで年収バッジを確認する。
// 求人サイトでよくある3つのレイアウト(表 th/td・定義リスト dt/dd・見出し+本文)と一覧ページを再現する。
// あわせてストア掲載用スクリーンショット(1280x800)を store/screenshots/ に書き出す。
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

const page = (title, body) => `<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8">
<title>${title}</title>
<style>
  body{margin:0;font-family:'Noto Sans JP',system-ui,sans-serif;background:#f5f5f4;color:#333}
  header{height:60px;background:#fff;border-bottom:1px solid #e5e5e5;display:flex;align-items:center;
    padding:0 32px;font-weight:700;color:#555}
  main{max-width:760px;margin:24px 48px;background:#fff;padding:24px 32px;border-radius:8px}
  h1{font-size:22px;margin:0 0 18px}
  table{border-collapse:collapse;width:100%} th,td{border:1px solid #e5e5e5;padding:10px;text-align:left;
    vertical-align:top;font-size:14px} th{width:120px;background:#fafaf9}
  dt{font-weight:700;margin-top:12px} dd{margin:4px 0 0}
</style></head><body><header>求人サイトの求人詳細(イメージ)</header><main><h1>${title}</h1>${body}</main></body></html>`;

const PAGES = {
  // 表レイアウト(賞与の月数あり)
  "https://employment.en-japan.com/desc_1/": page(
    "経理スタッフ/年休125日/賞与実績5ヶ月分",
    `<table>
      <tr><th>仕事内容</th><td>月次・年次決算、税務申告の補助など</td></tr>
      <tr><th>給与</th><td>月給28万円～42万円＋賞与年2回（昨年度実績：5ヶ月分）<br>年収例 520万円／入社2年目</td></tr>
      <tr><th>勤務時間</th><td>9:00～17:45（実働7時間45分）</td></tr>
      <tr><th>休日休暇</th><td>完全週休2日制（土日祝）／年間休日125日</td></tr>
    </table>`,
  ),
  // 定義リストのレイアウト(固定残業代あり)
  "https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__2/": page(
    "法人営業/未経験歓迎",
    `<dl>
      <dt>給与</dt><dd>月給30万円（固定残業代：月40時間分、7万円を含む。超過分は別途支給）</dd>
      <dt>勤務時間</dt><dd>9:00～18:00（実働8時間）</dd>
      <dt>休日・休暇</dt><dd>年間休日120日</dd>
    </dl>`,
  ),
  // 見出し+本文のレイアウト(想定年収のみ)
  "https://tenshoku.mynavi.jp/jobinfo-3/": page(
    "Webエンジニア",
    `<h3>想定年収</h3><p>500万円～800万円</p><h3>勤務時間</h3><p>フレックスタイム制（標準労働時間8時間）</p>`,
  ),
  // 一覧ページ(給与欄が多数)=表示しない
  "https://employment.en-japan.com/list/": page(
    "求人一覧",
    Array.from(
      { length: 8 },
      (_, i) => `<table><tr><th>給与</th><td>月給${25 + i}万円～</td></tr></table>`,
    ).join(""),
  ),
};

const userDataDir = await fs.mkdtemp(path.join(os.tmpdir(), "job-ext-"));
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
  const badge = tab.locator("#job-salary-checker .card");
  const open = async (url) => {
    await tab.goto(url);
    await badge.waitFor({ timeout: 10000 });
    return badge.innerText();
  };

  // 1) 表レイアウト: 月給×12+賞与5ヶ月で年収目安、記載の年収例、年間休日を読む
  const t1 = await open("https://employment.en-japan.com/desc_1/");
  assert.match(t1, /約476万〜714万円/); // 28万×17=476万、42万×17=714万
  assert.match(t1, /賞与5ヶ月分で計算/);
  assert.match(t1, /年収例[\s\S]*520万円/);
  assert.match(t1, /年間休日125日/);
  console.log("ok - 表レイアウト: 年収目安(賞与込み)・記載の年収・休日を表示");
  if (takeShots) {
    await fs.mkdir(SHOTS_DIR, { recursive: true });
    await tab.screenshot({ path: path.join(SHOTS_DIR, "1-annual.png") });
  }

  // 2) 定義リスト: 固定残業代の警告と、除いた月給
  const t2 = await open("https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__2/");
  assert.match(t2, /固定残業代を含む給与です/);
  assert.match(t2, /月40時間分・7万円/);
  assert.match(t2, /除いた月給 23万円/);
  console.log("ok - 定義リスト: 固定残業代を警告し、除いた月給を表示");
  if (takeShots) await tab.screenshot({ path: path.join(SHOTS_DIR, "2-overtime.png") });

  // 3) 見出し+本文: 見出しが「想定年収」で本文が金額だけ
  const t3 = await open("https://tenshoku.mynavi.jp/jobinfo-3/");
  assert.match(t3, /求人に記載の年収\(想定年収\)[\s\S]*500万〜800万円/);
  console.log("ok - 見出し+本文: 想定年収を表示");

  // 4) 一覧ページ: 表示しない
  await tab.goto("https://employment.en-japan.com/list/");
  await tab.waitForTimeout(1500);
  assert.equal(await badge.count(), 0, "一覧ページにはバッジを出さないこと");
  console.log("ok - 一覧ページには表示しない");

  // 5) 紹介リンク(offers.js)は未設定なので広告枠を出さない
  await open("https://employment.en-japan.com/desc_1/");
  assert.equal(await tab.locator("#job-salary-checker .offers").count(), 0);
  console.log("ok - 紹介リンク未設定の間は広告枠を出さない");

  // 6) 閉じるボタン
  await tab.locator("#job-salary-checker button").click();
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
