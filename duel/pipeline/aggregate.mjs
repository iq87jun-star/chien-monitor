// ステップ2: 集計・差分検知
// data/raw/ を読み、円換算・騰落率(自前履歴ベース)を計算して
// サイト表示用JSON(data/site/)と変化検知結果(changes.json)を生成する
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  SITE_DIR,
  MIN_RANKING_EUR,
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

  const raw = await readJson(path.join(RAW_DIR, "cards.json"));
  const fx = await readJson(path.join(RAW_DIR, "fx.json"));
  const history = (await readJson(path.join(RAW_DIR, "history.json"), { cards: {} })).cards;

  if (!raw || !Array.isArray(raw.cards) || raw.cards.length === 0) {
    await write("economy", { available: false, generatedAt });
    await write("changes", { generatedAt, hasSignificantChange: false, bigMoverCount: 0 });
    console.warn("aggregate: raw data missing — wrote maintenance economy.json (available: false)");
    return { hasSignificantChange: false };
  }

  const eurJpy = fx?.rates?.JPY ?? null;
  const toJpy = (eur) => (eurJpy ? Math.round(eur * eurJpy) : null);

  // --- 履歴からN日前の価格を引いて騰落率を計算 ---
  const windowStart = new Date(Date.now() - CHANGE_WINDOW_DAYS * 24 * 3600e3)
    .toISOString()
    .slice(0, 10);
  const baseline = (id) => {
    const h = history[id];
    if (!h || h.length < 2) return null;
    // 窓の起点以前で最も新しいエントリ。無ければ履歴の最古を代用(蓄積初期用)
    const before = h.filter(([d]) => d <= windowStart);
    const [, eur] = before.length > 0 ? before[before.length - 1] : h[0];
    return eur > 0 ? eur : null;
  };

  const cards = raw.cards.map((c) => {
    const base = baseline(c.id);
    return {
      id: c.id,
      name: c.name,
      type: c.type,
      archetype: c.archetype,
      ban: c.ban,
      eur: round2(c.eur),
      usd: round2(c.usd),
      jpy: toJpy(c.eur),
      change7d: base != null ? round1(((c.eur - base) / base) * 100) : null,
    };
  });

  // --- ランキング ---
  const liquid = cards.filter((c) => c.eur >= MIN_RANKING_EUR && c.change7d != null);
  const gainers = [...liquid].sort((a, b) => b.change7d - a.change7d).slice(0, 10);
  const losers = [...liquid].sort((a, b) => a.change7d - b.change7d).slice(0, 10);
  const expensive = [...cards].sort((a, b) => b.eur - a.eur).slice(0, 10);

  // --- 禁止・制限(TCG)カードの高額どころ(海外セラー向けの独自コーナー) ---
  const banned = cards
    .filter((c) => c.ban && c.eur >= MIN_RANKING_EUR)
    .sort((a, b) => b.eur - a.eur)
    .slice(0, 10);

  const totals = {
    cardsFetched: raw.cards.length,
    rankedCards: liquid.length,
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
    fx: eurJpy ? { eurJpy: round2(eurJpy), date: fx.date ?? null } : null,
    totals,
    gainers,
    losers,
    expensive,
    banned,
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
