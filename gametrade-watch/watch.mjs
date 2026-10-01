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
const MAX_SEEN = 5000;

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
      info,
    });
  }
  return items;
}

async function fetchPage(url) {
  const res = await fetch(url, {
    headers: { "user-agent": "Mozilla/5.0 (compatible; chien-monitor/1.0)", "accept-language": "ja" },
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${url}`);
  return res.text();
}

async function loadState() {
  try {
    return JSON.parse(await readFile(statePath, "utf8"));
  } catch {
    return null;
  }
}

const yen = (n) => `¥${n.toLocaleString("ja-JP")}`;

async function notify(items) {
  // Discord は1投稿あたり埋め込み10件まで
  for (let i = 0; i < items.length; i += 10) {
    const chunk = items.slice(i, i + 10);
    const res = await fetch(webhook, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        username: "ゲームトレード新着",
        allowed_mentions: { parse: [] },
        content: i === 0 ? `🆕 ${config.label ?? "新着"}: ${items.length}件` : undefined,
        embeds: chunk.map((it) => ({
          title: it.name.slice(0, 250),
          url: it.url,
          description: [yen(it.price), ...it.info].join("\n").slice(0, 4000),
          color: 0x2563eb,
          thumbnail: it.image ? { url: it.image } : undefined,
        })),
      }),
    });
    if (!res.ok) throw new Error(`Discord への送信に失敗: ${res.status} ${await res.text()}`);
    await new Promise((r) => setTimeout(r, 1000));
  }
}

async function main() {
  const base = new URL(process.env.GAMETRADE_URL || config.url);
  base.searchParams.delete("page");
  // サイト側が価格の絞り込みを無視することがあるので、こちらでも絞り込む
  const low = Number(base.searchParams.get("low_price")) || 0;
  const high = Number(base.searchParams.get("high_price")) || Infinity;

  const found = new Map();
  for (let page = 1; page <= (config.pages ?? 3); page++) {
    const url = new URL(base);
    url.searchParams.set("page", String(page));
    for (const it of parseExhibits(await fetchPage(url), base.origin)) found.set(it.id, it);
  }
  if (found.size === 0) throw new Error("出品を1件も読み取れませんでした(サイトの構造が変わった可能性)");

  const all = [...found.values()];
  const inRange = all.filter((it) => it.price >= low && it.price <= high);
  const state = await loadState();
  const seen = new Set(state?.seen ?? []);
  const fresh = inRange.filter((it) => !seen.has(it.id));

  console.log(`取得 ${all.length}件 / 価格帯内 ${inRange.length}件 / 新着 ${fresh.length}件`);
  for (const it of fresh) console.log(`  ${yen(it.price)}  ${it.name}  ${it.url}`);

  if (dryRun) return;
  if (!state) {
    console.log("初回実行: 現在の出品を記録しただけで通知はしません");
  } else if (fresh.length && webhook) {
    await notify(fresh);
  } else if (fresh.length) {
    console.log("::warning::GAMETRADE_DISCORD_WEBHOOK が未設定のため通知していません");
  }

  // 記録するのは価格帯内の出品だけ(価格帯外の出品が値下げで入ってきたら新着として通知する)
  const ids = [...inRange.map((it) => it.id), ...seen];
  const next = { seen: [...new Set(ids)].slice(0, MAX_SEEN), updatedAt: new Date().toISOString() };
  await writeFile(statePath, JSON.stringify(next) + "\n");
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
