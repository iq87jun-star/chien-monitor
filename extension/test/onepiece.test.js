// ワンピースカード(toreca/pipeline/export-onepiece.mjs の出力)での照合テスト。
// fixtures/onepiece.json は 2026-09-23 取得の実データのスナップショット(optcgapi・TCGplayer USD)
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import "../src/matcher.js";

const M = globalThis.PokecaMatcher;
const read = (f) => JSON.parse(fs.readFileSync(new URL(`./fixtures/${f}`, import.meta.url)));
const data = read("onepiece.json");
const onepiece = M.buildIndex(data);
const pokeca = M.buildIndex(read("cards.json"));
const yugioh = M.buildIndex(read("yugioh.json"));

const price = (code, variant) =>
  data.cards.filter(([, no, , , , , , v]) => no === code && v === variant).map((c) => c[3]);

test("ワンピースはUSD建て・TCGplayer・ランキングサイトなし", () => {
  assert.equal(onepiece.game, "onepiece");
  assert.equal(onepiece.currency, "USD");
  assert.equal(onepiece.source, "TCGplayer");
  assert.equal(onepiece.siteUrl, null);
  assert.equal(M.toJpy(onepiece, 10), Math.round(10 * data.rateJpy));
});

test("カード番号で照合し、版の語が無ければ通常版", () => {
  const hits = M.match(onepiece, "ワンピースカード OP05-119 モンキー・D・ルフィ SEC");
  assert.equal(hits.length, 1);
  assert.match(hits[0].name, /^OP05-119 Monkey\.D\.Luffy/);
  assert.ok(hits[0].cards.every((c) => c.variant === "normal"));
});

test("パラレル・コミパラ・SP・金SPを見分ける", () => {
  const variantOf = (title) => M.match(onepiece, title)[0].cards.map((c) => c.variant);
  assert.ok(variantOf("OP05-119 ルフィ パラレル").every((v) => v === "parallel"));
  assert.ok(variantOf("OP05-119 ルフィ コミパラ").every((v) => v === "manga"));
  assert.deepEqual(variantOf("OP05-119 ルフィ SP"), ["sp"]);
  assert.deepEqual(variantOf("OP05-119 ルフィ 金SP"), ["sp-gold"]);
  const gold = M.match(onepiece, "OP05-119 ルフィ 金SP")[0];
  assert.equal(gold.exact, true);
  assert.equal(gold.cards[0].price, price("OP05-119", "sp-gold")[0]);
});

test("全角・小文字のカード番号も照合する", () => {
  assert.ok(M.match(onepiece, "ワンピカ　ｏｐ０５－１１９　ルフィ"));
  assert.ok(M.match(onepiece, "ワンピースカード st01-012 ルフィ パラレル"));
});

test("カード番号が無い出品・他ゲームの出品には反応しない", () => {
  assert.equal(M.match(onepiece, "ワンピースカード ルフィ SEC"), null);
  assert.equal(M.match(onepiece, "ポケカ ピカチュウ 025/165"), null);
  assert.equal(M.match(onepiece, "遊戯王 灰流うらら QCCP-JP001"), null);
  // ワンピースの出品にポケカ・遊戯王の相場を出さない
  assert.equal(M.match(pokeca, "ワンピースカード OP05-119 ルフィ"), null);
  assert.equal(M.match(yugioh, "ワンピースカード OP05-119 ルフィ"), null);
});

test("未開封BOX・まとめ売りには表示しない", () => {
  assert.equal(M.match(onepiece, "ワンピースカード OP05 新時代の主役 BOX 未開封"), null);
  assert.equal(M.match(onepiece, "ワンピースカード まとめ売り OP05-119 OP01-120"), null);
});
