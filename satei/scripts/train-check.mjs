// チェック式査定(グラブル・ウマ娘・第五人格)の値付けモデルを、売れたアカウントの記録(gametrade-watch の D1)から学習し、
// public/check-model.json に書き出す。
//
//   GAMETRADE_INGEST_TOKEN=<合言葉> node satei/scripts/train-check.mjs
//   node satei/scripts/train-check.mjs --from <dir>   # <dir>/<ゲームトレードのゲーム名>.json から学習する
//
// モデル: log(売値) をリッジ回帰で当てる。特徴量は項目ごとの log(1+数)と、説明文によく出る語(キャラ名・衣装名など)が
// あるか(public/lib/check.js)。語は出品 25 件以上・全体の 6 割以下に出るものから、多い順に TERMS 個。
// 値段を上げる語の上位(pick)は、査定ページで「持っているもの」として選べるようにする。
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
const TERM_LAMBDA = 30; // 語は数が多いので強めに縮める
const TERMS = 300;
const PICK = 40;
// 「持っているもの」に出さない語(取引の決まり文句など)
const NOT_PICK = /ます|です|あり|など|また|購入|引き継|方法|連携|コメント|質問|価格|値下|即|可能|不可|お願|垢|アカウント|課金|ガチャ|画像|写真|参照|詳細|以上|多数|所持|未使用|済|コード|google|apple|ios|android|メール|取引|出品|引退|ご覧|ランク|宝晶石|ジュエル|サポ|衣装$|^ur|^ssr|^sr$|^lr|段|^限定$|^コラボ$|居館|エコー|手がかり|プラットフォーム|制限|キャラ$|サイド|^オー$|モバゲー|追記|注意|ウマ娘|その他|^スピ$|^エル$|周年|anniversary|引換券|結晶|誕生日|^正月$|アナザー|^完凸$|^賢者$|女神像|有償|^th$|タフネス|根性|^メイ$/i;
const BUY_RATE = 0.55; // 買取額 = 売れた相場 × この割合(原神・スタレと同じ)

const quantile = (a, q) => {
  const s = [...a].sort((x, y) => x - y);
  return s[Math.min(s.length - 1, Math.max(0, Math.round(q * (s.length - 1))))];
};
const r4 = (v) => Math.round(v * 1e4) / 1e4;

// 項目(log:*)の重みが 0 以上になるまで、負の項目を外して学ぶ
function fitMonotone(X, y, names, lambda) {
  const off = new Set();
  for (;;) {
    const Xm = X.map((x) => x.map((v, i) => (off.has(i) ? 0 : v)));
    const w = fitRidge(Xm, y, lambda).map((v, i) => (off.has(i) ? 0 : v));
    const neg = names.map((f, i) => (f.startsWith("log:") && w[i] < 0 ? i : -1)).filter((i) => i >= 0);
    if (!neg.length) return w;
    for (const i of neg) off.add(i);
  }
}

const model = { trainedAt: new Date().toISOString(), buyRate: BUY_RATE, games: {} };
for (const game of Object.keys(CHECK)) {
  const rows = (await loadSold(SOLD_GAME[game])).filter((r) => !/様/.test(r.name) && !NOT_ACCOUNT.test(r.name));
  const parsed = rows.map((r) => ({ ...listingValues(game, r), y: Math.log(r.price) }));
  const df = new Map();
  for (const p of parsed) for (const t of p.terms) df.set(t, (df.get(t) ?? 0) + 1);
  const terms = [...df].filter(([, n]) => n >= 25 && n <= 0.6 * parsed.length).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1)).slice(0, TERMS).map(([t]) => t);
  const names = checkFeatureNames(game, terms);
  const lambda = names.map((f) => (f.startsWith("term:") ? TERM_LAMBDA : LAMBDA));
  const data = parsed.map((p) => ({ x: checkFeatures(game, p.values, p.extra, terms, p.terms), y: p.y }));
  const resid = [];
  for (let f = 0; f < 5; f++) {
    const tr = data.filter((_, i) => i % 5 !== f);
    const w = fitMonotone(tr.map((d) => d.x), tr.map((d) => d.y), names, lambda);
    for (const d of data.filter((_, i) => i % 5 === f)) resid.push(d.y - dot(w, d.x));
  }
  const w = fitMonotone(data.map((d) => d.x), data.map((d) => d.y), names, lambda);
  // 値段を上げる語の上位(査定ページの「持っているもの」とスクショ読み取りの候補)
  const pick = terms
    .map((t, i) => [t, w[names.indexOf(`term:${t}`)]])
    .filter(([t, v]) => v > 0.02 && !NOT_PICK.test(t))
    .sort((a, b) => b[1] - a[1])
    .slice(0, PICK)
    .map(([t]) => t);
  const absErr = resid.map((r) => Math.abs(Math.exp(r) - 1));
  // 何も分からない時(切片だけ)との比較: 残差の分散がどれだけ減ったか
  const mean = data.reduce((s, d) => s + d.y, 0) / data.length;
  const r2 = 1 - resid.reduce((s, r) => s + r * r, 0) / data.reduce((s, d) => s + (d.y - mean) ** 2, 0);
  model.games[game] = {
    n: data.length,
    features: names,
    weights: w.map(r4),
    terms,
    pick,
    cap: quantile(rows.map((r) => r.price), 0.99),
    band: [quantile(resid, 0.25), quantile(resid, 0.75)].map(r4),
    cv: { r2: Math.round(r2 * 100) / 100, medianAbsErr: Math.round(quantile(absErr, 0.5) * 100) / 100, within30: Math.round((absErr.filter((e) => e <= 0.3).length / absErr.length) * 100) / 100 },
  };
  console.log(`${game}: n=${data.length} band=${model.games[game].band} cv=${JSON.stringify(model.games[game].cv)}`);
  console.log("  " + names.filter((f) => !f.startsWith("term:")).map((f) => `${f}=${w[names.indexOf(f)].toFixed(3)}`).join(" "));
  console.log("  pick: " + pick.join(" "));
}
await writeFile(join(here, "../public/check-model.json"), JSON.stringify(model));
