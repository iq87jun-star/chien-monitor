import { describe, expect, it } from "vitest";
import { simulateBattle, elementMultiplier, MAX_ROUNDS, turnOrder } from "../src/core/battle/engine";
import { enemyUnits, teamUnits } from "../src/core/battle/setup";
import type { UnitSetup } from "../src/core/battle/types";
import { STAGES } from "../src/data/stages";

const roster = {
  koyuki: { level: 10, star: 1 },
  aoi: { level: 10, star: 1 },
  yuzu: { level: 10, star: 1 },
  akari: { level: 10, star: 1 },
  chizuru: { level: 10, star: 1 },
};
const team = ["yuzu", "chizuru", "koyuki", "aoi", "akari"];

function dummy(slot: number, over: Partial<UnitSetup> = {}): UnitSetup {
  return {
    refId: "d",
    name: "d",
    element: "fire",
    role: "atk",
    stats: { hp: 1000, atk: 100, def: 0, spd: 100 },
    skill: { name: "s", desc: "", effects: [{ kind: "damage", target: "front", mult: 1 }] },
    slot,
    ...over,
  };
}

describe("属性相性", () => {
  it("炎→嵐→岩→潮→炎で有利1.3／不利0.85", () => {
    expect(elementMultiplier("fire", "wind")).toBe(1.3);
    expect(elementMultiplier("wind", "rock")).toBe(1.3);
    expect(elementMultiplier("rock", "water")).toBe(1.3);
    expect(elementMultiplier("water", "fire")).toBe(1.3);
    expect(elementMultiplier("wind", "fire")).toBe(0.85);
    expect(elementMultiplier("fire", "water")).toBe(0.85);
    expect(elementMultiplier("fire", "rock")).toBe(1);
    expect(elementMultiplier("fire", "fire")).toBe(1);
  });
});

describe("戦闘エンジン", () => {
  const input = (seed: number) => ({
    allies: teamUnits(team, roster),
    enemies: enemyUnits(STAGES[3].enemies, STAGES[3].enemyLevel),
    seed,
  });

  it("同じシードなら同じ結果になる", () => {
    const a = simulateBattle(input(12345));
    const b = simulateBattle(input(12345));
    expect(a).toEqual(b);
  });

  it("シードが違えば経過が変わる", () => {
    const a = simulateBattle(input(1));
    const b = simulateBattle(input(2));
    expect(JSON.stringify(a.events)).not.toEqual(JSON.stringify(b.events));
  });

  it("入力のステータスを書き換えない（純関数）", () => {
    const i = input(7);
    const snapshot = JSON.stringify(i);
    simulateBattle(i);
    expect(JSON.stringify(i)).toBe(snapshot);
  });

  it("20合で決着しなければ時間切れ敗北", () => {
    const tank = (slot: number) =>
      dummy(slot, { stats: { hp: 1_000_000, atk: 1, def: 0, spd: 100 } });
    const r = simulateBattle({ allies: [tank(0)], enemies: [tank(0)], seed: 1 });
    expect(r.win).toBe(false);
    expect(r.reason).toBe("timeout");
    expect(r.rounds).toBe(MAX_ROUNDS);
    expect(r.events.filter((e) => e.t === "round")).toHaveLength(20);
  });

  it("通常攻撃は前列を狙う", () => {
    const r = simulateBattle({
      allies: [dummy(0, { stats: { hp: 1e6, atk: 10, def: 0, spd: 200 } })],
      enemies: [dummy(1, { stats: { hp: 1e6, atk: 1, def: 0, spd: 1 } }), dummy(3, { stats: { hp: 1e6, atk: 1, def: 0, spd: 1 } })],
      seed: 3,
      maxRounds: 2,
    });
    const first = r.events.find((e) => e.t === "action" && e.actor === "ally-0");
    expect(first && first.t === "action" && first.hits[0].target).toBe("enemy-1");
  });

  it("前列が全滅すると後列が狙われる", () => {
    const r = simulateBattle({
      allies: [dummy(0, { stats: { hp: 1e6, atk: 10, def: 0, spd: 200 } })],
      enemies: [dummy(3, { stats: { hp: 1e6, atk: 1, def: 0, spd: 1 } })],
      seed: 3,
      maxRounds: 1,
    });
    const first = r.events.find((e) => e.t === "action" && e.actor === "ally-0");
    expect(first && first.t === "action" && first.hits[0].target).toBe("enemy-3");
  });

  it("気力：通常攻撃+40、被弾+10、100でスキル", () => {
    const r = simulateBattle({
      allies: [dummy(0, { stats: { hp: 1e6, atk: 1, def: 0, spd: 200 } })],
      enemies: [dummy(0, { stats: { hp: 1e6, atk: 1, def: 0, spd: 1 } })],
      seed: 9,
      maxRounds: 4,
    });
    const acts = r.events.filter((e) => e.t === "action" && e.actor === "ally-0");
    // 1合目：攻撃で0→40（被弾で50）、2合目：攻撃で90（被弾で100）、3合目：スキル発動で0
    const a1 = acts[0];
    expect(a1.t === "action" && a1.kind).toBe("attack");
    expect(a1.t === "action" && a1.actorEnergy).toBe(40);
    expect(a1.t === "action" && a1.hits[0].energyAfter).toBe(10);
    const a2 = acts[1];
    expect(a2.t === "action" && a2.actorEnergy).toBe(90);
    const a3 = acts[2];
    expect(a3.t === "action" && a3.kind).toBe("skill");
    expect(a3.t === "action" && a3.actorEnergy).toBe(0);
  });

  it("凍結・目眩は行動不能", () => {
    const freezer = dummy(0, {
      stats: { hp: 1e6, atk: 1, def: 0, spd: 200 },
      skill: { name: "f", desc: "", effects: [{ kind: "damage", target: "front", mult: 1, status: { type: "freeze", chance: 1, turns: 1 } }] },
    });
    const r = simulateBattle({ allies: [freezer], enemies: [dummy(0, { stats: { hp: 1e6, atk: 1, def: 0, spd: 1 } })], seed: 1, maxRounds: 6 });
    expect(r.events.some((e) => e.t === "skip" && e.unit === "enemy-0" && e.reason === "freeze")).toBe(true);
  });

  it("出血・火傷は手番の開始時にダメージ", () => {
    const burner = dummy(0, {
      stats: { hp: 1e6, atk: 100, def: 0, spd: 200 },
      skill: { name: "b", desc: "", effects: [{ kind: "damage", target: "front", mult: 1, status: { type: "burn", chance: 1, turns: 2, power: 0.5 } }] },
    });
    const r = simulateBattle({ allies: [burner], enemies: [dummy(0, { stats: { hp: 1e6, atk: 1, def: 0, spd: 1 } })], seed: 1, maxRounds: 6 });
    const dots = r.events.filter((e) => e.t === "dot");
    expect(dots.length).toBeGreaterThan(0);
    expect(dots[0].t === "dot" && dots[0].dmg).toBe(50);
  });

  it("盾がダメージを先に受ける", () => {
    const shielder = dummy(0, {
      stats: { hp: 1000, atk: 1, def: 0, spd: 200 },
      skill: { name: "s", desc: "", effects: [{ kind: "shield", target: "self", ratio: 1, turns: 2 }] },
    });
    // 気力を満タンにするため、事前に3回攻撃させる
    const r = simulateBattle({
      allies: [shielder],
      enemies: [dummy(0, { stats: { hp: 1e6, atk: 50, def: 0, spd: 1 } })],
      seed: 4,
      maxRounds: 5,
    });
    const absorbed = r.events.some(
      (e) => e.t === "action" && e.actor === "enemy-0" && e.hits.some((h) => (h.absorbed ?? 0) > 0),
    );
    expect(absorbed).toBe(true);
  });

  it("攻撃力低下で与ダメージが約7割になる", () => {
    const enemyHit = (debuff: boolean, seed: number) => {
      const r = simulateBattle({
        allies: [
          dummy(0, {
            stats: { hp: 1e6, atk: 1, def: 0, spd: 200 },
            energy: 100,
            skill: {
              name: "x",
              desc: "",
              effects: debuff ? [{ kind: "damage", target: "front", mult: 0, status: { type: "atkDown", chance: 1, turns: 2 } }] : [],
            },
          }),
        ],
        enemies: [dummy(0, { stats: { hp: 1e6, atk: 1000, def: 0, spd: 1 } })],
        seed,
        maxRounds: 1,
      });
      const a = r.events.find((e) => e.t === "action" && e.actor === "enemy-0");
      return a && a.t === "action" ? a.hits[0].amount : 0;
    };
    // 乱数（会心・揺らぎ）をならすため複数シードで平均を取る
    let withDebuff = 0;
    let without = 0;
    for (let seed = 0; seed < 300; seed++) {
      withDebuff += enemyHit(true, seed);
      without += enemyHit(false, seed);
    }
    const ratio = withDebuff / without;
    expect(ratio).toBeCloseTo(0.7, 1);
  });

  it("行動順は素早さ順", () => {
    const r = simulateBattle({
      allies: [dummy(0, { stats: { hp: 1e6, atk: 1, def: 0, spd: 50 } })],
      enemies: [dummy(0, { stats: { hp: 1e6, atk: 1, def: 0, spd: 150 } })],
      seed: 1,
      maxRounds: 1,
    });
    const order = turnOrder(r.initial).map((u) => u.uid);
    expect(order).toEqual(["enemy-0", "ally-0"]);
    const firstAct = r.events.find((e) => e.t === "action");
    expect(firstAct && firstAct.t === "action" && firstAct.actor).toBe("enemy-0");
  });

  it("序盤ステージは初期編成で勝てる", () => {
    const starter = Object.fromEntries(team.map((id) => [id, { level: 1, star: 1 }]));
    let wins = 0;
    for (let s = 0; s < 20; s++) {
      const r = simulateBattle({ allies: teamUnits(team, starter), enemies: enemyUnits(STAGES[0].enemies, STAGES[0].enemyLevel), seed: s });
      if (r.win) wins++;
    }
    expect(wins).toBeGreaterThanOrEqual(18);
  });
});
