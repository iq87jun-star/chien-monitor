// ステップ1: データ収集
// Scryfall APIから「紙で発売済みの直近セット」の全カード価格(TCGplayer USD/Cardmarket EUR)を
// 取得し、必要な項目だけに絞って data/raw/ に保存する。価格履歴も自前で蓄積する
// (Scryfallは現在価格のみで過去平均を持たないため)。
// APIが一時的に落ちていても既存の生データを壊さないよう、失敗時は警告のみで正常終了する。
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  USER_AGENT,
  SCRYFALL_BASE,
  REQUEST_DELAY_MS,
  FX_URL,
  MONITOR_SETS,
  SET_CANDIDATES,
  MONITOR_SET_TYPES,
  MIN_PRICED_CARDS,
  MIN_TRACK_USD,
  HISTORY_KEEP_DAYS,
} from "./config.mjs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchJson(url, retries = 3) {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, {
        headers: { Accept: "application/json", "User-Agent": USER_AGENT },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
      return await res.json();
    } catch (err) {
      if (attempt >= retries) throw err;
      const waitMs = 2000 * 2 ** attempt;
      console.warn(`fetch failed (${err.message}), retrying in ${waitMs}ms`);
      await sleep(waitMs);
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

// Scryfallの検索結果をページ送りしながら全件取得する
async function searchAll(query) {
  const results = [];
  let url = `${SCRYFALL_BASE}/cards/search?q=${encodeURIComponent(query)}&unique=prints&order=set`;
  while (url) {
    const page = await fetchJson(url);
    results.push(...(page.data ?? []));
    url = page.has_more ? page.next_page : null;
    await sleep(REQUEST_DELAY_MS);
  }
  return results;
}

// 代表価格の抽出。通常版USDを優先し、無ければFoil版USD(foilOnlyフラグ付き)
function extractPricing(card) {
  const usd = parseFloat(card.prices?.usd) || 0;
  const usdFoil = parseFloat(card.prices?.usd_foil) || 0;
  const eur = parseFloat(card.prices?.eur) || parseFloat(card.prices?.eur_foil) || 0;
  const price = usd > 0 ? usd : usdFoil;
  if (price <= 0) return null;
  return { usd: price, foilOnly: usd <= 0, eur: eur > 0 ? eur : null };
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
      console.log(`fetch: fx USD/JPY=${fx.rates.JPY} USD/EUR=${fx.rates.EUR}`);
    }
  } catch (err) {
    console.warn(`fetch: fx unavailable — keeping existing fx.json (${err.message})`);
  }

  // --- セット一覧から「紙で発売済み」の候補を新しい順に選ぶ ---
  let setList;
  try {
    setList = (await fetchJson(`${SCRYFALL_BASE}/sets`)).data;
  } catch (err) {
    console.warn(`fetch: scryfall unavailable — keeping existing raw data (${err.message})`);
    return { ok: false };
  }
  if (!Array.isArray(setList) || setList.length === 0) {
    console.warn("fetch: set list empty — keeping existing raw data");
    return { ok: false };
  }
  const today = new Date().toISOString().slice(0, 10);
  const candidates = setList
    .filter(
      (s) =>
        !s.digital &&
        s.card_count > 0 &&
        s.released_at &&
        s.released_at <= today &&
        MONITOR_SET_TYPES.includes(s.set_type),
    )
    .sort((a, b) => (a.released_at < b.released_at ? 1 : -1))
    .slice(0, SET_CANDIDATES);

  // --- 各候補セットの全カードを取得し、価格が付いているセットだけ監視対象にする ---
  // (発売直後のセットは価格マッピングが揃うまで数日かかることがある)
  const monitored = [];
  const cards = [];
  for (const s of candidates) {
    if (monitored.length >= MONITOR_SETS) break;
    let prints;
    try {
      prints = await searchAll(`e:${s.code} game:paper`);
    } catch (err) {
      console.warn(`fetch: set ${s.code} failed (${err.message})`);
      continue;
    }
    const priced = [];
    for (const c of prints) {
      const pricing = extractPricing(c);
      if (!pricing) continue;
      priced.push({
        id: c.id,
        name: c.name,
        set: s.name,
        setCode: s.code,
        collector: c.collector_number,
        rarity: c.rarity ?? null,
        ...pricing,
      });
    }
    if (priced.length < MIN_PRICED_CARDS) {
      console.log(`fetch: ${s.name} (${s.code}) — only ${priced.length} priced, skipping`);
      continue;
    }
    monitored.push({
      code: s.code,
      name: s.name,
      releaseDate: s.released_at,
      cardCount: s.card_count,
      pricedCards: priced.length,
    });
    cards.push(...priced);
    console.log(`fetch: ${s.name} (${s.code}) — ${priced.length}/${prints.length} cards priced`);
  }

  if (cards.length === 0) {
    console.warn("fetch: no priced cards — keeping existing raw data");
    return { ok: false };
  }

  // --- 価格履歴の蓄積(騰落率の計算用。追跡は一定価格以上のカードのみ) ---
  const cutoff = new Date(Date.now() - HISTORY_KEEP_DAYS * 24 * 3600e3)
    .toISOString()
    .slice(0, 10);
  const history = (await readJson(path.join(RAW_DIR, "history.json"), { cards: {} })).cards;
  for (const c of cards) {
    if (c.usd < MIN_TRACK_USD) continue;
    const h = (history[c.id] ??= []);
    // 同日再実行は上書き
    const idx = h.findIndex(([d]) => d === today);
    const entry = [today, c.usd];
    if (idx >= 0) h[idx] = entry;
    else h.push(entry);
    history[c.id] = h.filter(([d]) => d >= cutoff);
  }
  // 追跡対象から外れたカードの履歴も期限切れ分を掃除
  for (const id of Object.keys(history)) {
    history[id] = history[id].filter(([d]) => d >= cutoff);
    if (history[id].length === 0) delete history[id];
  }

  await fs.writeFile(
    path.join(RAW_DIR, "history.json"),
    JSON.stringify({ updatedAt: new Date().toISOString(), cards: history }),
  );
  await fs.writeFile(
    path.join(RAW_DIR, "cards.json"),
    JSON.stringify({ fetchedAt: new Date().toISOString(), sets: monitored, cards }),
  );
  console.log(
    `fetch: done (${cards.length} priced cards from ${monitored.length} sets, ` +
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
