// ステップ1: データ収集
// Skinport APIからCS2全スキンの出品価格(最安値・中央値・出品数)を1リクエストで取得し、
// 必要な項目だけに絞って data/raw/ に保存する。価格履歴も自前で蓄積する
// (このAPIは現在の出品状況のみで過去平均を持たないため)。
// APIが一時的に落ちていても既存の生データを壊さないよう、失敗時は警告のみで正常終了する。
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  USER_AGENT,
  SKINPORT_ITEMS_URL,
  FX_URL,
  MIN_TRACK_USD,
  MIN_TRACK_QTY,
  HISTORY_KEEP_DAYS,
} from "./config.mjs";

async function fetchJson(url, retries = 3) {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, {
        headers: {
          Accept: "application/json",
          // Skinportのレスポンスはbrotli圧縮(Node 22のfetchはbrを展開できる)
          "Accept-Encoding": "br, gzip, deflate",
          "User-Agent": USER_AGENT,
        },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
      return await res.json();
    } catch (err) {
      if (attempt >= retries) throw err;
      const waitMs = 5000 * 2 ** attempt;
      console.warn(`fetch failed (${err.message}), retrying in ${waitMs}ms`);
      await new Promise((r) => setTimeout(r, waitMs));
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

export async function fetchAll() {
  await fs.mkdir(RAW_DIR, { recursive: true });

  // --- 為替(失敗しても致命ではない: 既存のfx.jsonを保持) ---
  try {
    const fx = await fetchJson(FX_URL);
    if (fx?.rates?.JPY) {
      await fs.writeFile(
        path.join(RAW_DIR, "fx.json"),
        JSON.stringify({ fetchedAt: new Date().toISOString(), ...fx }, null, 1),
      );
      console.log(`fetch: fx USD/JPY=${fx.rates.JPY}`);
    }
  } catch (err) {
    console.warn(`fetch: fx unavailable — keeping existing fx.json (${err.message})`);
  }

  // --- 全スキン取得(Skinportのレート制限に従い1リクエストで全件) ---
  let all;
  try {
    all = await fetchJson(SKINPORT_ITEMS_URL);
  } catch (err) {
    console.warn(`fetch: skinport unavailable — keeping existing raw data (${err.message})`);
    return { ok: false };
  }
  if (!Array.isArray(all) || all.length === 0) {
    console.warn("fetch: response had no items — keeping existing raw data");
    return { ok: false };
  }

  // 必要項目だけに絞る(生データを軽くしてgitに収める)。
  // 表示価格は中央値を優先(最安値は板の薄いスキンで振れやすいため)
  const items = [];
  for (const i of all) {
    const min = i.min_price ?? 0;
    const median = i.median_price ?? 0;
    const price = median > 0 ? median : min;
    if (!(price > 0)) continue; // 出品ゼロのスキンは監視対象外
    items.push({
      name: i.market_hash_name,
      price,
      min: min > 0 ? min : null,
      qty: i.quantity ?? 0,
    });
  }
  if (items.length === 0) {
    console.warn("fetch: no priced items — keeping existing raw data");
    return { ok: false };
  }

  // --- 価格履歴の蓄積(騰落率の計算用。追跡は一定価格以上のスキンのみ) ---
  const today = new Date().toISOString().slice(0, 10);
  const cutoff = new Date(Date.now() - HISTORY_KEEP_DAYS * 24 * 3600e3)
    .toISOString()
    .slice(0, 10);
  const history = (await readJson(path.join(RAW_DIR, "history.json"), { items: {} })).items;
  for (const i of items) {
    if (i.price < MIN_TRACK_USD || i.qty < MIN_TRACK_QTY) continue;
    const h = (history[i.name] ??= []);
    // 同日再実行は上書き
    const idx = h.findIndex(([d]) => d === today);
    const entry = [today, i.price];
    if (idx >= 0) h[idx] = entry;
    else h.push(entry);
    history[i.name] = h.filter(([d]) => d >= cutoff);
  }
  // 追跡対象から外れたスキンの履歴も期限切れ分を掃除
  for (const name of Object.keys(history)) {
    history[name] = history[name].filter(([d]) => d >= cutoff);
    if (history[name].length === 0) delete history[name];
  }

  await fs.writeFile(
    path.join(RAW_DIR, "history.json"),
    JSON.stringify({ updatedAt: new Date().toISOString(), items: history }),
  );
  await fs.writeFile(
    path.join(RAW_DIR, "items.json"),
    JSON.stringify({ fetchedAt: new Date().toISOString(), items }),
  );
  console.log(
    `fetch: done (${items.length} priced items, ${Object.keys(history).length} tracked in history)`,
  );
  return { ok: true };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  fetchAll().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
