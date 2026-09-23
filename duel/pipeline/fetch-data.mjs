// ステップ1: データ収集
// YGOPRODeck APIから全カードの海外価格(Cardmarket/TCGplayer)を1リクエストで取得し、
// 必要な項目だけに絞って data/raw/ に保存する。価格履歴も自前で蓄積する
// (このAPIは現在価格のみで過去平均を持たないため)。
// APIが一時的に落ちていても既存の生データを壊さないよう、失敗時は警告のみで正常終了する。
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  USER_AGENT,
  YGO_API,
  FX_URL,
  MIN_TRACK_EUR,
  HISTORY_KEEP_DAYS,
  YGORES_NAME_INDEX,
} from "./config.mjs";

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
      console.log(`fetch: fx EUR/JPY=${fx.rates.JPY} EUR/USD=${fx.rates.USD}`);
    }
  } catch (err) {
    console.warn(`fetch: fx unavailable — keeping existing fx.json (${err.message})`);
  }

  // --- 全カード取得(YGOPRODeckのガイドラインに従い1リクエストで全件) ---
  let body;
  try {
    body = await fetchJson(YGO_API);
  } catch (err) {
    console.warn(`fetch: ygoprodeck unavailable — keeping existing raw data (${err.message})`);
    return { ok: false };
  }
  const all = body?.data;
  if (!Array.isArray(all) || all.length === 0) {
    console.warn("fetch: response had no cards — keeping existing raw data");
    return { ok: false };
  }

  // 必要項目だけに絞る(生データを軽くしてgitに収める)
  const cards = [];
  for (const c of all) {
    const p = c.card_prices?.[0];
    if (!p) continue;
    const eur = parseFloat(p.cardmarket_price) || 0;
    const usd = parseFloat(p.tcgplayer_price) || 0;
    if (eur <= 0 && usd <= 0) continue;
    cards.push({
      id: c.id,
      name: c.name,
      type: c.humanReadableCardType ?? c.type,
      archetype: c.archetype ?? null,
      eur,
      usd,
      sets: (c.card_sets ?? []).length,
      ban: c.banlist_info?.ban_tcg ?? null,
    });
  }

  // --- 価格履歴の蓄積(騰落率の計算用。追跡は一定価格以上のカードのみ) ---
  const today = new Date().toISOString().slice(0, 10);
  const cutoff = new Date(Date.now() - HISTORY_KEEP_DAYS * 24 * 3600e3)
    .toISOString()
    .slice(0, 10);
  const history = (await readJson(path.join(RAW_DIR, "history.json"), { cards: {} })).cards;
  for (const c of cards) {
    if (c.eur < MIN_TRACK_EUR) continue;
    const h = (history[c.id] ??= []);
    // 同日再実行は上書き
    const idx = h.findIndex(([d]) => d === today);
    const entry = [today, c.eur, c.usd];
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
    JSON.stringify({ fetchedAt: new Date().toISOString(), cards }),
  );
  console.log(
    `fetch: done (${cards.length} priced cards, ${Object.keys(history).length} tracked in history)`,
  );
  await fetchJaNames(cards);
  return { ok: true };
}

// 英語名→日本語(OCG)名の対応表を data/raw/ja-names.json に保存する(ブラウザ拡張用)。
// ygoresources の言語別「カード名→KonamiID」索引を英語・日本語で突き合わせる。
// 日本語側には漢字表記と読み仮名の両方が入っていることがあるので両方残す。
// 失敗しても致命ではない(既存の対応表を保持)。対象は履歴追跡と同じ価格帯のカードのみ
async function fetchJaNames(cards) {
  let en;
  let ja;
  try {
    [en, ja] = await Promise.all([
      fetchJson(`${YGORES_NAME_INDEX}/en`),
      fetchJson(`${YGORES_NAME_INDEX}/ja`),
    ]);
  } catch (err) {
    console.warn(`fetch: ja names unavailable — keeping existing ja-names.json (${err.message})`);
    return;
  }
  const jaById = new Map();
  for (const [name, ids] of Object.entries(ja)) {
    for (const id of ids) {
      if (!jaById.has(id)) jaById.set(id, []);
      jaById.get(id).push(name);
    }
  }
  const names = {};
  for (const c of cards) {
    if (c.eur < MIN_TRACK_EUR) continue;
    const jaNames = new Set((en[c.name] ?? []).flatMap((id) => jaById.get(id) ?? []));
    if (jaNames.size > 0) names[c.name] = [...jaNames];
  }
  const count = Object.keys(names).length;
  if (count === 0) {
    console.warn("fetch: ja names matched nothing — keeping existing ja-names.json");
    return;
  }
  // 対応表はほとんど変わらないので、変化があった時だけ書き換える(毎回のコミット差分を避ける)
  const file = path.join(RAW_DIR, "ja-names.json");
  const prev = await readJson(file);
  if (JSON.stringify(prev?.names) === JSON.stringify(names)) {
    console.log(`fetch: ja names unchanged (${count} cards)`);
    return;
  }
  await fs.writeFile(file, JSON.stringify({ fetchedAt: new Date().toISOString(), names }));
  console.log(`fetch: ja names for ${count} cards`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  fetchAll().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
