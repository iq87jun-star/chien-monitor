import { test } from "node:test";
import assert from "node:assert/strict";
import { emptyPaper, momentum, pickBuys, step, buy, summary } from "../src/paper.js";

test("momentum は出場した試合だけで、直近3試合÷直近10試合を出す(5試合未満は null)", () => {
  assert.equal(momentum([10, 10, 10, 0]), null);
  const m = momentum([60, 60, 60, 30, 30, 30, 0, 30]);   // 出場 7 試合: 平均 (180+120)/7、直近 60
  assert.equal(+m.ratio.toFixed(3), +(60 / (300 / 7)).toFixed(3));
  assert.equal(m.recentAvg, 60);
});

test("pickBuys は勢い・直近平均・価格・持っていない選手で絞り、勢いの強い順", () => {
  const s = (hi, lo) => [hi, hi, hi, lo, lo, lo, lo, lo, lo, lo];
  const cands = [
    { id: "a", price: 5, scores: s(60, 30) }, { id: "b", price: 5, scores: s(50, 40) },   // b は勢い不足
    { id: "c", price: 20, scores: s(60, 30) }, { id: "d", price: 5, scores: s(20, 10) },  // c は高すぎ、d は点が低い
    { id: "e", price: 5, scores: s(80, 30) }, { id: "f", price: 5, scores: s(60, 30) },   // f は持っている
  ];
  assert.deepEqual(pickBuys(cands, [{ id: "f" }]).map((c) => c.id), ["e", "a"]);
});

test("pickBuys は売ってから cooldownDays 日たっていない選手を買わない", () => {
  const s = [60, 60, 60, 30, 30, 30, 30, 30, 30, 30], now = Date.parse("2026-11-19T00:00:00Z");
  const cands = [{ id: "a", price: 5, scores: s }, { id: "b", price: 5, scores: s }];
  const closed = [{ id: "a", soldAt: "2026-11-15T00:00:00Z" }, { id: "b", soldAt: "2026-11-10T00:00:00Z" }];
  assert.deepEqual(pickBuys(cands, [], { closed, now }).map((c) => c.id), ["b"]);
});

test("step は利確・下がり始め・損切り・期限で仮に売り、手数料を引いて現金に戻す", () => {
  const at = "2026-11-01T00:00:00Z", now = Date.parse("2026-11-05T00:00:00Z");
  const paper = { ...emptyPaper(100), cash: 60, open: [
    { id: "take", buy: 10, peak: 10, at }, { id: "drop", buy: 10, peak: 14, at }, { id: "stop", buy: 10, peak: 10, at },
    { id: "hold", buy: 10, peak: 10, at }, { id: "old", buy: 10, peak: 10, at: "2026-10-01T00:00:00Z" }, { id: "nopx", buy: 10, at } ] };
  const r = step(paper, { take: 13, drop: 12.5, stop: 8, hold: 10.5, old: 10 }, now);
  assert.deepEqual(r.closed.map((c) => [c.id, c.why]), [["take", "利確"], ["drop", "下がり始め"], ["stop", "損切り"], ["old", "期限"]]);
  assert.deepEqual(r.open.map((p) => p.id), ["hold", "nopx"]);
  assert.equal(r.cash, +(60 + (13 + 12.5 + 8 + 10) * 0.95).toFixed(2));
});

test("buy は現金の範囲で買い、summary は手取り見込みで資産と勝ち負けを出す", () => {
  const now = Date.parse("2026-11-15T00:00:00Z");
  const { paper, bought } = buy(emptyPaper(10), [{ id: "x", price: 6, m: { ratio: 1.5 } }, { id: "y", price: 6, m: { ratio: 1.4 } }], now);
  assert.deepEqual(bought.map((b) => b.id), ["x"]);
  assert.equal(paper.cash, 4);
  const s = summary({ ...paper, closed: [{ pnl: 1 }, { pnl: -0.5 }] });
  assert.deepEqual(s, { total: +(4 + 6 * 0.95).toFixed(2), pct: +(((4 + 5.7) / 10 - 1) * 100).toFixed(1), wins: 1, losses: 1, realized: 0.5 });
});
