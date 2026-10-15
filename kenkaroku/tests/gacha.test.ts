import { describe, expect, it } from "vitest";
import { pull, resolveDuplicates, PITY } from "../src/core/gacha";
import { createRng } from "../src/core/rng";
import { bannerPool, CURRENT_BANNER } from "../src/data/banners";

const pool = bannerPool(CURRENT_BANNER);

describe("花結び（召喚）", () => {
  it("単発の排出率：UR3%・SSR15%・SR82%、URの半分がピックアップ", () => {
    const rng = createRng(2024);
    const N = 200_000;
    const count = { UR: 0, SSR: 0, SR: 0, pickup: 0 };
    let pity = 0;
    for (let i = 0; i < N; i++) {
      // 天井の影響を除くため pity は毎回0から
      const r = pull(rng, pool, 0, 1).results[0];
      count[r.rarity]++;
      if (r.pickup) count.pickup++;
      pity = 0;
    }
    expect(pity).toBe(0);
    expect(count.UR / N).toBeCloseTo(0.03, 2);
    expect(count.SSR / N).toBeCloseTo(0.15, 2);
    expect(count.SR / N).toBeCloseTo(0.82, 2);
    expect(count.pickup / count.UR).toBeGreaterThan(0.46);
    expect(count.pickup / count.UR).toBeLessThan(0.54);
  });

  it("十連はSSR以上を1体以上保証する", () => {
    const rng = createRng(1);
    for (let i = 0; i < 5000; i++) {
      const { results } = pull(rng, pool, 0, 10);
      expect(results).toHaveLength(10);
      expect(results.some((r) => r.rarity !== "SR")).toBe(true);
    }
  });

  it("80回目でピックアップURが確定（天井）", () => {
    const rng = createRng(5);
    const { results, pity } = pull(rng, pool, PITY - 1, 1);
    expect(results[0]).toMatchObject({ rarity: "UR", charId: CURRENT_BANNER.pickup, byPity: true });
    expect(pity).toBe(0);
  });

  it("URが出なければ天井カウントが進み、出たらリセット", () => {
    const rng = createRng(77);
    let pity = 0;
    let maxGap = 0;
    let gap = 0;
    for (let i = 0; i < 20_000; i++) {
      const r = pull(rng, pool, pity, 1);
      pity = r.pity;
      gap = r.results[0].rarity === "UR" ? 0 : gap + 1;
      maxGap = Math.max(maxGap, gap);
      expect(pity).toBe(gap);
    }
    expect(maxGap).toBeLessThan(PITY);
  });

  it("十連の途中でも天井が効く", () => {
    const rng = createRng(3);
    const { results } = pull(rng, pool, PITY - 3, 10);
    const firstUr = results.findIndex((r) => r.rarity === "UR");
    expect(firstUr).toBeGreaterThanOrEqual(0);
    expect(firstUr).toBeLessThanOrEqual(2);
  });

  it("被りは花片10に変換、同じ十連内の2体目以降も被り扱い", () => {
    const res = resolveDuplicates(new Set(["koyuki"]), [
      { charId: "koyuki", rarity: "SR", pickup: false, byPity: false, byGuarantee: false },
      { charId: "aoi", rarity: "SR", pickup: false, byPity: false, byGuarantee: false },
      { charId: "aoi", rarity: "SR", pickup: false, byPity: false, byGuarantee: false },
    ]);
    expect(res.map((r) => [r.isNew, r.shards])).toEqual([
      [false, 10],
      [true, 0],
      [false, 10],
    ]);
  });

  it("同じシードなら同じ結果", () => {
    const a = pull(createRng(99), pool, 0, 10);
    const b = pull(createRng(99), pool, 0, 10);
    expect(a).toEqual(b);
  });
});
