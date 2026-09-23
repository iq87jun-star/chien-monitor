import { test } from "node:test";
import assert from "node:assert/strict";
import { buildCards, loadPrices, normalize, searchCards } from "../public/prices.js";
import { fakeFetch, priceData } from "./helpers.js";

const data = priceData();

test("ポケカ: セットと番号で1枚ずつ、円換算", () => {
  const cards = buildCards("pokeca", data["https://pokeca-kaigai.com/api/cards.json"]);
  const zard = cards.find((c) => c.key === "pokeca:SV2a-201");
  assert.equal(zard.label, "リザードンex");
  assert.equal(zard.sub, "ポケモンカード151 201");
  assert.equal(zard.jpy, 1800);
  assert.equal(cards.length, 3);
});

test("遊戯王: 英語名をキーにし、表示名の『』と引用符を外す", () => {
  const cards = buildCards("yugioh", data["https://pocketduel.tokyo/api/cards.json"]);
  const ash = cards.find((c) => c.key === "yugioh:Ash Blossom & Joyous Spring");
  assert.equal(ash.label, "灰流うらら");
  assert.equal(ash.jpy, 540);
  assert.ok(cards.some((c) => c.key === "yugioh:7"));
});

test("ワンピース: 番号と版ごと、同じ番号・版の再録は最安値にまとめる", () => {
  const cards = buildCards("onepiece", data["https://pokeca-kaigai.com/api/onepiece.json"]);
  assert.equal(cards.length, 2);
  const normal = cards.find((c) => c.key === "onepiece:OP05-119:normal");
  assert.equal(normal.jpy, 1200); // $8 × 150
  assert.equal(normal.sub, "通常版");
  assert.equal(cards.find((c) => c.key === "onepiece:OP05-119:parallel").sub, "パラレル");
});

test("未公開・形式違いのデータは空", () => {
  assert.deepEqual(buildCards("pokeca", { v: 1, available: false }), []);
  assert.deepEqual(buildCards("pokeca", { v: 2, available: true, cards: [] }), []);
});

test("取得に失敗したゲームがあっても他は読み込む", async () => {
  const d = priceData();
  delete d["https://pocketduel.tokyo/api/cards.json"];
  const { cards, sources, errors } = await loadPrices(fakeFetch(d).fetchImpl);
  assert.deepEqual(Object.keys(sources).sort(), ["onepiece", "pokeca"]);
  assert.match(errors.yugioh, /404/);
  assert.equal(cards.size, 5);
});

test("検索: ひらがな・全角・複数語、名前の一致を先に", async () => {
  const { cards } = await loadPrices(fakeFetch(priceData()).fetchImpl);
  assert.equal(normalize("ﾘｻﾞｰﾄﾞﾝ ＥＸ"), "リザードンex");
  const zard = searchCards(cards, "りざーどん");
  assert.deepEqual(
    zard.map((c) => c.key),
    ["pokeca:SV2a-201", "pokeca:SV2a-006"], // 価格の高い順
  );
  assert.deepEqual(
    searchCards(cards, "リザードン 006").map((c) => c.key),
    ["pokeca:SV2a-006"],
  );
  assert.equal(searchCards(cards, "はるうらら")[0].key, "yugioh:Ash Blossom & Joyous Spring");
  assert.equal(searchCards(cards, "op05-119 パラレル")[0].key, "onepiece:OP05-119:parallel");
  assert.deepEqual(searchCards(cards, "  "), []);
  assert.equal(searchCards(cards, "ex", { game: "yugioh" }).length, 0);
  assert.equal(searchCards(cards, "ex", { game: "pokeca", limit: 1 }).length, 1);
});
