import type { MissionCond, MissionDef } from "../data/missions";

/** 任務判定に使う集計値 */
export interface Progress {
  stageCleared: number;
  pulls: number;
  maxLevel: number;
  blooms: number;
  teamSize: number;
  idleClaims: number;
  trials: number;
  owned: number;
}

export function condValue(cond: MissionCond, p: Progress): number {
  return p[cond.type];
}

export function isMissionDone(m: MissionDef, p: Progress): boolean {
  return condValue(m.cond, p) >= m.cond.n;
}
