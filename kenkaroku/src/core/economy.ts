// レベル・開花コスト、放置報酬、花結び価格

export const MAX_STAR = 10;
export const SHARDS_PER_DUPLICATE = 10;

export const levelCap = (star: number) => 40 + 20 * (star - 1);

/** star → star+1 に必要な花片。満開なら null */
export function bloomCost(star: number): number | null {
  return star >= MAX_STAR ? null : 10 * star;
}

/** lv → lv+1 に必要な両（金） */
export function levelUpCost(lv: number): number {
  return Math.round(20 * lv ** 1.35);
}

/** 花の段階名（★1=蕾 … ★10=満開） */
export const BLOOM_STAGES = [
  "蕾",
  "一分咲き",
  "二分咲き",
  "三分咲き",
  "五分咲き",
  "六分咲き",
  "七分咲き",
  "八分咲き",
  "九分咲き",
  "満開",
] as const;

export const bloomStageName = (star: number) => BLOOM_STAGES[Math.max(1, Math.min(MAX_STAR, star)) - 1];

// ---- 放置報酬 ----
export const IDLE_CAP_HOURS = 12;
export const FAST_IDLE_HOURS = 2;
export const FAST_IDLE_DAILY = 2;

export interface IdleReward {
  gold: number;
  gems: number;
  hours: number;
}

export const goldPerHour = (cleared: number) => 1000 + 250 * cleared;
export const gemsPerHour = 10;

/** 経過時間（ミリ秒）と突破数から放置報酬を計算。12時間で頭打ち。 */
export function idleReward(elapsedMs: number, cleared: number): IdleReward {
  const hours = Math.min(IDLE_CAP_HOURS, Math.max(0, elapsedMs) / 3_600_000);
  return {
    hours,
    gold: Math.floor(goldPerHour(cleared) * hours),
    gems: Math.floor(gemsPerHour * hours),
  };
}

export function fastIdleReward(cleared: number): IdleReward {
  return idleReward(FAST_IDLE_HOURS * 3_600_000, cleared);
}

/** ローカル日付キー（日替わり判定用） */
export function dayKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

// ---- 花結び ----
export const PULL_COST_SINGLE = 150;
export const PULL_COST_TEN = 1500;

export const START_GEMS = 3000;
export const START_GOLD = 5000;
