// 売れたアカウント(SOLD)をゲームトレードの一覧から集め、Cloudflare Worker(D1)に貯める。査定ツールの値付けの学習用。
// Claude の定期実行から、新着チェック(relay.mjs)と一緒に1日1回実行する。
//
//   GAMETRADE_INGEST_TOKEN=<合言葉> node gametrade-watch/sold-relay.mjs
//   node gametrade-watch/sold-relay.mjs --dry-run            # 送らずに件数と例を表示(合言葉は不要)
//   ... --pages 99                                           # 初回など、一覧を深くまで見る
//   ... --details 0                                          # 出品ページ(説明文の全文・画像)を取りに行かない
//
// 定期実行は依存なしで動かすため、このファイル・config.sold.json・src/core.js・src/sold.js だけを
// GitHub から取ってきて実行する(README 参照)。

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { fetchPages } from "./src/core.js";
import { listUrl, parseSold, parseDetail, soldRecord } from "./src/sold.js";

const here = dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(await readFile(join(here, "config.sold.json"), "utf8"));
const args = process.argv.slice(2);
const opt = (name, fallback) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? Number(args[i + 1]) : fallback;
};
const dryRun = args.includes("--dry-run");
const pages = opt("pages", config.pages);
const details = opt("details", config.details);
const token = process.env.GAMETRADE_INGEST_TOKEN;
if (!dryRun && !token) throw new Error("GAMETRADE_INGEST_TOKEN が未設定です");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36";

async function worker(path, init = {}) {
  const res = await fetch(new URL(path, config.worker), {
    ...init,
    headers: { authorization: `Bearer ${token}`, "content-type": "application/json", ...init.headers },
  });
  const text = await res.text();
  if (!res.ok) throw new Error(`${path}: ${res.status} ${text}`);
  return JSON.parse(text);
}

// 1. 一覧から売れた出品を集めて送る
const summary = [];
for (const { game, label } of config.games) {
  const html = await fetchPages({ url: listUrl(game, config), pages });
  const found = new Map();
  for (const page of html) for (const it of parseSold(page)) found.set(it.id, soldRecord(it));
  const items = [...found.values()];
  if (dryRun) {
    console.log(`${label}: ${pages}ページで売れた出品 ${items.length}件`);
    for (const it of items.slice(0, 3)) console.log(`  ¥${it.price.toLocaleString("ja-JP")} ${it.name}`);
    summary.push({ game, sold: items.length });
    continue;
  }
  let added = 0;
  for (let i = 0; i < items.length; i += 200) {
    const r = await worker("/sold", { method: "POST", body: JSON.stringify({ game, items: items.slice(i, i + 200) }) });
    added += r.added;
  }
  summary.push({ game, sold: items.length, added });
}

// 2. 説明文の全文と画像がまだ無いものを、出品ページから取ってきて足す(1件ずつ間を空けて)
let filled = 0;
if (details > 0) {
  const missing = dryRun
    ? [] // 手元の確認では、一覧の先頭の1件だけ出品ページを読んでみる
    : (await worker(`/sold/missing?limit=${details}`)).items;
  if (dryRun) {
    const first = parseSold(
      (await fetchPages({ url: listUrl(config.games[0].game, config), pages: 1 }))[0],
    )[0];
    if (first) missing.push(first);
  }
  const out = [];
  for (const it of missing) {
    await sleep(2000);
    const res = await fetch(it.url, { headers: { "user-agent": UA, "accept-language": "ja" }, signal: AbortSignal.timeout(20000) });
    if (!res.ok) continue; // 削除された出品など。次回また試す
    const d = parseDetail(await res.text());
    if (dryRun) {
      console.log(`出品ページの例: ${it.url}\n  画像 ${d.images.length}枚 / 説明文 ${d.description.length}文字 / 取引終了 ${d.done}`);
      console.log(`  ${d.description.slice(0, 120).replace(/\n/g, " ")}`);
    }
    out.push({ id: it.id, description: d.description.slice(0, 20000), images: d.images.slice(0, 30) });
  }
  if (!dryRun && out.length) filled = (await worker("/sold/details", { method: "POST", body: JSON.stringify({ details: out }) })).updated;
}

console.log(JSON.stringify({ ok: true, pages, games: summary, details: filled }));
