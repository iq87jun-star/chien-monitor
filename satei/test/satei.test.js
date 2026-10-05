import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseRoster, featureNames } from "../public/lib/features.js";
import { fitRidge, dot } from "../public/lib/model.js";
import { estimate } from "../public/lib/estimate.js";
import { prompt, SCHEMA } from "../src/worker.js";

test("タイトルからキャラごとの凸数と餅を読む(次のキャラ名の手前まで)", () => {
  assert.deepEqual(parseRoster("サンドローネ オデット マーヴィカ1凸+餅 ナヒーダ3凸", "genshin-impact"), {
    サンドローネ: { cons: 0, mochi: false },
    オデット: { cons: 0, mochi: false },
    マーヴィカ: { cons: 1, mochi: true },
    ナヒーダ: { cons: 3, mochi: false },
  });
  assert.deepEqual(parseRoster("召使完凸、ヌヴィ C2", "genshin-impact"), {
    アルレッキーノ: { cons: 6, mochi: false },
    ヌヴィレット: { cons: 2, mochi: false },
  });
  assert.deepEqual(parseRoster("黄泉両完凸 キャスE2 丹恒・騰荒", "houkaistarrail"), {
    黄泉: { cons: 6, mochi: true },
    キャストリス: { cons: 2, mochi: false },
    丹恒騰荒: { cons: 0, mochi: false },
  });
});

test("リッジ回帰は一次式を当てる", () => {
  const X = [], y = [];
  for (let i = 0; i < 50; i++) {
    const a = i % 7, b = i % 3;
    X.push([1, a, b]);
    y.push(2 + 0.5 * a - 0.25 * b);
  }
  const w = fitRidge(X, y, 1e-6);
  assert.ok(Math.abs(dot(w, [1, 4, 2]) - 3.5) < 1e-3);
});

test("査定額は上位 topK 人だけで出し、幅と買取の割合をかける", () => {
  const game = "genshin-impact";
  const features = featureNames(game);
  const weights = features.map((f) => (f === "bias" ? Math.log(100000) : f.startsWith("has:") ? 0.1 : 0));
  const model = { buyRate: 0.5, games: { [game]: { features, weights, topK: 2, band: [Math.log(0.8), Math.log(1.2)] } } };
  const r = estimate(model, game, [
    { name: "フリーナ", cons: 0, mochi: false },
    { name: "ナヒーダ", cons: 0, mochi: false },
    { name: "夜蘭", cons: 0, mochi: false },
    { name: "辞書にないキャラ", cons: 6, mochi: true },
  ]);
  assert.equal(r.keys.length, 2);
  // 相場 = 10万 × e^0.2(2人分)× 星5の数の重み 0 → 約12.2万。× 0.8〜1.2 × 0.5
  const market = 100000 * Math.exp(0.2);
  assert.equal(r.low, Math.floor((market * 0.8 * 0.5) / 1000) * 1000);
  assert.equal(r.high, Math.ceil((market * 1.2 * 0.5) / 1000) * 1000);
});

test("公開しているモデルはキャラ辞書と合っている", () => {
  const model = JSON.parse(readFileSync(new URL("../public/model.json", import.meta.url)));
  assert.equal(model.buyRate, 0.55);
  for (const [game, m] of Object.entries(model.games)) {
    assert.deepEqual(m.features, featureNames(game));
    assert.ok(m.band[0] < 0 && m.band[1] > 0);
  }
});

test("読み取りの指示にキャラ名の一覧が入る", () => {
  assert.match(prompt("houkaistarrail"), /キャストリス/);
  assert.match(prompt("genshin-impact"), /命ノ星座/);
});

test("読み取り結果の形は構造化出力で使えない制約(minimum など)を含まない", () => {
  assert.doesNotMatch(JSON.stringify(SCHEMA), /"(minimum|maximum|multipleOf|minLength|maxLength)"/);
});
