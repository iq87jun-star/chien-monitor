import type { Rarity, Role, Stats } from "./types";

/** Lv1・SR・★1 の役割別基礎値 */
export const ROLE_BASE: Record<Role, Stats> = {
  atk: { hp: 520, atk: 60, def: 24, spd: 105 },
  mag: { hp: 450, atk: 66, def: 20, spd: 100 },
  def: { hp: 780, atk: 40, def: 42, spd: 92 },
  heal: { hp: 540, atk: 48, def: 28, spd: 98 },
};

export const RARITY_MULT: Record<Rarity, number> = { SR: 1, SSR: 1.15, UR: 1.32 };

export const levelMult = (lv: number) => 1 + 0.07 * (lv - 1);
export const starMult = (star: number) => 1 + 0.1 * (star - 1);

function apply(base: Stats, mod: Partial<Stats> | undefined, mult: number, spdMult: number): Stats {
  return {
    hp: Math.round(base.hp * (mod?.hp ?? 1) * mult),
    atk: Math.round(base.atk * (mod?.atk ?? 1) * mult),
    def: Math.round(base.def * (mod?.def ?? 1) * mult),
    spd: Math.round(base.spd * (mod?.spd ?? 1) * spdMult),
  };
}

export function characterStats(
  role: Role,
  rarity: Rarity,
  level: number,
  star: number,
  mod?: Partial<Stats>,
): Stats {
  const m = RARITY_MULT[rarity] * levelMult(level) * starMult(star);
  return apply(ROLE_BASE[role], mod, m, 1 + 0.01 * (star - 1));
}

export function enemyStats(role: Role, level: number, mod?: Partial<Stats>): Stats {
  return apply(ROLE_BASE[role], mod, 0.95 * levelMult(level), 1);
}

/** 戦力の目安（表示用） */
export function power(s: Stats): number {
  return Math.round(s.hp * 0.2 + s.atk * 2.5 + s.def * 2 + s.spd);
}
