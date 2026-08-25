// ステップ1: データ収集
// warframe.market APIから監視対象(全プライムセット+定番トレード品)の
// 日次取引統計を取得し、直近分だけに絞って data/raw/ に保存する。
// このAPIは90日分の日次統計を持つため、騰落率の履歴を自前で蓄積する必要はない。
// APIが一時的に落ちていても既存の生データを壊さないよう、失敗時は警告のみで正常終了する。
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  USER_AGENT,
  WFM_ITEMS_URL,
  WFM_STATS_URL,
  FETCH_CONCURRENCY,
  REQUEST_DELAY_MS,
  WATCH_EXTRAS,
  KEEP_DAYS,
  MIN_FETCHED_ITEMS,
} from "./config.mjs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function fetchJson(url, retries = 2) {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, {
        headers: {
          Accept: "application/json",
          // 日本語のアイテム名を取得する
          Language: "ja",
          "User-Agent": USER_AGENT,
        },
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

// 同時実行数を絞ってタスク配列を消化する(1件の失敗はnullにして続行)
async function mapLimit(items, limit, fn) {
  const results = new Array(items.length);
  let next = 0;
  async function worker() {
    while (next < items.length) {
      const i = next++;
      results[i] = await fn(items[i]).catch((err) => {
        console.warn(`item ${items[i].slug ?? i} failed: ${err.message}`);
        return null;
      });
    }
  }
  await Promise.all(Array.from({ length: limit }, worker));
  return results;
}

export async function fetchAll() {
  await fs.mkdir(RAW_DIR, { recursive: true });

  // --- 品目一覧(v2)から監視対象を決める ---
  let list;
  try {
    list = (await fetchJson(WFM_ITEMS_URL)).data;
  } catch (err) {
    console.warn(`fetch: warframe.market unavailable — keeping existing raw data (${err.message})`);
    return { ok: false };
  }
  if (!Array.isArray(list) || list.length === 0) {
    console.warn("fetch: item list empty — keeping existing raw data");
    return { ok: false };
  }

  const bySlug = new Map(list.map((i) => [i.slug, i]));
  const watch = [
    ...list.filter((i) => i.slug.endsWith("_prime_set")).map((i) => ({ ...i, group: "prime" })),
    ...WATCH_EXTRAS.filter((s) => bySlug.has(s)).map((s) => ({ ...bySlug.get(s), group: "extra" })),
  ];
  console.log(`fetch: watching ${watch.length} items (${list.length} total on market)`);

  // --- 各アイテムの日次取引統計(v1)。直近KEEP_DAYS日分だけ保持する ---
  const items = (
    await mapLimit(watch, FETCH_CONCURRENCY, async (w) => {
      await sleep(REQUEST_DELAY_MS);
      const stats = await fetchJson(WFM_STATS_URL(w.slug), 1);
      const days = (stats.payload?.statistics_closed?.["90days"] ?? [])
        .slice(-KEEP_DAYS)
        .map((d) => [d.datetime.slice(0, 10), d.median, d.volume]);
      if (days.length === 0) return null;
      const i18n = w.i18n?.ja ?? w.i18n?.en ?? {};
      return {
        slug: w.slug,
        name: i18n.name ?? w.slug,
        group: w.group,
        thumb: i18n.thumb ?? null,
        days,
      };
    })
  ).filter(Boolean);

  if (items.length < MIN_FETCHED_ITEMS) {
    console.warn(
      `fetch: only ${items.length} items fetched (<${MIN_FETCHED_ITEMS}) — keeping existing raw data`,
    );
    return { ok: false };
  }

  await fs.writeFile(
    path.join(RAW_DIR, "items.json"),
    JSON.stringify({ fetchedAt: new Date().toISOString(), items }, null, 1),
  );
  console.log(`fetch: done (${items.length}/${watch.length} watched items with statistics)`);
  return { ok: true };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  fetchAll().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
