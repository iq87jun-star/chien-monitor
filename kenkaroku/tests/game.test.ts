import { describe, expect, it } from "vitest";
import * as G from "../src/core/game";
import { CURRENT_BANNER } from "../src/data/banners";
import { BEGINNER_MISSIONS } from "../src/data/missions";
import { STAGES } from "../src/data/stages";
import { migrate } from "../src/state/migrate";
import { MemorySaveRepository } from "../src/state/saveRepository";

const NOW = new Date(2026, 9, 15, 12, 0, 0).getTime();
const H = 3_600_000;

function ok<T>(o: G.Outcome<T>) {
  if (!o.ok) throw new Error(o.error);
  return o;
}

describe("ゲーム操作", () => {
  it("新規データは初期剣華5人・花玉3000", () => {
    const s = G.newSave(NOW);
    expect(Object.keys(s.roster)).toHaveLength(5);
    expect(s.gems).toBe(3000);
    expect(s.version).toBe(G.SAVE_VERSION);
  });

  it("レベル上げは両を消費し、上限で止まる", () => {
    let s = { ...G.newSave(NOW), gold: 10_000_000 };
    s = ok(G.levelUp(s, "koyuki", 100)).save;
    expect(s.roster.koyuki.level).toBe(40);
    expect(G.levelUp(s, "koyuki").ok).toBe(false);
  });

  it("開花で★と上限が上がり花片を消費", () => {
    let s = G.newSave(NOW);
    s.roster.koyuki.shards = 25;
    s = ok(G.bloom(s, "koyuki")).save;
    expect(s.roster.koyuki).toMatchObject({ star: 2, shards: 15 });
    expect(G.bloom(s, "koyuki").ok).toBe(false); // 20必要
    expect(s.counters.blooms).toBe(1);
  });

  it("花結びは花玉を消費し、新規は所持に・被りは花片に", () => {
    const s = G.newSave(NOW);
    const r = ok(G.gachaPull(s, CURRENT_BANNER, 10, 42));
    expect(r.save.gems).toBe(3000 - 1500);
    expect(r.save.counters.pulls).toBe(10);
    for (const p of r.results) expect(r.save.roster[p.charId]).toBeDefined();
    const shardTotal = Object.values(r.save.roster).reduce((a, o) => a + o.shards, 0);
    expect(shardTotal).toBe(r.results.filter((x) => !x.isNew).length * 10);
  });

  it("花玉不足では引けない", () => {
    expect(G.gachaPull({ ...G.newSave(NOW), gems: 100 }, CURRENT_BANNER, 1, 1).ok).toBe(false);
  });

  it("放置報酬は12時間で頭打ち、受け取りで時計がリセット", () => {
    const s = G.newSave(NOW);
    const r = ok(G.claimIdle(s, NOW + 30 * H));
    expect(r.reward.hours).toBe(12);
    expect(r.save.idleSince).toBe(NOW + 30 * H);
  });

  it("高速放置は1日2回まで、日付が変わると戻る", () => {
    let s = G.newSave(NOW);
    s = ok(G.useFastIdle(s, NOW)).save;
    s = ok(G.useFastIdle(s, NOW + 1000)).save;
    expect(G.useFastIdle(s, NOW + 2000).ok).toBe(false);
    expect(G.fastIdleLeft(s, NOW + 24 * H)).toBe(2);
    expect(G.useFastIdle(s, NOW + 24 * H).ok).toBe(true);
  });

  it("ステージは順番に解放、初回だけ花玉", () => {
    const s = G.newSave(NOW);
    expect(G.fightStage(s, 1, 1).ok).toBe(false);
    let won: G.SaveData | null = null;
    for (let seed = 0; seed < 10 && !won; seed++) {
      const r = ok(G.fightStage(s, 0, seed));
      if (r.result.win) {
        expect(r.rewards).toMatchObject({ firstClear: true, gems: STAGES[0].firstGems });
        won = r.save;
      }
    }
    expect(won!.cleared).toBe(1);
    for (let seed = 0; seed < 10; seed++) {
      const again = ok(G.fightStage(won!, 0, seed));
      if (again.result.win) {
        expect(again.rewards).toMatchObject({ firstClear: false, gems: 0 });
        break;
      }
    }
  });

  it("開花任務：解放条件・属性一致・1日3回（勝利時のみ消費）", () => {
    let s = { ...G.newSave(NOW), cleared: 30 };
    for (const id of Object.keys(s.roster)) s.roster[id] = { ...s.roster[id], level: 40 };
    expect(G.fightTrial({ ...s, cleared: 0 }, "water", 1, "koyuki", 1, NOW).ok).toBe(false);
    expect(G.fightTrial(s, "water", 1, "aoi", 1, NOW).ok).toBe(false);
    let wins = 0;
    for (let seed = 0; seed < 30 && wins < 3; seed++) {
      const r = ok(G.fightTrial(s, "water", 1, "koyuki", seed, NOW));
      if (r.result.win) {
        wins++;
        s = r.save;
      }
    }
    expect(wins).toBe(3);
    expect(s.roster.koyuki.shards).toBe(15);
    expect(G.fightTrial(s, "water", 1, "koyuki", 99, NOW).ok).toBe(false);
  });

  it("任務は達成後に1回だけ受け取れる", () => {
    let s = G.newSave(NOW);
    const m = BEGINNER_MISSIONS.find((x) => x.id === "b01")!;
    expect(G.claimMission(s, m.id).ok).toBe(false);
    s = G.setTeamSlot(s, 3, "aoi");
    s = ok(G.claimMission(s, m.id)).save;
    expect(s.gems).toBe(3000 + 100);
    expect(G.claimMission(s, m.id).ok).toBe(false);
  });

  it("編成：同じ剣華を別枠に置くと入れ替わる", () => {
    let s = G.newSave(NOW);
    s = G.setTeamSlot(s, 3, "yuzu");
    expect(s.team).toEqual([null, "chizuru", "koyuki", "yuzu", "akari"]);
  });

  it("推奨レベルは単調増加", () => {
    for (let i = 1; i < STAGES.length; i++) expect(STAGES[i].recommendedLevel).toBeGreaterThanOrEqual(STAGES[i - 1].recommendedLevel);
  });
});

describe("セーブ移行", () => {
  it("v1（設定なし・花片別テーブル）をv2に変換", () => {
    const v1 = {
      version: 1,
      createdAt: NOW,
      gems: 10,
      gold: 20,
      roster: { koyuki: { level: 5, star: 1 } },
      shardsById: { koyuki: 7 },
      team: ["koyuki", null, null, null, null],
      cleared: 2,
      pity: 3,
      idleSince: NOW,
    };
    const s = migrate(v1, NOW);
    expect(s.version).toBe(G.SAVE_VERSION);
    expect(s.roster.koyuki).toEqual({ level: 5, star: 1, shards: 7 });
    expect(s.settings).toEqual(G.DEFAULT_SETTINGS);
    expect(s.counters.pulls).toBe(0);
    expect((s as unknown as Record<string, unknown>).shardsById).toBeUndefined();
  });

  it("壊れたデータ・空は新規データ", () => {
    expect(migrate(null, NOW).roster.koyuki).toBeDefined();
    expect(migrate("x", NOW).gems).toBe(3000);
  });

  it("保存→読み込みで同じ内容", () => {
    const repo = new MemorySaveRepository();
    const s = G.newSave(NOW);
    repo.save(s);
    expect(migrate(repo.load(), NOW)).toEqual(s);
  });
});
