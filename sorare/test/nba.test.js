import { test } from "node:test";
import assert from "node:assert/strict";
import { nbaProject, bestNbaLineup } from "../src/model.js";

test("nbaProject は試合数が多いほど上振れを足し、試合が無い・欠場は 0、出場未定は 0.7 倍", () => {
  const p = { club: "A", l15: 40, scores: [30, 50, 30, 50], stars: 3 };   // 平均 40・標準偏差 10
  assert.equal(nbaProject(p, { A: 1 }).proj, 40);
  assert.equal(nbaProject(p, { A: 2 }).proj, 40 + 10 * 0.56);
  assert.ok(nbaProject(p, { A: 4 }).proj > nbaProject(p, { A: 3 }).proj);
  assert.equal(nbaProject(p, {}).proj, 0);
  assert.equal(nbaProject({ ...p, injury: "OUT" }, { A: 3 }).proj, 0);
  assert.equal(nbaProject({ ...p, injury: "GTD" }, { A: 1 }).proj, 28);
});

const P = (id, proj, stars, price = 1) => ({ id, proj, stars, price });

test("bestNbaLineup は星の合計の上限と予算を守って予想の合計を最大にする", () => {
  const c = [P("goat", 70, 5), P("star", 60, 4), P("imp1", 45, 3), P("imp2", 44, 3), P("ros1", 35, 2), P("ros2", 34, 2), P("dnp", 20, 1), P("rich", 50, 2, 100)];
  const r = bestNbaLineup(c, { starCap: 11, budget: 10 });
  assert.equal(r.lineup.length, 5);
  assert.ok(r.stars <= 11);
  assert.ok(!r.lineup.some((x) => x.id === "rich"));   // 予算超え
  // 星 11 以内の最良: goat(5)+ros1(2)+ros2(2)+dnp(1)=10 に 1 星の枠が無い → 総当たりで確かめる
  let bestPts = 0;
  const ok = c.filter((x) => x.price <= 10);
  const rec = (i, pick) => {
    if (pick.length === 5) { const s = pick.reduce((a, x) => a + x.stars, 0); if (s <= 11) bestPts = Math.max(bestPts, pick.reduce((a, x) => a + x.proj, 0)); return; }
    for (let j = i; j < ok.length; j++) rec(j + 1, [...pick, ok[j]]);
  };
  rec(0, []);
  assert.equal(r.pts, bestPts);
  assert.equal(r.captain, null);
  assert.equal(bestNbaLineup(c.slice(0, 4), { starCap: 16 }), null);   // 5 枚そろわない
});
