// ステップ2: 集計・差分検知
// data/raw/market.json を読み、価格履歴(data/history.json)を更新し、
// サイト表示用JSON(data/site/economy.json)と変化検知結果(changes.json)を生成する
import fs from "node:fs/promises";
import path from "node:path";
import {
  DATA_DIR,
  RAW_DIR,
  SITE_DIR,
  HISTORY_WINDOW_MS,
  SIGNIFICANT_CHANGE_PCT,
} from "./config.mjs";

async function readJson(file, fallback = null) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

const round1 = (n) => Math.round(n * 10) / 10;

// nq優先・なければhqから、region集計値を取り出す
function pick(result, section, field) {
  return (
    result?.nq?.[section]?.region?.[field] ??
    result?.hq?.[section]?.region?.[field] ??
    null
  );
}

export async function aggregate() {
  await fs.mkdir(SITE_DIR, { recursive: true });

  const watchlist = await readJson(path.join(DATA_DIR, "watchlist.json"));
  const raw = await readJson(path.join(RAW_DIR, "market.json"));
  if (!watchlist || !raw) throw new Error("raw data missing — run fetch first");

  const byId = new Map(raw.results.map((r) => [r.itemId, r]));

  // --- 各アイテムの現在値 ---
  const items = [];
  for (const w of watchlist) {
    const r = byId.get(w.id);
    if (!r) continue;
    const avg = pick(r, "averageSalePrice", "price");
    const minListing = pick(r, "minListing", "price");
    const velocity = pick(r, "dailySaleVelocity", "quantity");
    const price = avg != null ? Math.round(avg) : minListing != null ? Math.round(minListing) : null;
    if (price == null) continue;
    items.push({
      id: w.id,
      name: w.name,
      price,
      minListing: minListing != null ? Math.round(minListing) : null,
      velocity: velocity != null ? round1(velocity) : 0,
    });
  }

  // --- 価格履歴の更新(7日窓・変動率の根拠) ---
  const historyPath = path.join(DATA_DIR, "history.json");
  const history = (await readJson(historyPath, {})) ?? {};
  const now = Date.now();
  const cutoff = now - HISTORY_WINDOW_MS;
  const firstRun = Object.keys(history).length === 0;

  for (const it of items) {
    const entries = (history[it.id] ?? []).filter((e) => e.t >= cutoff);
    entries.push({ t: now, p: it.price });
    history[it.id] = entries;
    // 窓内の最古サンプルとの比較(サンプル1件のみなら0 — 観測開始から蓄積される)
    const oldest = entries[0];
    it.samples = entries.length;
    it.change7d =
      entries.length >= 2 && oldest.p > 0
        ? round1(((it.price - oldest.p) / oldest.p) * 100)
        : 0;
  }
  await fs.writeFile(historyPath, JSON.stringify(history, null, 1));

  // --- ランキング ---
  const expensive = [...items].sort((a, b) => b.price - a.price).slice(0, 10);
  const topVolume = [...items].sort((a, b) => b.velocity - a.velocity).slice(0, 10);
  const withHistory = items.filter((i) => i.samples >= 2);
  const gainers = [...withHistory].sort((a, b) => b.change7d - a.change7d).slice(0, 10);
  const losers = [...withHistory].sort((a, b) => a.change7d - b.change7d).slice(0, 10);

  // --- 差分検知 ---
  const bigMovers = withHistory.filter(
    (i) => Math.abs(i.change7d) >= SIGNIFICANT_CHANGE_PCT,
  );
  const changes = {
    hasSignificantChange: firstRun || bigMovers.length > 0,
    firstRun,
    bigMoverCount: bigMovers.length,
  };

  const generatedAt = new Date().toISOString();
  const write = (name, data) =>
    fs.writeFile(path.join(SITE_DIR, `${name}.json`), JSON.stringify(data, null, 1));

  await write("economy", {
    region: "Japan",
    generatedAt,
    items,
    expensive,
    topVolume,
    gainers,
    losers,
  });
  await write("changes", { generatedAt, ...changes });

  console.log(
    `aggregate: done (items=${items.length}, withHistory=${withHistory.length}, ` +
      `significant=${changes.hasSignificantChange})`,
  );
  return changes;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  aggregate().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
