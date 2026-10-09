// 価格差リストの計算の単体テスト(通信なし)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  pickCandidates,
  searchKeyword,
  isSameCard,
  domesticQuote,
  profit,
  buildList,
  renderReport,
  discordMessages,
} from "../src/core.mjs";

const card = {
  id: "M4-120",
  name: "メガゲッコウガex",
  set: "ニンジャスピナー",
  setId: "M4",
  localId: "120",
  rarity: "Special illustration rare",
  eur: 495,
  avg7: 480,
};
const opts = { minListingJpy: 500, domesticShipping: 300 };
const settings = {
  eurJpy: 177,
  sellFeeRate: 0.15,
  fxHaircut: 0.03,
  intlShipping: 1500,
  minProfitJpy: 1000,
  minProfitRate: 10,
};
const item = (itemName, itemPrice, extra = {}) => ({
  itemName,
  itemPrice,
  itemUrl: `https://item.rakuten.co.jp/shop/${itemPrice}`,
  shopName: "テスト店",
  postageFlag: 0,
  ...extra,
});

test("候補は円換算の下限以上を高い順に上限まで", () => {
  const cards = [
    { id: "a", eur: 10 },
    { id: "b", eur: 100 },
    { id: "c", eur: 50 },
    { id: "d", eur: null },
  ];
  assert.deepEqual(
    pickCandidates(cards, 177, { minJpy: 3000, max: 2 }).map((c) => c.id),
    ["b", "c"],
  );
});

test("検索語は型番の分子を3桁で入れる", () => {
  assert.equal(searchKeyword({ name: "ピカチュウ", localId: "7" }), "ポケモンカード ピカチュウ 007");
});

test("カード名と型番が両方そろった単品出品だけを同じカードとみなす", () => {
  assert.equal(isSameCard(card, "メガゲッコウガex SAR 120/080 ニンジャスピナー"), true);
  assert.equal(isSameCard(card, "ポケカ　メガゲッコウガＥＸ　１２０／０８０"), true);
  // 型番違い(同名の別レアリティ)
  assert.equal(isSameCard(card, "メガゲッコウガex RR 022/080"), false);
  // 型番なし
  assert.equal(isSameCard(card, "メガゲッコウガex SAR 美品"), false);
  // 鑑定品・海外版・まとめ売り
  assert.equal(isSameCard(card, "【PSA10】メガゲッコウガex SAR 120/080"), false);
  assert.equal(isSameCard(card, "メガゲッコウガex 120/080 英語版"), false);
  assert.equal(isSameCard(card, "メガゲッコウガex 120/080 他 まとめ"), false);
});

test("国内最安は送料別の出品に送料を足して比べる", () => {
  const q = domesticQuote(
    card,
    [
      item("メガゲッコウガex SAR 120/080", 30000, { postageFlag: 1 }),
      item("メガゲッコウガex SAR 120/080", 30200),
      item("メガゲッコウガex RR 022/080", 800),
      item("ストレージ メガゲッコウガex 120/080", 300),
    ],
    opts,
  );
  assert.equal(q.count, 2);
  assert.equal(q.cheapest.total, 30200);
  assert.equal(q.cheapest.price, 30200);
});

test("一致する出品が無ければ null", () => {
  assert.equal(domesticQuote(card, [item("メガゲッコウガex RR 022/080", 800)], opts), null);
  assert.equal(domesticQuote(card, undefined, opts), null);
});

test("手残り = 売値×(1−手数料−為替) − 国際送料 − 仕入れ値", () => {
  // 100,000 × 0.82 − 1,500 = 80,500 → 80,500 − 60,000 = 20,500(仕入れ比 34.2%)
  assert.deepEqual(profit(100000, 60000, settings), { net: 80500, yen: 20500, rate: 34.2 });
});

test("リストは条件を満たすものを手残りの多い順に、国内が高いものは別に分ける", () => {
  const cheap = { ...card, id: "M4-120", eur: 495 }; // 海外 87,615円
  const pricey = { ...card, id: "M4-114", localId: "114", eur: 100 }; // 海外 17,700円
  const thin = { ...card, id: "M4-098", localId: "098", eur: 60 }; // 海外 10,620円
  const rows = [
    { card: cheap, quote: { count: 3, cheapest: { total: 50000, url: "u1", shop: "A", title: "t" } } },
    { card: pricey, quote: { count: 1, cheapest: { total: 25000, url: "u2", shop: "B", title: "t" } } },
    { card: thin, quote: { count: 1, cheapest: { total: 7000, url: "u3", shop: "C", title: "t" } } },
    { card: { ...card, id: "none" }, quote: null },
  ];
  const r = buildList(rows, settings);
  assert.equal(r.matched, 3);
  // cheap: 87,615×0.82−1,500−50,000 = 20,344 / thin: 10,620×0.82−1,500−7,000 = 208(条件外)
  assert.deepEqual(r.exportList.map((s) => s.id), ["M4-120"]);
  assert.equal(r.exportList[0].profitJpy, 20344);
  assert.deepEqual(r.domesticHigh.map((s) => s.id), ["M4-114"]);
  assert.equal(r.domesticHigh[0].gapRate, 41.2);
});

test("レポートと Discord の文に結果が入る", () => {
  const rows = [
    { card, quote: { count: 1, cheapest: { total: 50000, url: "https://x/1", shop: "A", title: "t" } } },
  ];
  const r = buildList(rows, settings);
  const meta = {
    ...settings,
    domesticShipping: 300,
    generatedAt: "2026-10-09 07:13",
    overseasFetchedAt: "2026-10-09",
    searched: 1,
    maxRows: 30,
  };
  const md = renderReport(r, meta);
  assert.match(md, /メガゲッコウガex 120/);
  assert.match(md, /¥87,615/);
  const msgs = discordMessages(r, meta);
  assert.equal(msgs.length, 1);
  assert.match(msgs[0], /手残り ¥20,344/);
  assert.ok(msgs.every((m) => m.length <= 2000));
});
