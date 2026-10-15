// セーブデータに対する操作（純関数）。ストアはこれを呼ぶだけにする。
import { CHAR_BY_ID, STARTER_IDS } from "../data/characters";
import { BEGINNER_MISSIONS } from "../data/missions";
import { STAGES, TRIALS, TRIAL_DAILY_LIMIT, TRIAL_LEVELS } from "../data/stages";
import type { BannerDef } from "../data/banners";
import { bannerPool } from "../data/banners";
import { simulateBattle } from "./battle/engine";
import { enemyUnits, teamUnits } from "./battle/setup";
import type { BattleResult } from "./battle/types";
import {
  bloomCost,
  dayKey,
  FAST_IDLE_DAILY,
  fastIdleReward,
  idleReward,
  levelCap,
  levelUpCost,
  MAX_STAR,
  PULL_COST_SINGLE,
  PULL_COST_TEN,
  START_GEMS,
  START_GOLD,
  type IdleReward,
} from "./economy";
import { pull, resolveDuplicates, type ResolvedPull } from "./gacha";
import { isMissionDone, type Progress } from "./missions";
import { createRng } from "./rng";
import type { Element } from "./types";

export interface OwnedState {
  level: number;
  star: number;
  shards: number;
}

export interface Settings {
  /** スキルカットイン */
  cutin: boolean;
  /** 戦闘速度 1/2/4 */
  speed: 1 | 2 | 4;
  /** 花結び演出 */
  gachaAnim: boolean;
}

export const DEFAULT_SETTINGS: Settings = { cutin: true, speed: 1, gachaAnim: true };

export const SAVE_VERSION = 2;

export interface SaveData {
  version: number;
  createdAt: number;
  gems: number;
  gold: number;
  roster: Record<string, OwnedState>;
  team: (string | null)[];
  /** 突破済みステージ数（順番に解放） */
  cleared: number;
  pity: number;
  idleSince: number;
  fastIdle: { day: string; used: number };
  trialsToday: { day: string; used: number };
  counters: { pulls: number; blooms: number; idleClaims: number; trials: number };
  missionsClaimed: string[];
  settings: Settings;
}

export function newSave(now: number): SaveData {
  const roster: Record<string, OwnedState> = {};
  for (const id of STARTER_IDS) roster[id] = { level: 1, star: 1, shards: 0 };
  return {
    version: SAVE_VERSION,
    createdAt: now,
    gems: START_GEMS,
    gold: START_GOLD,
    roster,
    team: ["yuzu", "chizuru", "koyuki", null, "akari"],
    cleared: 0,
    pity: 0,
    idleSince: now,
    fastIdle: { day: "", used: 0 },
    trialsToday: { day: "", used: 0 },
    counters: { pulls: 0, blooms: 0, idleClaims: 0, trials: 0 },
    missionsClaimed: [],
    settings: { ...DEFAULT_SETTINGS },
  };
}

export type Outcome<T = object> = ({ ok: true; save: SaveData } & T) | { ok: false; error: string };

const fail = (error: string): { ok: false; error: string } => ({ ok: false, error });

// ---- 育成 ----

export function levelUp(s: SaveData, id: string, times = 1): Outcome<{ levels: number }> {
  const o = s.roster[id];
  if (!o) return fail("未所持の剣華です");
  const cap = levelCap(o.star);
  let gold = s.gold;
  let lv = o.level;
  let n = 0;
  while (n < times && lv < cap && gold >= levelUpCost(lv)) {
    gold -= levelUpCost(lv);
    lv++;
    n++;
  }
  if (n === 0) return fail(lv >= cap ? "レベル上限です。開花で上限が上がります" : "両が足りません");
  return { ok: true, levels: n, save: { ...s, gold, roster: { ...s.roster, [id]: { ...o, level: lv } } } };
}

export function bloom(s: SaveData, id: string): Outcome<{ star: number }> {
  const o = s.roster[id];
  if (!o) return fail("未所持の剣華です");
  const cost = bloomCost(o.star);
  if (cost === null || o.star >= MAX_STAR) return fail("すでに満開です");
  if (o.shards < cost) return fail("花片が足りません");
  const star = o.star + 1;
  return {
    ok: true,
    star,
    save: {
      ...s,
      roster: { ...s.roster, [id]: { ...o, star, shards: o.shards - cost } },
      counters: { ...s.counters, blooms: s.counters.blooms + 1 },
    },
  };
}

// ---- 編成 ----

export function setTeamSlot(s: SaveData, slot: number, id: string | null): SaveData {
  const team = [...s.team];
  if (id) {
    const prev = team.indexOf(id);
    if (prev >= 0) team[prev] = team[slot]; // 入れ替え
  }
  team[slot] = id;
  return { ...s, team };
}

// ---- 花結び ----

export function gachaPull(
  s: SaveData,
  banner: BannerDef,
  count: 1 | 10,
  seed: number,
): Outcome<{ results: ResolvedPull[] }> {
  const cost = count === 10 ? PULL_COST_TEN : PULL_COST_SINGLE;
  if (s.gems < cost) return fail("花玉が足りません");
  const { results, pity } = pull(createRng(seed), bannerPool(banner), s.pity, count);
  const resolved = resolveDuplicates(new Set(Object.keys(s.roster)), results);
  const roster = { ...s.roster };
  for (const r of resolved) {
    if (r.isNew) roster[r.charId] = { level: 1, star: 1, shards: 0 };
    else roster[r.charId] = { ...roster[r.charId], shards: roster[r.charId].shards + r.shards };
  }
  return {
    ok: true,
    results: resolved,
    save: { ...s, gems: s.gems - cost, pity, roster, counters: { ...s.counters, pulls: s.counters.pulls + count } },
  };
}

// ---- 放置報酬 ----

export function pendingIdle(s: SaveData, now: number): IdleReward {
  return idleReward(now - s.idleSince, s.cleared);
}

export function claimIdle(s: SaveData, now: number): Outcome<{ reward: IdleReward }> {
  const reward = pendingIdle(s, now);
  if (reward.gold <= 0 && reward.gems <= 0) return fail("まだ報酬が貯まっていません");
  return {
    ok: true,
    reward,
    save: {
      ...s,
      gold: s.gold + reward.gold,
      gems: s.gems + reward.gems,
      idleSince: now,
      counters: { ...s.counters, idleClaims: s.counters.idleClaims + 1 },
    },
  };
}

export function fastIdleLeft(s: SaveData, now: number): number {
  const today = dayKey(new Date(now));
  return s.fastIdle.day === today ? Math.max(0, FAST_IDLE_DAILY - s.fastIdle.used) : FAST_IDLE_DAILY;
}

export function useFastIdle(s: SaveData, now: number): Outcome<{ reward: IdleReward }> {
  if (fastIdleLeft(s, now) <= 0) return fail("本日の高速放置は使い切りました");
  const today = dayKey(new Date(now));
  const used = s.fastIdle.day === today ? s.fastIdle.used + 1 : 1;
  const reward = fastIdleReward(s.cleared);
  return {
    ok: true,
    reward,
    save: { ...s, gold: s.gold + reward.gold, gems: s.gems + reward.gems, fastIdle: { day: today, used } },
  };
}

// ---- 出陣 ----

export interface StageRewards {
  gold: number;
  gems: number;
  firstClear: boolean;
}

export function fightStage(
  s: SaveData,
  index: number,
  seed: number,
): Outcome<{ result: BattleResult; rewards: StageRewards | null }> {
  const st = STAGES[index];
  if (!st) return fail("存在しないステージです");
  if (index > s.cleared) return fail("まだ解放されていません");
  const allies = teamUnits(s.team, s.roster);
  if (allies.length === 0) return fail("編成に剣華がいません");
  const result = simulateBattle({ allies, enemies: enemyUnits(st.enemies, st.enemyLevel), seed });
  if (!result.win) return { ok: true, result, rewards: null, save: s };
  const firstClear = index === s.cleared;
  const rewards = { gold: st.gold, gems: firstClear ? st.firstGems : 0, firstClear };
  return {
    ok: true,
    result,
    rewards,
    save: {
      ...s,
      gold: s.gold + rewards.gold,
      gems: s.gems + rewards.gems,
      cleared: firstClear ? s.cleared + 1 : s.cleared,
    },
  };
}

// ---- 開花任務（星上げ専用） ----

export function trialsLeft(s: SaveData, now: number): number {
  const today = dayKey(new Date(now));
  return s.trialsToday.day === today ? Math.max(0, TRIAL_DAILY_LIMIT - s.trialsToday.used) : TRIAL_DAILY_LIMIT;
}

export function fightTrial(
  s: SaveData,
  element: Element,
  level: number,
  targetId: string,
  seed: number,
  now: number,
): Outcome<{ result: BattleResult; shards: number }> {
  const trial = TRIALS.find((t) => t.element === element);
  const lv = TRIAL_LEVELS.find((l) => l.level === level);
  if (!trial || !lv) return fail("存在しない任務です");
  if (s.cleared < lv.requireStage) return fail(`ステージを${lv.requireStage}つ突破すると解放されます`);
  if (trialsLeft(s, now) <= 0) return fail("本日の挑戦回数を使い切りました");
  const target = s.roster[targetId];
  if (!target || CHAR_BY_ID[targetId]?.element !== element) return fail("この試練の属性の剣華を選んでください");
  const allies = teamUnits(s.team, s.roster);
  if (allies.length === 0) return fail("編成に剣華がいません");
  const result = simulateBattle({ allies, enemies: enemyUnits(trial.enemies, lv.enemyLevel), seed });
  const today = dayKey(new Date(now));
  // 挑戦回数は勝ったときだけ消費する
  if (!result.win) return { ok: true, result, shards: 0, save: s };
  const used = s.trialsToday.day === today ? s.trialsToday.used + 1 : 1;
  return {
    ok: true,
    result,
    shards: lv.shards,
    save: {
      ...s,
      roster: { ...s.roster, [targetId]: { ...target, shards: target.shards + lv.shards } },
      trialsToday: { day: today, used },
      counters: { ...s.counters, trials: s.counters.trials + 1 },
    },
  };
}

// ---- 任務 ----

export function progressOf(s: SaveData): Progress {
  const owned = Object.values(s.roster);
  return {
    stageCleared: s.cleared,
    pulls: s.counters.pulls,
    maxLevel: owned.reduce((m, o) => Math.max(m, o.level), 0),
    blooms: s.counters.blooms,
    teamSize: s.team.filter(Boolean).length,
    idleClaims: s.counters.idleClaims,
    trials: s.counters.trials,
    owned: owned.length,
  };
}

export function claimMission(s: SaveData, id: string): Outcome {
  const m = BEGINNER_MISSIONS.find((x) => x.id === id);
  if (!m) return fail("存在しない任務です");
  if (s.missionsClaimed.includes(id)) return fail("受け取り済みです");
  if (!isMissionDone(m, progressOf(s))) return fail("まだ達成していません");
  return {
    ok: true,
    save: {
      ...s,
      gems: s.gems + (m.reward.gems ?? 0),
      gold: s.gold + (m.reward.gold ?? 0),
      missionsClaimed: [...s.missionsClaimed, id],
    },
  };
}
