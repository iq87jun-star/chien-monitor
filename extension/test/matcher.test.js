// matcher.js の単体テスト。fixtures/cards.json は toreca の実データのスナップショット
// (2026-09-22 取得・export-ext.mjs と同じ v1 形式)
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import "../src/matcher.js";

const M = globalThis.PokecaMatcher;
const data = JSON.parse(fs.readFileSync(new URL("./fixtures/cards.json", import.meta.url)));
const index = M.buildIndex(data);

const ids = (hit) => hit.cards.map((c) => `${c.setId}-${c.localId}`);

test("型番つきタイトルは1枚に特定できる", () => {
  const hits = M.match(index, "【美品】メガゲッコウガex SAR 120/080 ニンジャスピナー ポケモンカード");
  assert.equal(hits.length, 1);
  assert.equal(hits[0].exact, true);
  assert.deepEqual(ids(hits[0]), ["M4-120"]);
  assert.equal(M.toJpy(index, hits[0].cards[0].eur), Math.round(495 * data.eurJpy));
});

test("全角英数・ひらがな・空白の揺れを吸収する", () => {
  const hits = M.match(index, "ぽけか　メガリザードンＹｅｘ　７６６／７４２");
  assert.deepEqual(ids(hits[0]), ["MC-766"]);
});

test("型番がなければ同名カードを高い順に全候補で返す", () => {
  const hits = M.match(index, "メガゲッコウガex ポケカ");
  assert.equal(hits[0].exact, false);
  assert.deepEqual(ids(hits[0]), ["M4-120", "M4-114", "M4-098", "M4-022"]);
});

test("セット略号・セット名で絞り込む", () => {
  assert.deepEqual(ids(M.match(index, "ゼルネアス M1S ポケカ")[0]), ["M1S-046"]);
  assert.deepEqual(ids(M.match(index, "ゼルネアス メガシンフォニア")[0]), ["M1S-046"]);
});

test("長い名前を優先し、含まれる短い名前は別カード扱いしない", () => {
  const hits = M.match(index, "メガゲッコウガex 114/080 ポケカ");
  assert.equal(hits.length, 1);
  assert.equal(hits[0].name, "メガゲッコウガex");
});

test("ポケカ以外の出品(同名グッズ)には反応しない", () => {
  assert.equal(M.match(index, "イーブイ ぬいぐるみ ポケモンセンター"), null);
  assert.equal(M.match(index, "ワンピースカード ルフィ SEC"), null);
});

test("まとめ売り(4種以上の名前)は表示しない", () => {
  assert.equal(M.match(index, "ポケカ まとめ売り イーブイ ゼルネアス シシコ デオキシス"), null);
});

test("短すぎるカード名(2文字)は照合しない", () => {
  assert.equal(M.match(index, "ポケカ グリーンの戦略"), null);
});

test("カード番号の抽出", () => {
  assert.deepEqual([...M.extractNumbers("081/080 SR")], ["081"]);
  assert.deepEqual([...M.extractNumbers("プロモ 100/M-P")], ["100"]);
  assert.deepEqual([...M.extractNumbers("No.5")], ["005"]);
  assert.equal(M.extractNumbers("2026年 新品").size, 0);
});

test("データ形式が違う・欠如時はインデックスを作らない", () => {
  assert.equal(M.buildIndex(null), null);
  assert.equal(M.buildIndex({ v: 1, available: false }), null);
  assert.equal(M.buildIndex({ ...data, v: 99 }), null);
  assert.equal(M.match(null, "メガゲッコウガex"), null);
});

test("7日平均比", () => {
  assert.equal(M.change7d({ eur: 110, avg7: 100 }), 10);
  assert.equal(M.change7d({ eur: 1, avg7: null }), null);
});
