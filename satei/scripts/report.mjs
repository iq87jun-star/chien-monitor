// 相場レポート(game-souba.com/hoyo/souba/)のデータを作り、public/report.json に書き出す。
//   GAMETRADE_INGEST_TOKEN=<合言葉> node satei/scripts/report.mjs   (または --from <dir>)
//
// ゲームトレードで売れたアカウントを、価格帯とキャラごとに集計する(キャラはタイトル・説明文から読む)。

import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { CHARS } from "../public/lib/chars.js";
import { parseRoster } from "../public/lib/features.js";
import { loadSold } from "./data.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const MIN_COUNT = 20; // これより少ないキャラは表に出さない
const MIN_C6 = 5; // 完凸の相場はこの件数以上ある時だけ出す
const BANDS = [
  [10000, 30000, "1万〜3万円"],
  [30000, 50000, "3万〜5万円"],
  [50000, 100000, "5万〜10万円"],
  [100000, 200000, "10万〜20万円"],
  [200000, Infinity, "20万円以上"],
];

const median = (a) => {
  if (!a.length) return null;
  const s = [...a].sort((x, y) => x - y);
  const m = s.length >> 1;
  return Math.round(s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2);
};

export function summarize(game, rows) {
  const prices = rows.map((r) => r.price);
  const chars = new Map();
  for (const r of rows) {
    for (const [name, { cons }] of Object.entries(parseRoster(`${r.name}\n${r.description ?? ""}`, game))) {
      const c = chars.get(name) ?? { all: [], c6: [] };
      c.all.push(r.price);
      if (cons === 6) c.c6.push(r.price);
      chars.set(name, c);
    }
  }
  return {
    n: rows.length,
    median: median(prices),
    bands: BANDS.map(([lo, hi, label]) => ({ label, n: prices.filter((p) => p >= lo && p < hi).length })),
    characters: [...chars]
      .filter(([, c]) => c.all.length >= MIN_COUNT)
      .map(([name, c]) => ({
        name,
        n: c.all.length,
        median: median(c.all),
        c6: c.c6.length >= MIN_C6 ? { n: c.c6.length, median: median(c.c6) } : null,
      }))
      .sort((a, b) => b.median - a.median),
  };
}

const report = { updatedAt: new Date().toISOString(), source: "ゲームトレード(1万〜50万円で売れたアカウント)", games: {} };
for (const game of Object.keys(CHARS)) {
  report.games[game] = summarize(game, await loadSold(game));
  console.log(`${game}: n=${report.games[game].n} median=${report.games[game].median} chars=${report.games[game].characters.length}`);
}
await writeFile(join(here, "../public/report.json"), JSON.stringify(report));
