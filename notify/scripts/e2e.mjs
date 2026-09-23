// E2Eテスト: ローカルの Worker(wrangler dev・ローカルD1)と偽の Discord を起動し、
// 実際の Chromium で登録ページを操作する。最後に同じD1に値下がりチェックをかけ、通知が届くことを確認する。
//   node scripts/e2e.mjs            … テストのみ
//   node scripts/e2e.mjs --shots    … テスト+スクリーンショット(screenshots/)
import { chromium } from "playwright";
import { spawn, execFileSync } from "node:child_process";
import assert from "node:assert/strict";
import fs from "node:fs/promises";
import http from "node:http";
import os from "node:os";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";
import { runCheck } from "../src/check.js";
import { priceData } from "../test/helpers.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SHOTS = path.join(ROOT, "screenshots");
const takeShots = process.argv.includes("--shots");
const HOOK_ID = "123456789012345678";
const WEBHOOK = `https://discord.com/api/webhooks/${HOOK_ID}/abcdefghijklmnopqrstuvwxyz0123456789ABCD`;

// 偽の Discord: HOOK_ID のウェブフックだけ存在し、投稿を記録する
const posts = [];
const discord = http.createServer((req, res) => {
  const exists = req.url.startsWith(`/api/webhooks/${HOOK_ID}/`);
  let body = "";
  req.on("data", (c) => (body += c));
  req.on("end", () => {
    if (req.method === "POST" && exists) posts.push(JSON.parse(body));
    res
      .writeHead(exists ? (req.method === "GET" ? 200 : 204) : 404)
      .end(req.method === "GET" ? "{}" : "");
  });
});
await new Promise((r) => discord.listen(0, "127.0.0.1", r));
const discordOrigin = `http://127.0.0.1:${discord.address().port}`;

const persist = await fs.mkdtemp(path.join(os.tmpdir(), "notify-e2e-"));
const wrangler = path.join(ROOT, "node_modules", ".bin", "wrangler");
execFileSync(
  wrangler,
  ["d1", "migrations", "apply", "toreca-notify", "--local", "--persist-to", persist],
  {
    cwd: ROOT,
    stdio: "ignore",
  },
);
// 空いているポートを使う(前回の実行が残っていても衝突しないように)
const freePort = () =>
  new Promise((resolve) => {
    const srv = http.createServer().listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
const PORT = await freePort();
const worker = spawn(
  wrangler,
  [
    "dev",
    "--port",
    String(PORT),
    "--ip",
    "127.0.0.1",
    "--inspector-port",
    String(await freePort()),
    "--persist-to",
    persist,
    "--var",
    `DISCORD_ORIGIN:${discordOrigin}`,
  ],
  {
    cwd: ROOT,
    stdio: ["ignore", "pipe", "pipe"],
    detached: true, // 終了時に workerd の子プロセスごと止める
    env: { ...process.env, NO_PROXY: "127.0.0.1,localhost", no_proxy: "127.0.0.1,localhost" },
  },
);
let workerLog = "";
worker.stdout.on("data", (d) => (workerLog += d));
worker.stderr.on("data", (d) => (workerLog += d));
const BASE = `http://127.0.0.1:${PORT}`;
for (let i = 0; ; i++) {
  try {
    if ((await fetch(BASE)).ok) break;
  } catch {}
  if (i > 60) throw new Error(`wrangler dev が起動しません\n${workerLog}`);
  await new Promise((r) => setTimeout(r, 500));
}

const data = priceData(); // リザードンex(SV2a-201)=1,800円 等
const browser = await chromium.launch({ channel: "chromium" });
let failed = false;
try {
  const context = await browser.newContext({ viewport: { width: 1000, height: 900 } });
  await context.route(
    (url) => Boolean(data[url.href]),
    (route) => route.fulfill({ json: data[route.request().url()] }),
  );
  const page = await context.newPage();
  page.on("dialog", (d) => d.accept());
  const status = page.locator("#status");
  await page.goto(BASE);

  // 1) 登録: 存在しないウェブフックは断られ、正しいURLで設定画面に進む
  await page.locator("#signup").waitFor();
  await page.fill("#webhook", WEBHOOK.replace(HOOK_ID, "999999999999999999"));
  await page.click("#signup-form button");
  await assert.doesNotReject(
    status.filter({ hasText: "見つかりませんでした" }).waitFor({ timeout: 5000 }),
  );
  await page.fill("#webhook", WEBHOOK);
  await page.click("#signup-form button");
  await page.locator("#manage").waitFor();
  assert.equal(posts.length, 1);
  const manageUrl = /(http:\S+#k=[\w-]+)/.exec(posts[0].content)[1];
  assert.ok(manageUrl.startsWith(BASE));
  console.log("ok - 登録すると設定画面になり、Discord に設定用リンクが届く");

  // 2) ポケカを検索して目標額つきで追加(ひらがなで検索できる)
  await page.fill("#query", "りざーどん");
  const zard = page.locator("#results li", { hasText: "ポケモンカード151 201" });
  assert.match(await zard.innerText(), /1,800円/);
  await zard.locator("input").fill("1500");
  await zard.locator("button").click();
  await page.locator("#watches li", { hasText: "リザードンex" }).waitFor();
  assert.match(await page.locator("#watches").innerText(), /現在 1,800円[\s\S]*目標 1,500円 以下/);
  assert.equal(await page.locator("#count").innerText(), "1 / 3枚");
  console.log("ok - カードを検索して目標額つきで追加");

  // 3) ワンピースは版ごとに選べる。遊戯王は日本語名で検索
  await page.check("input[name=game][value=onepiece]");
  await page.fill("#query", "op05-119");
  assert.equal(await page.locator("#results li").count(), 2);
  await page.locator("#results li", { hasText: "パラレル" }).locator("button").click();
  await page.locator("#watches li", { hasText: "OP05-119" }).waitFor();
  await page.check("input[name=game][value=yugioh]");
  await page.fill("#query", "はるうらら");
  await page.locator("#results li", { hasText: "灰流うらら" }).locator("button").click();
  await page.locator("#watches li", { hasText: "灰流うらら" }).waitFor();
  console.log("ok - ワンピース(版を選択)・遊戯王(日本語名)も追加できる");

  // 4) 無料プランは3枚まで
  await page.fill("#query", "せぶん");
  await page.locator("#results li", { hasText: "セブン" }).locator("button").click();
  await status.filter({ hasText: "3枚まで" }).waitFor({ timeout: 5000 });
  assert.equal(await page.locator("#watches li").count(), 3);
  console.log("ok - 無料プランの上限(3枚)で止まる");
  if (takeShots) {
    await fs.mkdir(SHOTS, { recursive: true });
    await page.screenshot({ path: path.join(SHOTS, "manage.png"), fullPage: true });
  }

  // 5) 削除・テスト通知
  await page.locator("#watches li", { hasText: "灰流うらら" }).locator("button").click();
  await status.filter({ hasText: "削除しました" }).waitFor();
  assert.equal(await page.locator("#watches li").count(), 2);
  await page.click("#test");
  await status.filter({ hasText: "テスト通知を送りました" }).waitFor();
  assert.match(posts.at(-1).content, /テスト通知/);
  console.log("ok - カードの削除・テスト通知");

  // 6) Discord に届いたリンクから、別のブラウザでも同じ設定を開ける
  const other = await browser.newContext();
  await other.route(
    (url) => Boolean(data[url.href]),
    (route) => route.fulfill({ json: data[route.request().url()] }),
  );
  const page2 = await other.newPage();
  await page2.goto(manageUrl);
  await page2.locator("#watches li", { hasText: "リザードンex" }).waitFor();
  assert.equal(new URL(page2.url()).hash, ""); // キーはアドレスバーから消す
  await other.close();
  console.log("ok - Discord のリンクから別のブラウザでも設定を開ける");

  // 7) 同じD1に値下がりチェック: リザードンが1,440円(目標1,500円以下)→ 通知
  const dir = path.join(persist, "v3", "d1", "miniflare-D1DatabaseObject");
  const file = (await fs.readdir(dir)).find((f) => f.endsWith(".sqlite"));
  const raw = new DatabaseSync(path.join(dir, file));
  const db = {
    all: async (sql, p = []) => raw.prepare(sql).all(...p),
    run: async (sql, p = []) => Number(raw.prepare(sql).run(...p).changes),
  };
  const cheaper = priceData({ pokecaEur: 8 });
  const fetchImpl = (url, init) =>
    cheaper[url] ? Promise.resolve(Response.json(cheaper[url])) : fetch(url, init);
  const stats = await runCheck({ db, fetchImpl, discordOrigin });
  raw.close();
  assert.equal(stats.notified, 1);
  const embed = posts.at(-1).embeds[0];
  assert.equal(embed.title, "リザードンex");
  assert.match(embed.description, /1,440円/);
  await page.reload();
  await page.locator("#watches li", { hasText: "通知済み" }).waitFor();
  console.log("ok - 値下がりチェックで Discord に通知が届き、画面に「通知済み」と出る");

  // 8) 登録の削除
  await page.click("#delete");
  await page.locator("#signup").waitFor();
  assert.equal(
    await (
      await fetch(`${BASE}/api/me`, {
        headers: { authorization: `Bearer ${manageUrl.split("#k=")[1]}` },
      })
    ).status,
    401,
  );
  console.log("ok - 登録を削除すると、設定用リンクも使えなくなる");
} catch (err) {
  failed = true;
  console.error("not ok -", err.message);
  if (process.env.DEBUG) console.error(workerLog);
} finally {
  await browser.close();
  try {
    process.kill(-worker.pid);
  } catch {}
  discord.close();
  await fs.rm(persist, { recursive: true, force: true });
}
process.exit(failed ? 1 : 0);
