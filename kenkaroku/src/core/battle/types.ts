import type { Element, Role, Skill, Stats, StatusType } from "../types";

export type Side = "ally" | "enemy";

/** 戦闘に入る1体分の設定 */
export interface UnitSetup {
  refId: string; // キャラID or 敵ID
  name: string;
  element: Element;
  role: Role;
  stats: Stats;
  skill: Skill;
  /** 0,1=前列 2,3,4=後列 */
  slot: number;
  /** 開始時の気力（省略時0） */
  energy?: number;
}

export interface BattleInput {
  allies: UnitSetup[];
  enemies: UnitSetup[];
  seed: number;
  maxRounds?: number;
}

export interface StatusInstance {
  type: Exclude<StatusType, "shield">;
  turns: number;
  power: number; // 継続ダメージ量（その他は0）
}

export interface UnitState {
  uid: string; // "ally-0" など
  side: Side;
  setup: UnitSetup;
  hp: number;
  maxHp: number;
  energy: number;
  shield: number;
  shieldTurns: number;
  statuses: StatusInstance[];
}

export interface HitResult {
  target: string;
  kind: "damage" | "heal" | "shield";
  amount: number;
  crit?: boolean;
  elem?: "adv" | "dis";
  absorbed?: number;
  hpAfter: number;
  shieldAfter: number;
  energyAfter: number;
  killed?: boolean;
  status?: StatusType;
}

export type BattleEvent =
  | { t: "round"; round: number }
  | {
      t: "action";
      round: number;
      actor: string;
      kind: "attack" | "skill";
      skillName?: string;
      hits: HitResult[];
      actorEnergy: number;
    }
  | { t: "dot"; round: number; unit: string; status: "bleed" | "burn"; dmg: number; hpAfter: number; shieldAfter: number; killed: boolean }
  | { t: "skip"; round: number; unit: string; reason: "freeze" | "stun" }
  | { t: "expire"; round: number; unit: string; statuses: StatusType[] }
  | { t: "end"; win: boolean; reason: "allEnemiesDown" | "allAlliesDown" | "timeout"; rounds: number };

export interface BattleResult {
  win: boolean;
  rounds: number;
  reason: "allEnemiesDown" | "allAlliesDown" | "timeout";
  seed: number;
  /** 戦闘開始時点の状態（演出の初期表示用） */
  initial: UnitState[];
  events: BattleEvent[];
  final: UnitState[];
}
