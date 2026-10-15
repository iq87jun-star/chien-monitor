// 戦闘エンジン：シードを受け取る純関数。同じ入力なら必ず同じ結果になる。
import { createRng, type Rng } from "../rng";
import type { Element, SkillEffect, StatusType, TargetRule } from "../types";
import type { BattleEvent, BattleInput, BattleResult, HitResult, Side, UnitState } from "./types";

export const MAX_ROUNDS = 20;
export const ENERGY_MAX = 100;
export const ENERGY_ON_ATTACK = 40;
export const ENERGY_ON_HIT = 10;
export const ELEM_ADV = 1.3;
export const ELEM_DIS = 0.85;
export const CRIT_RATE = 0.1;
export const CRIT_MULT = 1.5;
export const ATK_DOWN_MULT = 0.7;
export const FRONT_SLOTS = [0, 1];

/** 炎→嵐→岩→潮→炎（左が右に有利） */
const BEATS: Record<Element, Element> = { fire: "wind", wind: "rock", rock: "water", water: "fire" };

export function elementMultiplier(attacker: Element, defender: Element): number {
  if (BEATS[attacker] === defender) return ELEM_ADV;
  if (BEATS[defender] === attacker) return ELEM_DIS;
  return 1;
}

const clone = (u: UnitState): UnitState => ({ ...u, statuses: u.statuses.map((s) => ({ ...s })) });

function makeUnits(input: BattleInput): UnitState[] {
  const mk = (side: Side) => (s: BattleInput["allies"][number]): UnitState => ({
    uid: `${side}-${s.slot}`,
    side,
    setup: s,
    hp: s.stats.hp,
    maxHp: s.stats.hp,
    energy: s.energy ?? 0,
    shield: 0,
    shieldTurns: 0,
    statuses: [],
  });
  return [...input.allies.map(mk("ally")), ...input.enemies.map(mk("enemy"))];
}

const alive = (u: UnitState) => u.hp > 0;
const has = (u: UnitState, t: StatusType) => u.statuses.some((s) => s.type === t);
const effAtk = (u: UnitState) => u.setup.stats.atk * (has(u, "atkDown") ? ATK_DOWN_MULT : 1);
const hpRate = (u: UnitState) => u.hp / u.maxHp;

function pickTargets(rule: TargetRule, self: UnitState, units: UnitState[], rng: Rng): UnitState[] {
  const foes = units.filter((u) => u.side !== self.side && alive(u));
  const friends = units.filter((u) => u.side === self.side && alive(u));
  const lowest = (list: UnitState[]) =>
    list.length === 0 ? [] : [list.reduce((a, b) => (hpRate(b) < hpRate(a) ? b : a))];
  switch (rule) {
    case "front":
    case "back": {
      const front = foes.filter((u) => FRONT_SLOTS.includes(u.setup.slot));
      const back = foes.filter((u) => !FRONT_SLOTS.includes(u.setup.slot));
      const primary = rule === "front" ? front : back;
      const list = primary.length > 0 ? primary : rule === "front" ? back : front;
      return list.length > 0 ? [rng.pick(list)] : [];
    }
    case "all":
      return foes;
    case "lowestHp":
      return lowest(foes);
    case "self":
      return [self];
    case "allAllies":
      return friends;
    case "lowestAlly":
      return lowest(friends);
  }
}

function dealDamage(
  actor: UnitState,
  target: UnitState,
  mult: number,
  rng: Rng,
): HitResult {
  const elem = elementMultiplier(actor.setup.element, target.setup.element);
  const crit = rng.chance(CRIT_RATE);
  const variance = 0.9 + rng.next() * 0.2;
  const def = target.setup.stats.def;
  const raw = effAtk(actor) * mult * (100 / (100 + def)) * elem * (crit ? CRIT_MULT : 1) * variance;
  const dmg = Math.max(1, Math.round(raw));
  const absorbed = Math.min(target.shield, dmg);
  target.shield -= absorbed;
  if (target.shield === 0) target.shieldTurns = 0;
  target.hp = Math.max(0, target.hp - (dmg - absorbed));
  if (target.hp > 0) target.energy = Math.min(ENERGY_MAX, target.energy + ENERGY_ON_HIT);
  return {
    target: target.uid,
    kind: "damage",
    amount: dmg,
    crit: crit || undefined,
    elem: elem > 1 ? "adv" : elem < 1 ? "dis" : undefined,
    absorbed: absorbed || undefined,
    hpAfter: target.hp,
    shieldAfter: target.shield,
    energyAfter: target.energy,
    killed: target.hp === 0 || undefined,
  };
}

function applyEffect(actor: UnitState, eff: SkillEffect, units: UnitState[], rng: Rng): HitResult[] {
  const out: HitResult[] = [];
  if (eff.kind === "damage") {
    const hits = eff.hits ?? 1;
    let targets: UnitState[] = [];
    for (let h = 0; h < hits; h++) {
      // 単体技は対象が倒れたら選び直す
      if (h === 0 || targets.every((t) => !alive(t))) targets = pickTargets(eff.target, actor, units, rng);
      for (const t of targets) {
        if (!alive(t)) continue;
        const hit = dealDamage(actor, t, eff.mult, rng);
        if (eff.status && alive(t) && rng.chance(eff.status.chance)) {
          const power = Math.round(effAtk(actor) * (eff.status.power ?? 0));
          const existing = t.statuses.find((s) => s.type === eff.status!.type);
          if (existing) {
            existing.turns = Math.max(existing.turns, eff.status.turns);
            existing.power = Math.max(existing.power, power);
          } else {
            t.statuses.push({ type: eff.status.type, turns: eff.status.turns, power });
          }
          hit.status = eff.status.type;
        }
        out.push(hit);
      }
    }
  } else if (eff.kind === "heal") {
    for (const t of pickTargets(eff.target, actor, units, rng)) {
      const amount = Math.round(effAtk(actor) * eff.mult);
      const before = t.hp;
      t.hp = Math.min(t.maxHp, t.hp + amount);
      out.push({
        target: t.uid,
        kind: "heal",
        amount: t.hp - before,
        hpAfter: t.hp,
        shieldAfter: t.shield,
        energyAfter: t.energy,
      });
    }
  } else {
    for (const t of pickTargets(eff.target, actor, units, rng)) {
      const amount = Math.round(actor.maxHp * eff.ratio);
      t.shield = Math.max(t.shield, amount);
      t.shieldTurns = Math.max(t.shieldTurns, eff.turns);
      out.push({
        target: t.uid,
        kind: "shield",
        amount,
        hpAfter: t.hp,
        shieldAfter: t.shield,
        energyAfter: t.energy,
        status: "shield",
      });
    }
  }
  return out;
}

/** 行動順：素早さ降順、同値なら味方→敵、枠番号順 */
export function turnOrder(units: UnitState[]): UnitState[] {
  return [...units].sort(
    (a, b) =>
      b.setup.stats.spd - a.setup.stats.spd ||
      (a.side === b.side ? 0 : a.side === "ally" ? -1 : 1) ||
      a.setup.slot - b.setup.slot,
  );
}

export function simulateBattle(input: BattleInput): BattleResult {
  const rng = createRng(input.seed);
  const maxRounds = input.maxRounds ?? MAX_ROUNDS;
  const units = makeUnits(input);
  const initial = units.map(clone);
  const events: BattleEvent[] = [];

  const sideDown = (side: Side) => units.filter((u) => u.side === side).every((u) => !alive(u));
  const finish = (win: boolean, reason: "allEnemiesDown" | "allAlliesDown" | "timeout", rounds: number): BattleResult => {
    events.push({ t: "end", win, reason, rounds });
    return { win, rounds, reason, seed: input.seed, initial, events, final: units.map(clone) };
  };
  const checkEnd = (round: number): BattleResult | null => {
    if (sideDown("enemy")) return finish(true, "allEnemiesDown", round);
    if (sideDown("ally")) return finish(false, "allAlliesDown", round);
    return null;
  };

  const early = checkEnd(0);
  if (early) return early;

  for (let round = 1; round <= maxRounds; round++) {
    events.push({ t: "round", round });
    for (const u of turnOrder(units)) {
      if (!alive(u)) continue;

      // 0) 盾は自分の手番の開始時に残り合数を減らす（張った直後の手番では消えない）
      if (u.shieldTurns > 0) {
        u.shieldTurns -= 1;
        if (u.shieldTurns === 0 && u.shield > 0) {
          u.shield = 0;
          events.push({ t: "expire", round, unit: u.uid, statuses: ["shield"] });
        }
      }

      // 1) 継続ダメージ
      for (const s of u.statuses) {
        if ((s.type === "bleed" || s.type === "burn") && alive(u)) {
          const dmg = Math.max(1, s.power);
          const absorbed = Math.min(u.shield, dmg);
          u.shield -= absorbed;
          u.hp = Math.max(0, u.hp - (dmg - absorbed));
          events.push({ t: "dot", round, unit: u.uid, status: s.type, dmg, hpAfter: u.hp, shieldAfter: u.shield, killed: u.hp === 0 });
        }
      }
      if (!alive(u)) {
        const end = checkEnd(round);
        if (end) return end;
        continue;
      }

      // 2) 行動
      const cc = u.statuses.find((s) => s.type === "freeze" || s.type === "stun");
      if (cc) {
        events.push({ t: "skip", round, unit: u.uid, reason: cc.type as "freeze" | "stun" });
      } else if (u.energy >= ENERGY_MAX) {
        u.energy = 0;
        const hits = u.setup.skill.effects.flatMap((e) => applyEffect(u, e, units, rng));
        events.push({ t: "action", round, actor: u.uid, kind: "skill", skillName: u.setup.skill.name, hits, actorEnergy: u.energy });
      } else {
        u.energy = Math.min(ENERGY_MAX, u.energy + ENERGY_ON_ATTACK);
        const hits = applyEffect(u, { kind: "damage", target: "front", mult: 1 }, units, rng);
        events.push({ t: "action", round, actor: u.uid, kind: "attack", hits, actorEnergy: u.energy });
      }

      // 3) 自分の状態異常の残り合数を減らす
      const expired: StatusType[] = [];
      for (const s of u.statuses) s.turns -= 1;
      for (const s of u.statuses) if (s.turns <= 0) expired.push(s.type);
      u.statuses = u.statuses.filter((s) => s.turns > 0);
      if (expired.length) events.push({ t: "expire", round, unit: u.uid, statuses: expired });

      const end = checkEnd(round);
      if (end) return end;
    }
  }
  return finish(false, "timeout", maxRounds);
}
