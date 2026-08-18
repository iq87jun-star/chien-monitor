// ステップ2: 集計・差分検知
// data/raw/ を読み、円換算・騰落率を計算してサイト表示用JSON(data/site/)と
// 変化検知結果(changes.json)を生成する
import fs from "node:fs/promises";
import path from "node:path";
import { RAW_DIR, SITE_DIR, MIN_RANKING_EUR, SIGNIFICANT_CHANGE_PCT } from "./config.mjs";

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

  const raw = await readJson(path.join(RAW_DIR, "cards.json"));
  const fx = await readJson(path.join(RAW_DIR, "fx.json"));

  // 生データが無い(初回かつAPI障害)場合はメンテナンス表示用のJSONを書いて終了する
  if (!raw || !Array.isArray(raw.cards) || raw.cards.length === 0) {
    await write("economy", { available: false, generatedAt });
    await write("changes", { generatedAt, hasSignificantChange: false, bigMoverCount: 0 });
    console.warn("aggregate: raw data missing — wrote maintenance economy.json (available: false)");
    return { hasSignificantChange: false };
  }

  const eurJpy = fx?.rates?.JPY ?? null;
  const toJpy = (eur) => (eurJpy ? Math.round(eur * eurJpy) : null);

  // --- カードごとに円換算と騰落率(7日/30日)を計算 ---
  const cards = raw.cards.map((c) => ({
    id: c.id,
    name: c.name,
    set: c.set,
    localId: c.localId,
    rarity: c.rarity,
    image: c.image,
    eur: round2(c.eur),
    jpy: toJpy(c.eur),
    // Cardmarketのavg1(直近1日平均)とavg7/avg30(7日/30日平均)の乖離を騰落率として使う
    change7d: c.avg7 ? round1(((c.eur - c.avg7) / c.avg7) * 100) : null,
    change30d: c.avg30 ? round1(((c.eur - c.avg30) / c.avg30) * 100) : null,
    usdMarket: c.usdMarket != null ? round2(c.usdMarket) : null,
  }));

  // --- 騰落ランキング: 少額カードの変動率ノイズを避けるため最低価格で足切り ---
  const liquid = cards.filter((c) => c.eur >= MIN_RANKING_EUR && c.change7d != null);
  const gainers = [...liquid].sort((a, b) => b.change7d - a.change7d).slice(0, 10);
  const losers = [...liquid].sort((a, b) => a.change7d - b.change7d).slice(0, 10);
  const expensive = [...cards].sort((a, b) => b.eur - a.eur).slice(0, 10);

  // --- セット別サマリー(各セットの最高額カード=当たり枠) ---
  const setSummaries = (raw.sets ?? []).map((s) => {
    const inSet = cards.filter((c) => c.set === s.name);
    const top = [...inSet].sort((a, b) => b.eur - a.eur)[0] ?? null;
    return {
      id: s.id,
      name: s.name,
      releaseDate: s.releaseDate,
      pricedCards: inSet.length,
      topCard: top && { name: top.name, eur: top.eur, jpy: top.jpy, image: top.image },
    };
  });

  const totals = {
    cardsFetched: raw.cards.length,
    rankedCards: liquid.length,
    sets: raw.sets?.length ?? 0,
  };

  // --- 差分検知: 前回のsiteデータと比較 ---
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
    fx: eurJpy ? { eurJpy: round2(eurJpy), date: fx.date ?? null } : null,
    totals,
    sets: setSummaries,
    gainers,
    losers,
    expensive,
  });
  await write("changes", { generatedAt, ...changes });

  console.log(
    `aggregate: done (cards=${totals.cardsFetched}, ranked=${totals.rankedCards}, ` +
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
