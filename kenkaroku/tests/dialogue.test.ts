import { describe, expect, it } from "vitest";
import { availableBanters, homeLines, teamLeader, timeOfDay } from "../src/core/dialogue";
import { CHARACTERS } from "../src/data/characters";
import { BANTERS, VOICES } from "../src/data/voices";
import { ENEMIES } from "../src/data/enemies";

describe("台詞データ", () => {
  it("全キャラに必須の台詞（編成・スキル・勝利・敗北・開花・ホーム）がある", () => {
    for (const c of CHARACTERS) {
      const v = VOICES[c.id];
      expect(v, c.id).toBeDefined();
      for (const k of ["formation", "skill", "victory", "defeat", "bloom"] as const) expect(v[k].length, `${c.id}.${k}`).toBeGreaterThan(0);
      expect(v.home.length).toBeGreaterThanOrEqual(1);
      expect(Object.keys(v.homeTime)).toHaveLength(3);
    }
  });

  it("掛け合い・縁は実在するキャラを指す", () => {
    const ids = new Set(CHARACTERS.map((c) => c.id));
    for (const b of BANTERS) {
      expect(ids.has(b.leader)).toBe(true);
      expect(ids.has(b.partner)).toBe(true);
      for (const l of b.lines) expect([b.leader, b.partner]).toContain(l.who);
    }
    for (const c of CHARACTERS) for (const r of c.relations) expect(ids.has(r.id), `${c.id}→${r.id}`).toBe(true);
  });

  it("キャラは14人、敵は全員に特徴文がある", () => {
    expect(CHARACTERS).toHaveLength(14);
    for (const e of ENEMIES) expect(e.desc.length).toBeGreaterThan(5);
  });
});

describe("ホームの会話", () => {
  it("時間帯の判定", () => {
    expect(timeOfDay(new Date(2026, 0, 1, 6))).toBe("morning");
    expect(timeOfDay(new Date(2026, 0, 1, 12))).toBe("day");
    expect(timeOfDay(new Date(2026, 0, 1, 22))).toBe("night");
    expect(timeOfDay(new Date(2026, 0, 1, 3))).toBe("night");
  });

  it("ホーム台詞は時間帯限定のものを含む", () => {
    expect(homeLines("hisame", "night")).toContain(VOICES.hisame.homeTime.night);
    expect(homeLines("hisame", "night")).not.toContain(VOICES.hisame.homeTime.morning);
  });

  it("掛け合いは相手を所持しているときだけ", () => {
    expect(availableBanters("hisame", ["hisame"])).toHaveLength(0);
    expect(availableBanters("hisame", ["hisame", "yae"]).map((b) => b.partner)).toEqual(["yae"]);
  });

  it("リーダーは編成の先頭", () => {
    expect(teamLeader([null, "rin", "yae", null, null])).toBe("rin");
    expect(teamLeader([null, null, null, null, null])).toBeNull();
  });
});
