// ステップ2: 集計・差分検知
// data/raw/ を読み、円換算・騰落率(自前履歴ベース)を計算して
// サイト表示用JSON(data/site/)と変化検知結果(changes.json)を生成する
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  SITE_DIR,
  MIN_RANKING_USD,
  MIN_RANKING_QTY,
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
const round2 = (n) => Math.round(n * 100) / 100;

export async function aggregate() {
  await fs.mkdir(SITE_DIR, { recursive: true });

  const generatedAt = new Date().toISOString();
  const write = (name, data) =>
    fs.writeFile(path.join(SITE_DIR, `${name}.json`), JSON.stringify(data, null, 1));

  const raw = await readJson(path.join(RAW_DIR, "items.json"));
  const fx = await readJson(path.join(RAW_DIR, "fx.json"));
  const history = (await readJson(path.join(RAW_DIR, "history.json"), { items: {} })).items;

  if (!raw || !Array.isArray(raw.items) || raw.items.length === 0) {
    await write("economy", { available: false, generatedAt });
    await write("changes", { generatedAt, hasSignificantChange: false, bigMoverCount: 0 });
    console.warn("aggregate: raw data missing — wrote maintenance economy.json (available: false)");
    return { hasSignificantChange: false };
  }

  const usdJpy = fx?.rates?.JPY ?? null;
  const toJpy = (usd) => (usdJpy ? Math.round(usd * usdJpy) : null);

  // --- 履歴からN日前の価格を引いて騰落率を計算 ---
  const windowStart = new Date(Date.now() - CHANGE_WINDOW_DAYS * 24 * 3600e3)
    .toISOString()
    .slice(0, 10);
  const baseline = (name) => {
    const h = history[name];
    if (!h || h.length < 2) return null;
    // 窓の起点以前で最も新しいエントリ。無ければ履歴の最古を代用(蓄積初期用)
    const before = h.filter(([d]) => d <= windowStart);
    const [, usd] = before.length > 0 ? before[before.length - 1] : h[0];
    return usd > 0 ? usd : null;
  };

  const items = raw.items.map((i) => {
    const base = baseline(i.name);
    return {
      name: i.name,
      usd: round2(i.price),
      min: i.min != null ? round2(i.min) : null,
      qty: i.qty,
      jpy: toJpy(i.price),
      change7d: base != null ? round1(((i.price - base) / base) * 100) : null,
    };
  });

  // --- ランキング: 少額・板の薄いスキンの変動率ノイズを避けるため足切り ---
  const liquid = items.filter(
    (i) => i.usd >= MIN_RANKING_USD && i.qty >= MIN_RANKING_QTY && i.change7d != null,
  );
  const gainers = [...liquid].sort((a, b) => b.change7d - a.change7d).slice(0, 10);
  const losers = [...liquid].sort((a, b) => a.change7d - b.change7d).slice(0, 10);
  const expensive = [...items].sort((a, b) => b.usd - a.usd).slice(0, 10);

  // --- ナイフ・グローブ(★付きアイテム)の高額どころ(CS2の花形コーナー) ---
  const premium = items
    .filter((i) => i.name.startsWith("★"))
    .sort((a, b) => b.usd - a.usd)
    .slice(0, 10);

  const totals = {
    itemsFetched: raw.items.length,
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
    fx: usdJpy ? { usdJpy: round2(usdJpy), date: fx.date ?? null } : null,
    totals,
    gainers,
    losers,
    expensive,
    premium,
  });
  await write("changes", { generatedAt, ...changes });

  console.log(
    `aggregate: done (items=${totals.itemsFetched}, ranked=${totals.rankedItems}, ` +
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
