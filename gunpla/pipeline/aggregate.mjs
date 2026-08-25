// ステップ2: 集計・差分検知
// data/raw/ とウォッチリストを突き合わせ、騰落率(自前履歴ベース)・定価比プレミア率・
// 初回記録比を計算してサイト表示用JSON(data/site/)と変化検知結果(changes.json)を生成する
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  SITE_DIR,
  CONTENT_DIR,
  MIN_RANKING_JPY,
  SCARCE_MAX_COUNT,
  CHANGE_WINDOW_DAYS,
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

export async function aggregate() {
  await fs.mkdir(SITE_DIR, { recursive: true });

  const generatedAt = new Date().toISOString();
  const write = (name, data) =>
    fs.writeFile(path.join(SITE_DIR, `${name}.json`), JSON.stringify(data, null, 1));

  const raw = await readJson(path.join(RAW_DIR, "items.json"));
  const history = (await readJson(path.join(RAW_DIR, "history.json"), { items: {} })).items;
  const watchlist = (await readJson(path.join(CONTENT_DIR, "watchlist.json"), { items: [] }))
    .items;
  const meta = new Map(watchlist.map((w) => [w.id, w]));

  if (!raw || !Array.isArray(raw.items) || raw.items.length === 0) {
    await write("economy", { available: false, generatedAt });
    await write("changes", { generatedAt, hasSignificantChange: false, bigMoverCount: 0 });
    console.warn("aggregate: raw data missing — wrote maintenance economy.json (available: false)");
    return { hasSignificantChange: false };
  }

  // --- 履歴からN日前の中央値を引いて騰落率を計算 ---
  const windowStart = new Date(Date.now() - CHANGE_WINDOW_DAYS * 24 * 3600e3)
    .toISOString()
    .slice(0, 10);
  const baseline = (id) => {
    const h = history[id];
    if (!h || h.length < 2) return null;
    // 窓の起点以前で最も新しいエントリ。無ければ履歴の最古を代用(蓄積初期用)
    const before = h.filter(([d]) => d <= windowStart);
    const [, , med] = before.length > 0 ? before[before.length - 1] : h[0];
    return med > 0 ? med : null;
  };

  const items = raw.items
    .filter((it) => meta.has(it.id) && it.median != null)
    .map((it) => {
      const w = meta.get(it.id);
      const base = baseline(it.id);
      const first = history[it.id]?.[0]?.[2] ?? null; // 初回記録時の中央値
      return {
        id: it.id,
        name: w.name,
        brand: w.brand,
        category: w.category,
        count: it.count,
        low: it.low,
        median: it.median,
        url: it.url,
        shop: it.shop,
        msrp: w.msrp ?? null,
        // 定価比プレミア率(%)。定価が分かるアイテムのみ
        premium: w.msrp ? round1((it.low / w.msrp - 1) * 100) : null,
        change7d: base != null ? round1(((it.median - base) / base) * 100) : null,
        // 初回記録時の中央値からの変化率(%)。定価が無いアイテムの長期目安
        sinceFirst:
          first != null && first > 0 ? round1(((it.median - first) / first) * 100) : null,
      };
    });

  // --- ランキング ---
  const liquid = items.filter((c) => c.median >= MIN_RANKING_JPY && c.change7d != null);
  const gainers = [...liquid].sort((a, b) => b.change7d - a.change7d).slice(0, 10);
  const losers = [...liquid].sort((a, b) => a.change7d - b.change7d).slice(0, 10);
  const expensive = [...items].sort((a, b) => b.low - a.low).slice(0, 10);
  const premium = items
    .filter((c) => c.premium != null)
    .sort((a, b) => b.premium - a.premium)
    .slice(0, 10);
  const scarce = items
    .filter((c) => c.count > 0 && c.count <= SCARCE_MAX_COUNT)
    .sort((a, b) => b.low - a.low)
    .slice(0, 10);

  const totals = {
    itemsTracked: items.length,
    rankedItems: liquid.length,
  };

  const prevEconomy = await readJson(path.join(SITE_DIR, "economy.json"));
  const bigMovers = [...gainers, ...losers].filter(
    (c) => Math.abs(c.change7d) >= SIGNIFICANT_CHANGE_PCT,
  );
  const changes = {
    hasSignificantChange: !prevEconomy || prevEconomy.available === false || bigMovers.length > 0,
    bigMoverCount: bigMovers.length,
  };

  await write("economy", {
    available: true,
    generatedAt,
    fetchedAt: raw.fetchedAt,
    totals,
    gainers,
    losers,
    expensive,
    premium,
    scarce,
  });
  await write("changes", { generatedAt, ...changes });

  console.log(
    `aggregate: done (items=${totals.itemsTracked}, ranked=${totals.rankedItems}, ` +
      `premium=${premium.length}, scarce=${scarce.length}, significant=${changes.hasSignificantChange})`,
  );
  return changes;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  aggregate().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
