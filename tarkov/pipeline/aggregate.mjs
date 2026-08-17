// ステップ2: 集計・差分検知
// data/raw/items.json を読み、サイト表示用JSON(data/site/)と変化検知結果(changes.json)を生成する
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  SITE_DIR,
  MIN_RANKING_PRICE,
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

  // 生データが無い(初回かつAPI障害)場合はメンテナンス表示用のJSONを書いて終了する
  if (!raw || !Array.isArray(raw.items) || raw.items.length === 0) {
    await write("economy", { available: false, generatedAt });
    await write("changes", { generatedAt, hasSignificantChange: false, bigMoverCount: 0 });
    console.warn("aggregate: raw data missing — wrote maintenance economy.json (available: false)");
    return { hasSignificantChange: false };
  }

  // --- フリマ取引のあるアイテムだけに絞る(プリセット類は重複表示になるため除外) ---
  const tradable = raw.items
    .filter(
      (i) =>
        typeof i.avg24hPrice === "number" &&
        i.avg24hPrice > 0 &&
        !(i.types ?? []).some((t) => String(t).toLowerCase().includes("preset")),
    )
    .map((i) => ({
      name: i.name,
      shortName: i.shortName,
      price: i.avg24hPrice,
      change48h: round1(i.changeLast48hPercent ?? 0),
      icon: i.iconLink ?? null,
    }));

  // --- 騰落ランキング: 安値アイテムの変動率ノイズを避けるため最低価格で足切り ---
  const liquid = tradable.filter((i) => i.price >= MIN_RANKING_PRICE);
  const gainers = [...liquid].sort((a, b) => b.change48h - a.change48h).slice(0, 10);
  const losers = [...liquid].sort((a, b) => a.change48h - b.change48h).slice(0, 10);
  const expensive = [...tradable].sort((a, b) => b.price - a.price).slice(0, 10);

  const totals = {
    itemsFetched: raw.items.length,
    tradableItems: tradable.length,
    rankedItems: liquid.length,
  };

  // --- 差分検知: 前回のsiteデータと比較 ---
  const prevEconomy = await readJson(path.join(SITE_DIR, "economy.json"));
  const bigMovers = [...gainers, ...losers].filter(
    (i) => Math.abs(i.change48h) >= SIGNIFICANT_CHANGE_PCT,
  );
  const changes = {
    // 初回(前回データなし・メンテ状態からの復帰含む)または大きな変動があれば記事生成の対象
    hasSignificantChange: !prevEconomy || prevEconomy.available === false || bigMovers.length > 0,
    bigMoverCount: bigMovers.length,
  };

  await write("economy", {
    available: true,
    generatedAt,
    totals,
    gainers,
    losers,
    expensive,
  });
  await write("changes", { generatedAt, ...changes });

  console.log(
    `aggregate: done (items=${totals.itemsFetched}, tradable=${totals.tradableItems}, ` +
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
