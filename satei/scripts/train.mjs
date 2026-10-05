// 売れたアカウントの記録(gametrade-watch の D1)から値付けモデルを学習し、public/model.json に書き出す。
//
//   GAMETRADE_INGEST_TOKEN=<合言葉> node satei/scripts/train.mjs
//   node satei/scripts/train.mjs --from <dir>   # <dir>/<game>.json(書き出し済みの記録)から学習する
//
// モデル: log(売値) をリッジ回帰で当てる。特徴量はキャラごとの所持・凸数・モチーフ武器と星5の数(public/lib/features.js)。
// 査定額の幅は、交差検証の誤差(log の残差)の分位点から決める。

import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { CHARS } from "../public/lib/chars.js";
import { parseRoster, infoNumber, STAR5_RE, featurize, featureNames } from "../public/lib/features.js";
import { fitRidge, dot } from "../public/lib/model.js";

const here = dirname(fileURLToPath(import.meta.url));
const WORKER = "https://gametrade-watch.iq87jun.workers.dev";
const LAMBDA = 3;
const BUY_RATE = 0.55; // 査定額 = 売れた相場 × この割合(買取額)
const args = process.argv.slice(2);
const from = args.includes("--from") ? args[args.indexOf("--from") + 1] : null;

async function load(game) {
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

const quantile = (a, q) => {
  const s = [...a].sort((x, y) => x - y);
  return s[Math.min(s.length - 1, Math.max(0, Math.round(q * (s.length - 1))))];
};

// 学習に使う1件(個別取引の「〇〇様専用」は除く)
export function example(game, r) {
  const roster = parseRoster(`${r.name}\n${r.description ?? ""}`, game);
  return {
    x: featurize(game, { roster, star5: infoNumber(r.info, STAR5_RE), starter: /初期|リセマラ/.test(r.name) }),
    y: Math.log(r.price),
    mentioned: Object.keys(roster).length,
  };
}

const model = { trainedAt: new Date().toISOString(), buyRate: BUY_RATE, games: {} };
for (const game of Object.keys(CHARS)) {
  const rows = (await load(game)).filter((r) => !/専用/.test(r.name) && r.price > 0);
  const data = rows.map((r) => example(game, r));
  // 5分割の交差検証で、予測と実際の売値のずれ(log)を集める
  const resid = [];
  for (let f = 0; f < 5; f++) {
    const tr = data.filter((_, i) => i % 5 !== f);
    const w = fitRidge(tr.map((d) => d.x), tr.map((d) => d.y), LAMBDA);
    for (const d of data.filter((_, i) => i % 5 === f)) resid.push(d.y - dot(w, d.x));
  }
  const w = fitRidge(data.map((d) => d.x), data.map((d) => d.y), LAMBDA);
  const withChars = data.filter((d) => d.mentioned > 0);
  const absErr = resid.map((r) => Math.abs(Math.exp(r) - 1));
  model.games[game] = {
    n: data.length,
    features: featureNames(game),
    weights: w.map((v) => Math.round(v * 1e5) / 1e5),
    // 出品タイトルに書かれるキャラは数人なので、査定でも上位この人数だけを数える(手持ち全員を足すと高く出すぎる)
    topK: Math.max(3, Math.round(quantile(withChars.map((d) => d.mentioned), 0.75))),
    // 幅: 交差検証の残差の 25%〜75% 点
    band: [quantile(resid, 0.25), quantile(resid, 0.75)].map((v) => Math.round(v * 1e4) / 1e4),
    cv: { medianAbsErr: Math.round(quantile(absErr, 0.5) * 100) / 100, within30: Math.round((absErr.filter((e) => e <= 0.3).length / absErr.length) * 100) / 100 },
  };
  console.log(`${game}: n=${data.length} topK=${model.games[game].topK} band=${model.games[game].band} cv=${JSON.stringify(model.games[game].cv)}`);
}
await writeFile(join(here, "../public/model.json"), JSON.stringify(model));
