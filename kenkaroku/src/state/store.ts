import { create } from "zustand";
import { CURRENT_BANNER } from "../data/banners";
import * as G from "../core/game";
import type { SaveData } from "../core/game";
import { randomSeed } from "../core/rng";
import type { IdleReward } from "../core/economy";
import type { ResolvedPull } from "../core/gacha";
import type { BattleResult } from "../core/battle/types";
import type { Element } from "../core/types";
import { migrate } from "./migrate";
import { LocalStorageSaveRepository, type SaveRepository } from "./saveRepository";

let repo: SaveRepository = new LocalStorageSaveRepository();

/** テスト等で保存先を差し替える */
export function setSaveRepository(r: SaveRepository) {
  repo = r;
}

type StageOutcome = { result: BattleResult; rewards: G.StageRewards | null; save: SaveData };
type TrialOutcome = { result: BattleResult; shards: number; save: SaveData };

interface GameStore {
  save: SaveData;
  toast: { id: number; text: string } | null;
  /** 操作結果を受け取って保存。失敗ならトーストを出して null */
  apply<T extends object>(out: G.Outcome<T>): (T & { save: SaveData }) | null;
  notify(text: string): void;
  reset(): void;

  levelUp(id: string, times?: number): boolean;
  bloom(id: string): number | null;
  setTeamSlot(slot: number, id: string | null): void;
  setTeam(team: (string | null)[]): void;
  pull(count: 1 | 10): ResolvedPull[] | null;
  claimIdle(): G.Outcome<{ reward: IdleReward }>;
  fastIdle(): G.Outcome<{ reward: IdleReward }>;
  fightStage(index: number): StageOutcome | null;
  fightTrial(element: Element, level: number, target: string): TrialOutcome | null;
  claimMission(id: string): boolean;
  updateSettings(p: Partial<G.Settings>): void;
}

let toastId = 0;

export const useGame = create<GameStore>((set, get) => ({
  save: migrate(repo.load(), Date.now()),
  toast: null,

  apply(out) {
    if (!out.ok) {
      get().notify(out.error);
      return null;
    }
    repo.save(out.save);
    set({ save: out.save });
    return out;
  },
  notify(text) {
    set({ toast: { id: ++toastId, text } });
  },
  reset() {
    repo.clear();
    set({ save: G.newSave(Date.now()) });
  },

  levelUp(id, times = 1) {
    return !!get().apply(G.levelUp(get().save, id, times));
  },
  bloom(id) {
    const r = get().apply(G.bloom(get().save, id));
    return r ? r.star : null;
  },
  setTeamSlot(slot, id) {
    get().apply({ ok: true, save: G.setTeamSlot(get().save, slot, id) });
  },
  setTeam(team) {
    get().apply({ ok: true, save: { ...get().save, team: team.slice(0, 5) } });
  },
  pull(count) {
    const r = get().apply(G.gachaPull(get().save, CURRENT_BANNER, count, randomSeed()));
    return r ? r.results : null;
  },
  claimIdle() {
    const out = G.claimIdle(get().save, Date.now());
    get().apply(out);
    return out;
  },
  fastIdle() {
    const out = G.useFastIdle(get().save, Date.now());
    get().apply(out);
    return out;
  },
  fightStage(index) {
    return get().apply(G.fightStage(get().save, index, randomSeed()));
  },
  fightTrial(element, level, target) {
    return get().apply(G.fightTrial(get().save, element, level, target, randomSeed(), Date.now()));
  },
  claimMission(id) {
    return !!get().apply(G.claimMission(get().save, id));
  },
  updateSettings(p) {
    const s = get().save;
    get().apply({ ok: true, save: { ...s, settings: { ...s.settings, ...p } } });
  },
}));
