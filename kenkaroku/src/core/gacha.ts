import type { Rarity } from "./types";
import type { Rng } from "./rng";
import { SHARDS_PER_DUPLICATE } from "./economy";

export const RATE_UR = 0.03;
export const RATE_SSR = 0.15;
export const PICKUP_SHARE = 0.5;
export const PITY = 80;

export interface GachaPool {
  pickup: string; // ピックアップUR
  ur: string[]; // ピックアップを含むUR全員
  ssr: string[];
  sr: string[];
}

export interface PullResult {
  charId: string;
  rarity: Rarity;
  pickup: boolean;
  /** 天井で確定したUR */
  byPity: boolean;
  /** 十連の最低保証で引き上げられた */
  byGuarantee: boolean;
}

function pickUr(rng: Rng, pool: GachaPool): { charId: string; pickup: boolean } {
  const others = pool.ur.filter((id) => id !== pool.pickup);
  if (others.length === 0 || rng.chance(PICKUP_SHARE)) return { charId: pool.pickup, pickup: true };
  return { charId: rng.pick(others), pickup: false };
}

function rollOne(rng: Rng, pool: GachaPool, pity: number, minSSR: boolean): PullResult {
  if (pity + 1 >= PITY) {
    return { charId: pool.pickup, rarity: "UR", pickup: true, byPity: true, byGuarantee: false };
  }
  const r = rng.next();
  if (minSSR) {
    // SSR以上確定枠：UR:SSR を本来の比率（3:15）で配分
    if (r < RATE_UR / (RATE_UR + RATE_SSR)) {
      return { ...pickUr(rng, pool), rarity: "UR", byPity: false, byGuarantee: true };
    }
    return { charId: rng.pick(pool.ssr), rarity: "SSR", pickup: false, byPity: false, byGuarantee: true };
  }
  if (r < RATE_UR) return { ...pickUr(rng, pool), rarity: "UR", byPity: false, byGuarantee: false };
  if (r < RATE_UR + RATE_SSR) return { charId: rng.pick(pool.ssr), rarity: "SSR", pickup: false, byPity: false, byGuarantee: false };
  return { charId: rng.pick(pool.sr), rarity: "SR", pickup: false, byPity: false, byGuarantee: false };
}

/**
 * count回引く。pity は「最後にURが出てからの回数」。
 * 十連（count===10）は最後の1回で SSR 以上を保証する。
 */
export function pull(
  rng: Rng,
  pool: GachaPool,
  pity: number,
  count: 1 | 10,
): { results: PullResult[]; pity: number } {
  const results: PullResult[] = [];
  let p = pity;
  for (let i = 0; i < count; i++) {
    const needGuarantee = count === 10 && i === count - 1 && !results.some((r) => r.rarity !== "SR");
    const res = rollOne(rng, pool, p, needGuarantee);
    p = res.rarity === "UR" ? 0 : p + 1;
    results.push(res);
  }
  return { results, pity: p };
}

export interface ResolvedPull extends PullResult {
  isNew: boolean;
  shards: number; // 被りで得た花片
}

/** 所持状況と照らして、新規入手か被り（花片化）かを決める */
export function resolveDuplicates(owned: ReadonlySet<string>, results: PullResult[]): ResolvedPull[] {
  const have = new Set(owned);
  return results.map((r) => {
    if (have.has(r.charId)) return { ...r, isNew: false, shards: SHARDS_PER_DUPLICATE };
    have.add(r.charId);
    return { ...r, isNew: true, shards: 0 };
  });
}
