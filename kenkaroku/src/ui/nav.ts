import { create } from "zustand";
import type { BattleResult } from "../core/battle/types";
import type { StageRewards } from "../core/game";

export type Tab = "home" | "team" | "chars" | "gacha" | "quest";

export interface BattleView {
  title: string;
  result: BattleResult;
  rewards?: StageRewards | null;
  shards?: { charId: string; amount: number };
}

export type Overlay =
  | { kind: "char"; id: string }
  | { kind: "battle"; view: BattleView }
  | { kind: "settings" }
  | null;

interface NavState {
  tab: Tab;
  overlay: Overlay;
  go(tab: Tab): void;
  open(o: Overlay): void;
  close(): void;
}

export const useNav = create<NavState>((set) => ({
  tab: "home",
  overlay: null,
  go: (tab) => set({ tab, overlay: null }),
  open: (overlay) => set({ overlay }),
  close: () => set({ overlay: null }),
}));
