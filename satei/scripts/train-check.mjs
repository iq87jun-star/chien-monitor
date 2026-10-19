// チェック式査定(グラブル・ウマ娘・第五人格)の値付けモデルを、売れたアカウントの記録(gametrade-watch の D1)から学習し、
// public/check-model.json に書き出す。
//
//   GAMETRADE_INGEST_TOKEN=<合言葉> node satei/scripts/train-check.mjs
//   node satei/scripts/train-check.mjs --from <dir>   # <dir>/<ゲームトレードのゲーム名>.json から学習する
//
// モデル: log(売値) をリッジ回帰で当てる。特徴量は項目ごとの log(1+数)(public/lib/check.js)。
// 項目の重みが負になったら、その項目を外して学習し直す(数が多いほど安くなる査定にしない)。
// 項目の数は、出品の項目欄とタイトルから読む(listingValues)。特典コードなどアカウント以外の出品は除く。
// 査定額の幅は、交差検証の誤差(log の残差)の分位点から決める。

import { writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { CHECK, SOLD_GAME, NOT_ACCOUNT, listingValues, checkFeatures, checkFeatureNames } from "../public/lib/check.js";
import { fitRidge, dot } from "../public/lib/model.js";
import { loadSold } from "./data.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const LAMBDA = 3;
const BUY_RATE = 0.55; // 買取額 = 売れた相場 × この割合(原神・スタレと同じ)

const quantile = (a, q) => {
  const s = [...a].sort((x, y) => x - y);
  return s[Math.min(s.length - 1, Math.max(0, Math.round(q * (s.length - 1))))];
};
const r4 = (v) => Math.round(v * 1e4) / 1e4;

// 項目(log:*)の重みが 0 以上になるまで、負の項目を外して学ぶ
function fitMonotone(X, y, names) {
  const off = new Set();
  for (;;) {
    const Xm = X.map((x) => x.map((v, i) => (off.has(i) ? 0 : v)));
    const w = fitRidge(Xm, y, LAMBDA).map((v, i) => (off.has(i) ? 0 : v));
    const neg = names.map((f, i) => (f.startsWith("log:") && w[i] < 0 ? i : -1)).filter((i) => i >= 0);
    if (!neg.length) return w;
    for (const i of neg) off.add(i);
  }
}

const model = { trainedAt: new Date().toISOString(), buyRate: BUY_RATE, games: {} };
for (const game of Object.keys(CHECK)) {
  const rows = (await loadSold(SOLD_GAME[game])).filter((r) => !/様/.test(r.name) && !NOT_ACCOUNT.test(r.name));
  const data = rows.map((r) => {
    const { values, extra } = listingValues(game, r);
    return { x: checkFeatures(game, values, extra), y: Math.log(r.price) };
  });
  const resid = [];
  for (let f = 0; f < 5; f++) {
    const tr = data.filter((_, i) => i % 5 !== f);
    const w = fitMonotone(tr.map((d) => d.x), tr.map((d) => d.y), checkFeatureNames(game));
    for (const d of data.filter((_, i) => i % 5 === f)) resid.push(d.y - dot(w, d.x));
  }
  const w = fitMonotone(data.map((d) => d.x), data.map((d) => d.y), checkFeatureNames(game));
  const absErr = resid.map((r) => Math.abs(Math.exp(r) - 1));
  // 何も分からない時(切片だけ)との比較: 残差の分散がどれだけ減ったか
  const mean = data.reduce((s, d) => s + d.y, 0) / data.length;
  const r2 = 1 - resid.reduce((s, r) => s + r * r, 0) / data.reduce((s, d) => s + (d.y - mean) ** 2, 0);
  model.games[game] = {
    n: data.length,
    features: checkFeatureNames(game),
    weights: w.map(r4),
    cap: quantile(rows.map((r) => r.price), 0.99),
    band: [quantile(resid, 0.25), quantile(resid, 0.75)].map(r4),
    cv: { r2: Math.round(r2 * 100) / 100, medianAbsErr: Math.round(quantile(absErr, 0.5) * 100) / 100, within30: Math.round((absErr.filter((e) => e <= 0.3).length / absErr.length) * 100) / 100 },
  };
  console.log(`${game}: n=${data.length} band=${model.games[game].band} cv=${JSON.stringify(model.games[game].cv)}`);
  console.log("  " + checkFeatureNames(game).map((f, i) => `${f}=${w[i].toFixed(3)}`).join(" "));
}
await writeFile(join(here, "../public/check-model.json"), JSON.stringify(model));
