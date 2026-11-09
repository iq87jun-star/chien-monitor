import { test } from "node:test";
import assert from "node:assert/strict";
import { median, calibration, cutoffLine, reach, sellSignal, addPrice, cashRank } from "../src/learn.js";

test("calibration は実際÷予想の中央値を、件数が少ないうちは 1 に寄せ、0.7〜1.3 に収める", () => {
  assert.equal(calibration([], "Defender"), 1);
  const ten = Array.from({ length: 10 }, () => ({ pos: "Defender", proj: 50, actual: 40 }));   // 0.8 が 10 件 → (8 + 10) / 20 = 0.9
  assert.equal(+calibration(ten, "Defender").toFixed(3), 0.9);
  assert.equal(calibration(ten, "Forward"), 1);
  const many = Array.from({ length: 1000 }, () => ({ pos: "Forward", proj: 50, actual: 5 }));
  assert.equal(calibration(many, "Forward"), 0.7);
});

test("cutoffLine は直近 5 節の中央値、reach は記録が足りなければ判断しない", () => {
  assert.equal(median([3, 1, 2, 10]), 2.5);
  const l = cutoffLine([1, 2, 3, 4, 5, 6].map((i) => ({ rank: 50, score: 100 + i })));
  assert.deepEqual(l, { score: 104, rank: 50, n: 5 });
  assert.equal(reach(208, l), 2);
  assert.equal(reach(100, { score: 200, n: 1 }), null);
  assert.equal(reach(100, null), null);
});

test("sellSignal は値上がりの後に最高値から下がり始め、まだ利益がある時だけ出す", () => {
  const s = (...p) => p.map((v, i) => [i, v]);
  assert.match(sellSignal(s(10, 13, 11.5), 10), /最高値 \$13\.00 から 12% 下がり始めた/);
  assert.equal(sellSignal(s(10, 13, 12.5), 10), null);    // 4% しか下がっていない
  assert.equal(sellSignal(s(10, 11.5, 10.2), 10), null);  // 最高値が +15% で、+20% に届かない
  assert.equal(sellSignal(s(10, 13, 10.5), 10), null);    // 買値から +5% しか残らない
  assert.equal(sellSignal(s(10, 13, 11.5), null), null);
});

test("addPrice は 2 時間以内を上書きし、cashRank は現金の出る最後の順位", () => {
  assert.deepEqual(addPrice([[0, 1]], 3600e3, 2), [[3600e3, 2]]);
  assert.deepEqual(addPrice([[0, 1]], 3 * 3600e3, 2), [[0, 1], [3 * 3600e3, 2]]);
  assert.equal(cashRank([{ toRank: 1, usdAmount: 100 }, { toRank: 50, usdAmount: 25 }, { toRank: 100, usdAmount: null }]), 50);
  assert.equal(cashRank([{ toRank: 10, ethAmount: 0.01 }]), 10);
  assert.equal(cashRank([]), null);
});
