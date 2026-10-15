import { useEffect, useState } from "react";
import { allyUnit } from "../core/battle/setup";
import { power } from "../core/stats";
import type { SaveData } from "../core/game";

/** 一定間隔で現在時刻を返す（放置報酬の表示更新用） */
export function useNow(intervalMs = 1000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

export function usePrefersReducedMotion(): boolean {
  const [r, setR] = useState(() => typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches);
  useEffect(() => {
    if (typeof matchMedia === "undefined") return;
    const m = matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setR(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return r;
}

export function charPower(save: SaveData, id: string): number {
  const o = save.roster[id];
  return o ? power(allyUnit(id, o, 0).stats) : 0;
}

export function teamPower(save: SaveData): number {
  return save.team.reduce((sum, id) => sum + (id ? charPower(save, id) : 0), 0);
}
