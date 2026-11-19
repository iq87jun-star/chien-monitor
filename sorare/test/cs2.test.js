import { test } from "node:test";
import assert from "node:assert/strict";
import { joinMarket, sellRef, pickItems } from "../src/cs2.js";

const h = (name, med7, vol7, med30, med90) => ({ market_hash_name: name, last_7_days: { median: med7, volume: vol7 }, last_30_days: { median: med30 }, last_90_days: { median: med90 } });
const it = (name, min, qty = 5) => ({ market_hash_name: name, min_price: min, quantity: qty, item_page: `https://skinport.com/item/${name}` });

test("joinMarket は出品のある品だけを相場と合わせ、sellRef は最安出品と 7 日の中央値の安い方", () => {
  const m = joinMarket([it("a", 5), it("b", 5, 0), it("c", 5)], [h("a", 4, 20, 4, 4), h("b", 4, 20, 4, 4)]);
  assert.deepEqual(m.map((c) => c.id), ["a"]);
  assert.equal(sellRef(m[0]), 4);
  assert.equal(sellRef({ ask: 3, med7: 4 }), 3);
});

test("pickItems は取引量・価格・上昇・急騰でない・持っていない・売って 7 日以内でない品を、上昇の強い順に選ぶ", () => {
  const now = Date.parse("2026-11-19T00:00:00Z");
  const market = joinMarket(
    ["up", "big", "few", "pricey", "spike", "longdown", "held", "sold", "flat"].map((n) => it(n, n === "pricey" ? 30 : n === "spike" ? 6 : n === "big" ? 5.5 : 5)),
    [h("up", 5, 30, 4.5, 4), h("big", 6, 30, 4, 4), h("few", 5, 3, 4, 4), h("pricey", 30, 30, 20, 20), h("spike", 5, 30, 4, 4),
     h("longdown", 5, 30, 4.5, 6), h("held", 5, 30, 4, 4), h("sold", 5, 30, 4, 4), h("flat", 5, 30, 5, 5)]);
  const picks = pickItems(market, [{ id: "held" }], { closed: [{ id: "sold", soldAt: "2026-11-17T00:00:00Z" }], now, slots: 5 });
  assert.deepEqual(picks.map((c) => c.id), ["big", "up"]);
  assert.equal(picks[0].price, 5.5);
});
