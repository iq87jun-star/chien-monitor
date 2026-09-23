// 遊戯王データ(duel/pipeline/export-ext.mjs の出力)での照合テスト。
// fixtures/yugioh.json は 2026-09-23 取得の実データのスナップショット(€0.30以上・約3,000枚)
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import "../src/matcher.js";

const M = globalThis.PokecaMatcher;
const read = (f) => JSON.parse(fs.readFileSync(new URL(`./fixtures/${f}`, import.meta.url)));
const yugioh = M.buildIndex(read("yugioh.json"));
const pokeca = M.buildIndex(read("cards.json"));

test("遊戯王データはゲーム固有の表示情報を持つ", () => {
  assert.equal(yugioh.game, "yugioh");
  assert.equal(yugioh.siteUrl, "https://pocketduel.tokyo/");
  assert.match(yugioh.disclaimer, /最も安い版/);
  // ポケカのデータ(初版形式)は既定値で補われる
  assert.equal(pokeca.game, "pokeca");
  assert.equal(pokeca.label, "日本語版");
});

test("日本語名で照合し、英語名を補足に持つ", () => {
  const hits = M.match(yugioh, "遊戯王 灰流うらら 20th シークレット");
  assert.equal(hits.length, 1);
  assert.equal(hits[0].name, "灰流うらら");
  assert.equal(hits[0].exact, true);
  assert.equal(hits[0].cards[0].note, "Ash Blossom & Joyous Spring");
});

test("表示名は読み仮名ではなく漢字の正式名", () => {
  const hits = M.match(yugioh, "遊戯王 万物創世龍 10000シークレット");
  assert.equal(hits[0].name, "万物創世龍");
  // 読み仮名(カタカナ表記)でも同じカードに当たる
  assert.equal(M.match(yugioh, "遊戯王 テンサウザンド・ドラゴン")[0].name, "万物創世龍");
});

test("遊戯王の語がなくてもカード番号(QCCP-JP001形式)で遊戯王と判定する", () => {
  const hits = M.match(yugioh, "QCCP-JP001 真エクゾディア");
  assert.equal(hits?.[0].name, "真エクゾディア");
});

test("ゲームが違う出品には反応しない", () => {
  // 遊戯王の語も番号もないタイトルは遊戯王として扱わない
  assert.equal(M.match(yugioh, "真エクゾディア フィギュア"), null);
  // ポケカの型番(025/165)は遊戯王の判定に使わない
  assert.equal(M.match(yugioh, "ポケカ ピカチュウ 025/165"), null);
  // 遊戯王の出品にポケカの相場を出さない
  assert.equal(M.match(pokeca, "遊戯王 灰流うらら 20th シークレット"), null);
});

test("まとめ売り・ストラクチャーデッキには表示しない", () => {
  assert.equal(M.match(yugioh, "遊戯王 まとめ売り 灰流うらら 増殖するG"), null);
  assert.equal(M.match(yugioh, "遊戯王 ストラクチャーデッキ 灰流うらら"), null);
});

test("漢字名と読み仮名が両方あっても1枚として扱う", () => {
  const hits = M.match(yugioh, "遊戯王 灰流うらら(はるうらら)");
  assert.equal(hits.length, 1);
});
