// ステップ1: データ収集
// data/watchlist.json のアイテムIDをUniversalisの集計APIに問い合わせ、data/raw/market.json に保存する
import fs from "node:fs/promises";
import path from "node:path";
import {
  DATA_DIR,
  RAW_DIR,
  USER_AGENT,
  UNIVERSALIS_BASE,
  REGION,
  BATCH_SIZE,
} from "./config.mjs";

async function fetchJson(url, retries = 3) {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, {
        headers: { "User-Agent": USER_AGENT, Accept: "application/json" },
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

export async function fetchAll() {
  await fs.mkdir(RAW_DIR, { recursive: true });

  const watchlist = JSON.parse(
    await fs.readFile(path.join(DATA_DIR, "watchlist.json"), "utf8"),
  );
  console.log(`watchlist: ${watchlist.length} items`);

  // 100件ずつバッチで集計APIに問い合わせる(連続アクセスを避けて少し間隔を置く)
  const results = [];
  for (let i = 0; i < watchlist.length; i += BATCH_SIZE) {
    const batch = watchlist.slice(i, i + BATCH_SIZE);
    const ids = batch.map((w) => w.id).join(",");
    const data = await fetchJson(
      `${UNIVERSALIS_BASE}/aggregated/${REGION}/${ids}`,
    );
    results.push(...(data.results ?? []));
    if (i + BATCH_SIZE < watchlist.length) {
      await new Promise((r) => setTimeout(r, 1000));
    }
  }

  await fs.writeFile(
    path.join(RAW_DIR, "market.json"),
    JSON.stringify({ fetchedAt: new Date().toISOString(), region: REGION, results }, null, 1),
  );

  console.log(`fetch: done (${results.length} items with data)`);
  return { count: results.length };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  fetchAll().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
