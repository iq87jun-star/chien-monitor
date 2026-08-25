// ステップ2: 集計・差分検知
// data/raw/items.json(日次取引統計)を読み、現在価格・騰落率・取引量を計算して
// サイト表示用JSON(data/site/)と変化検知結果(changes.json)を生成する
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  SITE_DIR,
  WFM_ASSET_BASE,
  MIN_RANKING_PLAT,
  MIN_VOLUME_7D,
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

  if (!raw || !Array.isArray(raw.items) || raw.items.length === 0) {
    await write("economy", { available: false, generatedAt });
    await write("changes", { generatedAt, hasSignificantChange: false, bigMoverCount: 0 });
    console.warn("aggregate: raw data missing — wrote maintenance economy.json (available: false)");
    return { hasSignificantChange: false };
  }

  // --- 各アイテム: 最新日の中央値を現在価格とし、約7日前の中央値と比較 ---
  const windowStart = new Date(Date.now() - CHANGE_WINDOW_DAYS * 24 * 3600e3)
    .toISOString()
    .slice(0, 10);
  const volumeStart = new Date(Date.now() - 7 * 24 * 3600e3).toISOString().slice(0, 10);

  const items = raw.items
    .map((i) => {
      const days = i.days ?? [];
      if (days.length === 0) return null;
      const [, price] = days[days.length - 1];
      if (!(price > 0)) return null;
      // 窓の起点以前で最も新しい日。無ければ保持分の最古を代用
      const before = days.filter(([d]) => d <= windowStart);
      const [, base] = before.length > 0 ? before[before.length - 1] : days[0];
      const vol7d = days
        .filter(([d]) => d >= volumeStart)
        .reduce((sum, [, , v]) => sum + (v ?? 0), 0);
      return {
        slug: i.slug,
        name: i.name,
        group: i.group,
        icon: i.thumb ? WFM_ASSET_BASE + i.thumb : null,
        price,
        change7d: base > 0 && days.length >= 2 ? round1(((price - base) / base) * 100) : null,
        vol7d,
      };
    })
    .filter(Boolean);

  // --- ランキング: 安値・薄い板のノイズを避けるため足切り ---
  const liquid = items.filter(
    (i) => i.price >= MIN_RANKING_PLAT && i.vol7d >= MIN_VOLUME_7D && i.change7d != null,
  );
  const gainers = [...liquid].sort((a, b) => b.change7d - a.change7d).slice(0, 10);
  const losers = [...liquid].sort((a, b) => a.change7d - b.change7d).slice(0, 10);
  const expensive = [...items].sort((a, b) => b.price - a.price).slice(0, 10);
  const mostTraded = [...items].sort((a, b) => b.vol7d - a.vol7d).slice(0, 10);

  const totals = {
    itemsWatched: items.length,
    rankedItems: liquid.length,
  };

  const prevEconomy = await readJson(path.join(SITE_DIR, "economy.json"));
  const bigMovers = [...gainers, ...losers].filter(
    (i) => Math.abs(i.change7d) >= SIGNIFICANT_CHANGE_PCT,
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
    mostTraded,
  });
  await write("changes", { generatedAt, ...changes });

  console.log(
    `aggregate: done (items=${totals.itemsWatched}, ranked=${totals.rankedItems}, ` +
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
