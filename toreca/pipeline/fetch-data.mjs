// ステップ1: データ収集
// TCGdex APIからポケカ日本語版セットのカード価格(Cardmarket/TCGplayer)と
// 為替レートを取得し data/raw/ に保存する。
// APIが一時的に落ちていても既存の生データを壊さないよう、失敗時は警告のみで正常終了する。
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  USER_AGENT,
  TCGDEX_BASE,
  FX_URL,
  SET_CANDIDATES,
  MONITOR_SETS,
  PROBE_CARDS,
  FETCH_CONCURRENCY,
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

// 同時実行数を絞ってタスク配列を消化する(1件の失敗はnullにして続行)
async function mapLimit(items, limit, fn) {
  const results = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const i = next++;
      results[i] = await fn(items[i]).catch((err) => {
        console.warn(`item ${i} failed: ${err.message}`);
        return null;
      });
    }
  }
  await Promise.all(Array.from({ length: limit }, worker));
  return results;
}

// variants_detailed から代表価格を抜き出す。
// 複数バリアント(通常/ホロ/リバース)がある場合は現在価格が最も高いものを採用する
// (コレクション需要を反映するのは上位バリアントのため)。
function extractPricing(card) {
  let best = null;
  for (const v of card.variants_detailed ?? []) {
    const cm = v.pricing?.cardmarket;
    const tp = v.pricing?.tcgplayer;
    // Cardmarketは通常面とホロ面の価格を同じオブジェクトに持つため両方を候補にする
    const faces = cm
      ? [
          { avg1: cm.avg1, avg7: cm.avg7, avg30: cm.avg30, trend: cm.trend, low: cm.low },
          {
            avg1: cm["avg1-holo"],
            avg7: cm["avg7-holo"],
            avg30: cm["avg30-holo"],
            trend: cm["trend-holo"],
            low: cm["low-holo"],
          },
        ]
      : [];
    for (const f of faces) {
      const current = f.avg1 ?? f.trend ?? f.avg7;
      if (typeof current !== "number" || current <= 0) continue;
      if (!best || current > best.eur) {
        best = {
          eur: current,
          avg7: typeof f.avg7 === "number" && f.avg7 > 0 ? f.avg7 : null,
          avg30: typeof f.avg30 === "number" && f.avg30 > 0 ? f.avg30 : null,
          variant: v.type,
          updated: cm.updated ?? null,
          usdMarket: null,
        };
      }
    }
    // TCGplayerはUSDの市場価格を参考値として持たせる
    if (best && tp) {
      const market =
        tp.normal?.marketPrice ?? tp.holofoil?.marketPrice ?? tp["reverse-holofoil"]?.marketPrice;
      if (typeof market === "number" && market > 0 && best.usdMarket == null) {
        best.usdMarket = market;
      }
    }
  }
  return best;
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
      console.log(`fetch: fx EUR/JPY=${fx.rates.JPY}`);
    }
  } catch (err) {
    console.warn(`fetch: fx unavailable — keeping existing fx.json (${err.message})`);
  }

  // --- セット一覧(APIは古い順に並ぶため末尾が最新) ---
  let setList;
  try {
    setList = await fetchJson(`${TCGDEX_BASE}/sets`);
  } catch (err) {
    console.warn(`fetch: tcgdex unavailable — keeping existing raw data (${err.message})`);
    return { ok: false };
  }
  if (!Array.isArray(setList) || setList.length === 0) {
    console.warn("fetch: set list empty — keeping existing raw data");
    return { ok: false };
  }

  // 候補セットの詳細を取り、「発売済み(releaseDate <= 今日)かつ価格が付いている」
  // 新しい順に MONITOR_SETS 件選ぶ。価格の有無はセット内から数枚を試し取りして判定する
  // (最新セットはCardmarket価格のマッピングが済んでいないことが多い)
  const candidates = setList.slice(-SET_CANDIDATES).reverse();
  const today = new Date().toISOString().slice(0, 10);
  const monitored = [];
  for (const s of candidates) {
    if (monitored.length >= MONITOR_SETS) break;
    try {
      const detail = await fetchJson(`${TCGDEX_BASE}/sets/${encodeURIComponent(s.id)}`);
      if (!detail.releaseDate || detail.releaseDate > today || !(detail.cards?.length > 0)) {
        continue;
      }
      const step = Math.max(1, Math.floor(detail.cards.length / PROBE_CARDS));
      const probes = detail.cards.filter((_, i) => i % step === 0).slice(0, PROBE_CARDS);
      const probed = await mapLimit(probes, FETCH_CONCURRENCY, (c) =>
        fetchJson(`${TCGDEX_BASE}/cards/${encodeURIComponent(c.id)}`, 1),
      );
      const hasPricing = probed.some((card) => card && extractPricing(card));
      if (!hasPricing) {
        console.log(`fetch: ${detail.name} (${s.id}) — no pricing yet, skipping`);
        continue;
      }
      monitored.push(detail);
    } catch (err) {
      console.warn(`fetch: set ${s.id} failed (${err.message})`);
    }
  }
  if (monitored.length === 0) {
    console.warn("fetch: no released sets found — keeping existing raw data");
    return { ok: false };
  }
  // サイト表示・集計は新しいセット順にする(一覧APIの並びは発売順とは限らない)
  monitored.sort((a, b) => (a.releaseDate < b.releaseDate ? 1 : -1));

  // --- 各セットの全カード詳細(価格つき)を取得 ---
  const cards = [];
  for (const set of monitored) {
    const fetched = await mapLimit(set.cards, FETCH_CONCURRENCY, (c) =>
      fetchJson(`${TCGDEX_BASE}/cards/${encodeURIComponent(c.id)}`, 1),
    );
    let priced = 0;
    for (const card of fetched) {
      if (!card) continue;
      const pricing = extractPricing(card);
      if (!pricing) continue; // 価格が無いカードは監視対象外
      priced++;
      cards.push({
        id: card.id,
        name: card.name,
        set: set.name,
        setId: set.id,
        localId: card.localId,
        rarity: card.rarity ?? null,
        image: card.image ?? null,
        ...pricing,
      });
    }
    console.log(`fetch: ${set.name} (${set.id}) — ${priced}/${set.cards.length} cards priced`);
  }

  if (cards.length === 0) {
    console.warn("fetch: no priced cards — keeping existing raw data");
    return { ok: false };
  }

  await fs.writeFile(
    path.join(RAW_DIR, "cards.json"),
    JSON.stringify(
      {
        fetchedAt: new Date().toISOString(),
        sets: monitored.map((s) => ({
          id: s.id,
          name: s.name,
          releaseDate: s.releaseDate,
          cardCount: s.cards.length,
        })),
        cards,
      },
      null,
      1,
    ),
  );
  console.log(`fetch: done (${cards.length} priced cards from ${monitored.length} sets)`);
  return { ok: true };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  fetchAll().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
