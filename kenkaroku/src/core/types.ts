// 画面に依存しない共通の型定義

export type Element = "fire" | "water" | "wind" | "rock";
export type Rarity = "SR" | "SSR" | "UR";
export type Role = "atk" | "mag" | "def" | "heal";

export const ELEMENT_LABEL: Record<Element, string> = {
  fire: "炎",
  water: "潮",
  wind: "嵐",
  rock: "岩",
};

export const ROLE_LABEL: Record<Role, string> = {
  atk: "攻",
  mag: "術",
  def: "守",
  heal: "癒",
};

export type StatusType = "bleed" | "burn" | "freeze" | "stun" | "atkDown" | "shield";

export const STATUS_LABEL: Record<StatusType, string> = {
  bleed: "出血",
  burn: "火傷",
  freeze: "凍結",
  stun: "目眩",
  atkDown: "攻撃低下",
  shield: "盾",
};

export interface Stats {
  hp: number;
  atk: number;
  def: number;
  spd: number;
}

/** スキルの対象 */
export type TargetRule =
  | "front" // 通常攻撃と同じ（前列優先）
  | "back" // 後列優先
  | "all" // 敵全体
  | "lowestHp" // HP割合が最も低い敵
  | "self"
  | "allAllies"
  | "lowestAlly"; // HP割合が最も低い味方

export interface StatusApply {
  type: Exclude<StatusType, "shield">;
  /** 0〜1 */
  chance: number;
  turns: number;
  /** 継続ダメージ系：術者攻撃力に対する倍率 */
  power?: number;
}

export type SkillEffect =
  | { kind: "damage"; target: TargetRule; mult: number; hits?: number; status?: StatusApply }
  | { kind: "heal"; target: TargetRule; mult: number }
  | { kind: "shield"; target: TargetRule; /** 術者最大HPに対する割合 */ ratio: number; turns: number };

export interface Skill {
  name: string;
  desc: string;
  effects: SkillEffect[];
}
