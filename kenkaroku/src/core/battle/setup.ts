import { CHAR_BY_ID } from "../../data/characters";
import { ENEMY_BY_ID } from "../../data/enemies";
import { fullName } from "../../data/characters";
import { characterStats, enemyStats } from "../stats";
import type { UnitSetup } from "./types";

export interface OwnedChar {
  level: number;
  star: number;
}

/** 剣華を戦闘ユニットにする */
export function allyUnit(id: string, owned: OwnedChar, slot: number): UnitSetup {
  const c = CHAR_BY_ID[id];
  if (!c) throw new Error(`unknown character: ${id}`);
  return {
    refId: id,
    name: fullName(c),
    element: c.element,
    role: c.role,
    stats: characterStats(c.role, c.rarity, owned.level, owned.star, c.statMod),
    skill: c.skill,
    slot,
  };
}

/** 編成（5枠、null可）から味方ユニット列を作る */
export function teamUnits(team: (string | null)[], roster: Record<string, OwnedChar>): UnitSetup[] {
  return team.flatMap((id, slot) => (id && roster[id] ? [allyUnit(id, roster[id], slot)] : []));
}

export function enemyUnits(enemies: (string | null)[], level: number): UnitSetup[] {
  return enemies.flatMap((id, slot) => {
    if (!id) return [];
    const e = ENEMY_BY_ID[id];
    if (!e) throw new Error(`unknown enemy: ${id}`);
    return [
      {
        refId: id,
        name: e.name,
        element: e.element,
        role: e.role,
        stats: enemyStats(e.role, level, e.statMod),
        skill: e.skill,
        slot,
      },
    ];
  });
}
