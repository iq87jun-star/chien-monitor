import { describe, expect, it } from "vitest";
import {
  bloomCost,
  bloomStageName,
  fastIdleReward,
  idleReward,
  IDLE_CAP_HOURS,
  levelCap,
  levelUpCost,
  MAX_STAR,
} from "../src/core/economy";
import { characterStats } from "../src/core/stats";

describe("レベル・開花", () => {
  it("レベル上限は 40 + 20×(★−1)", () => {
    expect(levelCap(1)).toBe(40);
    expect(levelCap(2)).toBe(60);
    expect(levelCap(10)).toBe(220);
  });

  it("開花に必要な花片は 10×★、★10で打ち止め", () => {
    expect(bloomCost(1)).toBe(10);
    expect(bloomCost(5)).toBe(50);
    expect(bloomCost(9)).toBe(90);
    expect(bloomCost(MAX_STAR)).toBeNull();
  });

  it("★1→★10 の累計花片は450", () => {
    let total = 0;
    for (let s = 1; s < MAX_STAR; s++) total += bloomCost(s)!;
    expect(total).toBe(450);
  });

  it("花の段階名", () => {
    expect(bloomStageName(1)).toBe("蕾");
    expect(bloomStageName(10)).toBe("満開");
  });

  it("レベルアップ費用は単調増加", () => {
    for (let lv = 1; lv < 220; lv++) expect(levelUpCost(lv + 1)).toBeGreaterThan(levelUpCost(lv));
  });

  it("レベル・★でステータスが上がり、URはSRより強い", () => {
    const a = characterStats("atk", "SR", 1, 1);
    const b = characterStats("atk", "SR", 20, 1);
    const c = characterStats("atk", "SR", 20, 3);
    const d = characterStats("atk", "UR", 20, 3);
    expect(b.atk).toBeGreaterThan(a.atk);
    expect(c.atk).toBeGreaterThan(b.atk);
    expect(d.atk).toBeGreaterThan(c.atk);
  });
});

describe("放置報酬", () => {
  it("経過時間に比例し、12時間で頭打ち", () => {
    const h = 3_600_000;
    const one = idleReward(h, 0);
    const twelve = idleReward(12 * h, 0);
    const day = idleReward(24 * h, 0);
    expect(twelve.gold).toBe(one.gold * 12);
    expect(day).toEqual(twelve);
    expect(day.hours).toBe(IDLE_CAP_HOURS);
  });

  it("突破数が多いほど報酬が増える", () => {
    expect(idleReward(3_600_000, 10).gold).toBeGreaterThan(idleReward(3_600_000, 0).gold);
  });

  it("負の経過時間は0扱い", () => {
    expect(idleReward(-1000, 5)).toEqual({ hours: 0, gold: 0, gems: 0 });
  });

  it("高速放置は2時間分", () => {
    expect(fastIdleReward(3)).toEqual(idleReward(2 * 3_600_000, 3));
  });
});
