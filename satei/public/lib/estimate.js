// 査定額を出す(ブラウザと Node の両方で使う)。model は public/model.json の中身。
import { featurize, featureNames } from "./features.js";
import { dot } from "./model.js";

// 1キャラ分の寄与(所持・凸数・餅の重みの合計)
function contribution(m, name, { cons, mochi }) {
  const i = (f) => m.features.indexOf(f);
  const w = (f) => (i(f) >= 0 ? m.weights[i(f)] : 0);
  return w(`has:${name}`) + w(`cons:${name}`) * (cons / 6) + (mochi ? w(`mochi:${name}`) : 0);
}

const roundDown = (yen) => Math.max(1000, Math.floor(yen / 1000) * 1000);
const roundUp = (yen) => Math.max(1000, Math.ceil(yen / 1000) * 1000);

// roster: [{ name, cons, mochi }](星5キャラ。辞書にない名前は値付けに使わない)
// 返り値: { low, high }(買取額の幅・円)と、値付けに効いたキャラ
export function estimate(model, game, roster) {
  const m = model.games[game];
  if (!m || featureNames(game).join() !== m.features.join()) throw new Error("モデルとキャラ辞書が合っていません");
  // 出品タイトルと同じく、値段に効く上位 topK 人だけを数える
  const ranked = roster
    .filter((c) => m.features.includes(`has:${c.name}`))
    .map((c) => ({ ...c, value: contribution(m, c.name, c) }))
    .sort((a, b) => b.value - a.value);
  const picked = ranked.slice(0, m.topK).filter((c) => c.value > 0);
  const x = featurize(game, {
    roster: Object.fromEntries(picked.map((c) => [c.name, { cons: c.cons, mochi: c.mochi }])),
    star5: roster.length,
  });
  const market = Math.exp(dot(m.weights, x)) * (m.adjust ?? 1);
  return {
    low: roundDown(market * Math.exp(m.band[0]) * model.buyRate),
    high: roundUp(market * Math.exp(m.band[1]) * model.buyRate),
    keys: picked.map((c) => c.name),
  };
}
