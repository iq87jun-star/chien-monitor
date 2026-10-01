// ゲームトレード(gametrade.jp)の出品一覧を見て、まだ見ていない出品を Discord に通知する。
// 依存なし(Node 22 の fetch のみ)。GitHub Actions から定期実行する(.github/workflows/gametrade-watch.yml)。
//
//   node watch.mjs            … 新着を通知し、見た出品IDを state.json に保存
//   node watch.mjs --dry-run  … 通知も保存もせず、新着を表示するだけ
//
// 環境変数:
//   GAMETRADE_DISCORD_WEBHOOK … 通知先の Discord ウェブフックURL(未設定なら表示のみ)
//   GAMETRADE_URL             … 監視する一覧URL(未設定なら config.json の url)
//   GAMETRADE_STATE           … 状態ファイルのパス(既定: このフォルダの state.json)

import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(await readFile(join(here, "config.json"), "utf8"));
const statePath = process.env.GAMETRADE_STATE || join(here, "state.json");
const webhook = process.env.GAMETRADE_DISCORD_WEBHOOK || "";
const dryRun = process.argv.includes("--dry-run");
const MAX_PRICES = 5000;

const decode = (s) =>
  s
    .replace(/&quot;/g, '"')
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&amp;/g, "&");

// 一覧ページの HTML から出品を取り出す
export function parseExhibits(html, origin) {
  const items = [];
  const re = /<input id="exhibit_(\d+)_deta" name="exhibit_data" type="hidden" value="([^"]*)" \/>([\s\S]*?)(?=<input id="exhibit_\d+_deta"|$)/g;
  for (const m of html.matchAll(re)) {
    let data;
    try {
      data = JSON.parse(decode(m[2]));
    } catch {
      continue;
    }
    const block = m[3];
    const img = /<img [^>]*src="([^"]+)"/.exec(block)?.[1];
    const href = /<a class="exhibit-link" href="([^"]+)"/.exec(block)?.[1] ?? "";
    const info = [...block.matchAll(/<div class="sub_form_values">([\s\S]*?)<\/div>/g)]
      .flatMap((x) => [...x[1].matchAll(/<p>([\s\S]*?)<\/p>/g)].map((p) => decode(p[1]).trim()));
    items.push({
      id: m[1],
      name: data.name,
      price: Number(data.price),
      url: new URL(href || `exhibits/${m[1]}`, origin).href,
      image: img && !img.includes("no-image") ? img : null,
      // 値下げされた出品は一覧に元の価格が出る
      previousPrice: Number(/<li class="previous_price"><p>[^0-9]*([\d,]+)/.exec(block)?.[1].replace(/,/g, "")) || null,
      info,
    });
  }
  return items;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// 連続で取りに行くと 403 が返ることがあるので、間を空けて数回やり直す
async function fetchPage(url) {
  for (let attempt = 0; ; attempt++) {
    const res = await fetch(url, {
      headers: {
        "user-agent":
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "ja,en-US;q=0.9,en;q=0.8",
      },
    });
    if (res.ok) return res.text();
    if (attempt >= 3 || ![403, 429, 500, 502, 503, 504].includes(res.status)) {
      throw new Error(`${res.status} ${res.statusText}: ${url}`);
    }
    await sleep(5000 * 2 ** attempt);
  }
}

async function loadState() {
  try {
    return JSON.parse(await readFile(statePath, "utf8"));
  } catch {
    return null;
  }
}

const yen = (n) => `¥${n.toLocaleString("ja-JP")}`;

// items: { ...出品, kind: "new" | "drop", before?: 値下げ前の価格 }
async function notify(items) {
  const counts = [
    ["new", "新規出品"],
    ["drop", "値下げ"],
  ]
    .map(([k, label]) => [label, items.filter((it) => it.kind === k).length])
    .filter(([, n]) => n)
    .map(([label, n]) => `${label} ${n}件`)
    .join(" / ");
  // Discord は1投稿あたり埋め込み10件まで
  for (let i = 0; i < items.length; i += 10) {
    const chunk = items.slice(i, i + 10);
    const res = await fetch(webhook, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        username: "ゲームトレード新着",
        allowed_mentions: { parse: [] },
        content: i === 0 ? `🆕 ${config.label ?? "新着"}: ${counts}` : undefined,
        embeds: chunk.map((it) => ({
          title: `${it.kind === "drop" ? "【値下げ】" : "【新規】"}${it.name}`.slice(0, 250),
          url: it.url,
          description: [priceText(it), ...it.info].join("\n").slice(0, 4000),
          color: it.kind === "drop" ? 0xdc2626 : 0x2563eb,
          thumbnail: it.image ? { url: it.image } : undefined,
        })),
      }),
    });
    if (!res.ok) throw new Error(`Discord への送信に失敗: ${res.status} ${await res.text()}`);
    await sleep(1000);
  }
}

const priceText = (it) =>
  it.kind === "drop" && it.before
    ? `${yen(it.before)} → **${yen(it.price)}**(${Math.round((1 - it.price / it.before) * 100)}%OFF)`
    : yen(it.price);

// 通知する出品を決める。
//   新規出品: 前回までに見た最大の出品IDより新しいID(出品IDは作成順に増える)
//   値下げ  : 記録した価格より下がった / 記録がなく一覧に「元の価格」が出ている
// 古い出品が説明文の編集などで一覧の上に来ただけのものは通知しない
export function pick(all, low, high, state) {
  const out = [];
  for (const it of all) {
    if (it.price < low || it.price > high) continue;
    const known = state.prices[it.id];
    if (known !== undefined) {
      if (it.price < known) out.push({ ...it, kind: "drop", before: known });
    } else if (BigInt(it.id) > BigInt(state.maxId)) {
      out.push({ ...it, kind: "new" });
    } else if (it.previousPrice && it.previousPrice > it.price) {
      out.push({ ...it, kind: "drop", before: it.previousPrice });
    }
  }
  return out;
}

async function main() {
  const base = new URL(process.env.GAMETRADE_URL || config.url);
  base.searchParams.delete("page");
  // サイト側が価格の絞り込みを無視することがあるので、こちらでも絞り込む
  const low = Number(base.searchParams.get("low_price")) || 0;
  const high = Number(base.searchParams.get("high_price")) || Infinity;

  const found = new Map();
  for (let page = 1; page <= (config.pages ?? 3); page++) {
    if (page > 1) await sleep(3000);
    const url = new URL(base);
    url.searchParams.set("page", String(page));
    for (const it of parseExhibits(await fetchPage(url), base.origin)) found.set(it.id, it);
  }
  if (found.size === 0) throw new Error("出品を1件も読み取れませんでした(サイトの構造が変わった可能性)");

  const all = [...found.values()];
  const loaded = await loadState();
  const state = loaded?.maxId ? loaded : null; // 古い形式の状態ファイルは初回扱い
  const hits = state ? pick(all, low, high, state) : [];

  console.log(`取得 ${all.length}件 / 通知 ${hits.length}件`);
  for (const it of hits) console.log(`  [${it.kind === "drop" ? "値下げ" : "新規"}] ${priceText(it)}  ${it.name}  ${it.url}`);

  if (dryRun) return;
  if (!state) {
    console.log("初回実行: 現在の出品を記録しただけで通知はしません");
  } else if (hits.length && webhook) {
    await notify(hits);
  } else if (hits.length) {
    console.log("::warning::GAMETRADE_DISCORD_WEBHOOK が未設定のため通知していません");
  }

  // 一覧に出た出品の現在価格を記録(価格帯外も。後で価格帯に下がってきた時に値下げと分かるように)
  const prices = { ...(state?.prices ?? {}) };
  for (const it of all) prices[it.id] = it.price;
  const kept = Object.keys(prices)
    .sort((a, b) => (BigInt(b) > BigInt(a) ? 1 : -1))
    .slice(0, MAX_PRICES);
  const maxId = all.reduce((m, it) => (BigInt(it.id) > BigInt(m) ? it.id : m), state?.maxId ?? "0");
  const next = {
    maxId,
    prices: Object.fromEntries(kept.map((id) => [id, prices[id]])),
    updatedAt: new Date().toISOString(),
  };
  await writeFile(statePath, JSON.stringify(next) + "\n");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
