// ステップ2: 集計・差分検知
// data/raw/ を読み、サイト表示用JSON(data/site/)と変化検知結果(changes.json)を生成する
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  SITE_DIR,
  UNIQUE_TYPES,
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

  const leagues = await readJson(path.join(RAW_DIR, "leagues.json"));
  const currencyRaw = await readJson(path.join(RAW_DIR, "currency.json"));
  const newsRaw = await readJson(path.join(RAW_DIR, "news.json"));
  if (!leagues || !currencyRaw) throw new Error("raw data missing — run fetch first");

  const league = leagues.current.id;

  // --- 通貨: Chaos Orb基準のレートに正規化 ---
  const nameById = new Map(
    [...(currencyRaw.core?.items ?? []), ...(currencyRaw.items ?? [])].map((i) => [i.id, i]),
  );
  const lines = currencyRaw.lines ?? [];
  const chaos = lines.find((l) => l.id === "chaos");
  const base = chaos?.primaryValue || 1;

  const currencies = lines
    .filter((l) => typeof l.primaryValue === "number")
    .map((l) => ({
      id: l.id,
      name: nameById.get(l.id)?.name ?? l.id,
      // Chaos Orb 1個に対するレート
      rateInChaos: l.primaryValue / base,
      change7d: round1(l.sparkline?.totalChange ?? 0),
      spark: l.sparkline?.data ?? [],
    }))
    .sort((a, b) => b.rateInChaos - a.rateInChaos);

  // --- ユニーク: 全カテゴリを統合して騰落ランキングを作る ---
  const allUniques = [];
  for (const type of UNIQUE_TYPES) {
    const data = await readJson(path.join(RAW_DIR, `uniques-${type}.json`));
    for (const l of data?.lines ?? []) {
      if (typeof l.chaosValue !== "number") continue;
      allUniques.push({
        name: l.name,
        baseType: l.baseType,
        category: type.replace(/^Unique/, ""),
        value: l.chaosValue,
        listingCount: l.listingCount ?? 0,
        change7d: round1(l.sparkLine?.totalChange ?? 0),
        spark: l.sparkLine?.data ?? [],
        icon: l.icon ?? null,
      });
    }
  }
  // 出品数が少なすぎるものはノイズなので騰落ランキングから除外
  const liquid = allUniques.filter((u) => u.listingCount >= 5);
  const gainers = [...liquid].sort((a, b) => b.change7d - a.change7d).slice(0, 10);
  const losers = [...liquid].sort((a, b) => a.change7d - b.change7d).slice(0, 10);
  const expensive = [...allUniques].sort((a, b) => b.value - a.value).slice(0, 10);

  // --- ニュース: パッチノートらしい項目を判定 ---
  const newsItems = (newsRaw?.appnews?.newsitems ?? []).map((n) => ({
    gid: n.gid,
    title: n.title,
    url: n.url,
    date: n.date,
    excerpt: n.contents,
    isPatch: /patch|hotfix|update|notes|\d+\.\d+\.\d+/i.test(n.title),
  }));

  // --- 差分検知: 前回のsiteデータと比較 ---
  const prevEconomy = await readJson(path.join(SITE_DIR, "economy.json"));
  const prevNews = await readJson(path.join(SITE_DIR, "news.json"));
  const prevGids = new Set((prevNews?.items ?? []).map((n) => n.gid));
  const newPatchNotes = newsItems.filter((n) => n.isPatch && !prevGids.has(n.gid));

  const bigMovers = [...gainers, ...losers].filter(
    (u) => Math.abs(u.change7d) >= SIGNIFICANT_CHANGE_PCT,
  );
  const leagueChanged = prevEconomy && prevEconomy.league !== league;

  const changes = {
    hasSignificantChange:
      !prevEconomy || leagueChanged || newPatchNotes.length > 0 || bigMovers.length > 0,
    leagueChanged: Boolean(leagueChanged),
    newPatchNotes: newPatchNotes.map((n) => ({ gid: n.gid, title: n.title })),
    bigMoverCount: bigMovers.length,
  };

  const generatedAt = new Date().toISOString();
  const write = (name, data) =>
    fs.writeFile(path.join(SITE_DIR, `${name}.json`), JSON.stringify(data, null, 1));

  await write("economy", { league, generatedAt, currencies, gainers, losers, expensive });
  await write("news", { generatedAt, items: newsItems });
  await write("changes", { generatedAt, ...changes });

  console.log(
    `aggregate: done (league=${league}, currencies=${currencies.length}, uniques=${allUniques.length}, ` +
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
