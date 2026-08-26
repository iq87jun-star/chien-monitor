// ステップ1: データ収集
// content/watchlist.json の各アイテムを楽天市場商品検索APIで検索し、
// 出品価格の分布(最安・中央値・出品数)と最安出品へのリンクを data/raw/ に保存する。
// 楽天APIは現在の出品価格のみで履歴を持たないため、騰落率用の履歴も自前で蓄積する。
// APIキー未設定・API障害時は既存の生データを壊さないよう、警告のみで正常終了する。
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  CONTENT_DIR,
  USER_AGENT,
  RAKUTEN_API,
  RAKUTEN_API_OPENAPI,
  RAKUTEN_GENRE,
  HITS_PER_ITEM,
  REQUEST_INTERVAL_MS,
  NG_WORDS,
  MIN_LISTING_JPY,
  HISTORY_KEEP_DAYS,
} from "./config.mjs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchJson(url, retries = 2) {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, {
        headers: { Accept: "application/json", "User-Agent": USER_AGENT },
      });
      // 429はリトライしても同分内は通らないことが多いので長めに待つ
      if (res.status === 429) throw new Error("HTTP 429 (rate limited)");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      if (attempt >= retries) throw err;
      await sleep(3000 * 2 ** attempt);
    }
  }
}

async function readJson(file, fallback = null) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

const median = (sorted) =>
  sorted.length === 0
    ? null
    : sorted.length % 2
      ? sorted[(sorted.length - 1) / 2]
      : Math.round((sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2);

export async function fetchAll() {
  await fs.mkdir(RAW_DIR, { recursive: true });

  const appId = process.env.DUEMA_RAKUTEN_APP_ID || process.env.RAKUTEN_APP_ID;
  const affiliateId =
    process.env.DUEMA_RAKUTEN_AFFILIATE_ID || process.env.RAKUTEN_AFFILIATE_ID || "";
  const accessKey =
    process.env.DUEMA_RAKUTEN_ACCESS_KEY || process.env.RAKUTEN_ACCESS_KEY || "";
  // アクセスキーがあれば新エンドポイント、なければ従来どおり旧エンドポイントを使う
  const endpoint = accessKey ? RAKUTEN_API_OPENAPI : RAKUTEN_API;
  if (!appId) {
    console.warn(
      "fetch: DUEMA_RAKUTEN_APP_ID not set — keeping existing raw data " +
        "(楽天ウェブサービスでアプリIDを無料発行してSecretsに設定してください)",
    );
    return { ok: false };
  }

  const watchlist = (await readJson(path.join(CONTENT_DIR, "watchlist.json"), { items: [] }))
    .items;
  if (watchlist.length === 0) {
    console.warn("fetch: watchlist is empty — nothing to do");
    return { ok: false };
  }

  const items = [];
  let failures = 0;
  for (const w of watchlist) {
    const params = new URLSearchParams({
      applicationId: appId,
      keyword: w.query,
      hits: String(HITS_PER_ITEM),
      sort: "+itemPrice",
      formatVersion: "2",
    });
    if (RAKUTEN_GENRE) params.set("genreId", RAKUTEN_GENRE);
    if (affiliateId) params.set("affiliateId", affiliateId);
    if (accessKey) params.set("accessKey", accessKey);

    try {
      const body = await fetchJson(`${endpoint}?${params}`);
      const listings = (body?.Items ?? [])
        .filter((i) => i.itemPrice >= MIN_LISTING_JPY && !NG_WORDS.test(i.itemName ?? ""))
        .sort((a, b) => a.itemPrice - b.itemPrice);
      const prices = listings.map((i) => i.itemPrice);
      const cheapest = listings[0] ?? null;
      items.push({
        id: w.id,
        count: listings.length,
        low: prices[0] ?? null,
        median: median(prices),
        url: cheapest ? (affiliateId && cheapest.affiliateUrl) || cheapest.itemUrl : null,
        shop: cheapest?.shopName ?? null,
      });
    } catch (err) {
      failures++;
      console.warn(`fetch: "${w.id}" failed (${err.message}) — skipped this run`);
    }
    await sleep(REQUEST_INTERVAL_MS);
  }

  // 全件失敗(キー無効・API全面障害)は既存rawを保持して撤退
  if (items.length === 0 || items.every((i) => i.count === 0 && i.low == null)) {
    console.warn("fetch: no usable listings returned — keeping existing raw data");
    return { ok: false };
  }

  // --- 価格履歴の蓄積(騰落率と「初回記録時からの倍率」の計算用) ---
  const today = new Date().toISOString().slice(0, 10);
  const cutoff = new Date(Date.now() - HISTORY_KEEP_DAYS * 24 * 3600e3)
    .toISOString()
    .slice(0, 10);
  const history = (await readJson(path.join(RAW_DIR, "history.json"), { items: {} })).items;
  for (const it of items) {
    if (it.median == null) continue;
    const h = (history[it.id] ??= []);
    const entry = [today, it.low, it.median, it.count];
    const idx = h.findIndex(([d]) => d === today);
    if (idx >= 0) h[idx] = entry; // 同日再実行は上書き
    else h.push(entry);
    // 初回記録([0])は「初回比」の基準として保持期間に関係なく残す
    history[it.id] = [h[0], ...h.slice(1).filter(([d]) => d >= cutoff)];
  }

  await fs.writeFile(
    path.join(RAW_DIR, "history.json"),
    JSON.stringify({ updatedAt: new Date().toISOString(), items: history }),
  );
  await fs.writeFile(
    path.join(RAW_DIR, "items.json"),
    JSON.stringify({ fetchedAt: new Date().toISOString(), items }, null, 1),
  );
  console.log(
    `fetch: done (${items.length}/${watchlist.length} items, ${failures} failures, ` +
      `${Object.keys(history).length} tracked in history)`,
  );
  return { ok: true };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  fetchAll().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
