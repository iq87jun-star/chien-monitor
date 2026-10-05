// 学習・集計に使う「売れたアカウント」の記録を読む(gametrade-watch の D1 から書き出す)。
//   GAMETRADE_INGEST_TOKEN=<合言葉> で Worker から、--from <dir> なら <dir>/<game>.json から読む

import { readFile } from "node:fs/promises";
import { join } from "node:path";

const WORKER = "https://gametrade-watch.iq87jun.workers.dev";
const args = process.argv.slice(2);
const from = args.includes("--from") ? args[args.indexOf("--from") + 1] : null;
const cache = new Map();

async function fetchAll(game) {
  if (from) return JSON.parse(await readFile(join(from, `${game}.json`), "utf8"));
  const token = process.env.GAMETRADE_INGEST_TOKEN;
  if (!token) throw new Error("GAMETRADE_INGEST_TOKEN が未設定です(または --from を使う)");
  const rows = [];
  for (let after = 0; ; ) {
    const res = await fetch(`${WORKER}/sold/export?game=${game}&after=${after}&limit=2000`, {
      headers: { authorization: `Bearer ${token}`, "user-agent": "satei-train" },
    });
    if (!res.ok) throw new Error(`export: ${res.status} ${await res.text()}`);
    const d = await res.json();
    rows.push(...d.rows);
    if (!d.next) return rows;
    after = d.next;
  }
}

// 個別取引の「〇〇様専用」は除く
export async function loadSold(game) {
  if (!cache.has(game)) cache.set(game, (await fetchAll(game)).filter((r) => !/専用/.test(r.name) && r.price > 0));
  return cache.get(game);
}
