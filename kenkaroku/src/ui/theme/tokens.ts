// デザイントークン。色・余白・角丸・影・フォントはここだけで定義し、
// 起動時に CSS 変数（--k-*）として流し込む。コンポーネントは var(--k-*) か TOKENS 経由で参照する。
import type { Element, Rarity } from "../../core/types";

export const TOKENS = {
  color: {
    sumi: "#0e0b0a", // 墨：背景
    sumi2: "#17110e",
    urushi: "#1f1512", // 漆：パネル
    urushiHi: "#2c1e19",
    urushiLine: "#3d2a22",
    kin: "#d6b25e", // 金箔
    kinLight: "#f2dc94",
    kinDeep: "#8f6f2c",
    shu: "#d4462c", // 朱
    shuDeep: "#8e2617",
    washi: "#f3ead8", // 和紙：文字
    washiDim: "#bcae96",
    washiFaint: "#7f7262",
    ok: "#7fbf7a",
    danger: "#e0604a",
    hp: "#7fcf6a",
    hpEnemy: "#e0604a",
    energy: "#e9c64f",
    shield: "#9fd3ff",
  },
  element: {
    fire: "#e2543a",
    water: "#3f9fd0",
    wind: "#4fb08a",
    rock: "#b48c4c",
  } satisfies Record<Element, string>,
  rarity: {
    SR: "#5b8fd9", // 青
    SSR: "#a46ad8", // 紫
    UR: "#e3b34a", // 金
  } satisfies Record<Rarity, string>,
  time: {
    morning: { top: "#3a2b3f", bottom: "#c98a5c", glow: "#ffd9a0" },
    day: { top: "#1d2b3a", bottom: "#4a6a7a", glow: "#f3ead8" },
    night: { top: "#07060c", bottom: "#1c1220", glow: "#e9a04a" },
  },
  space: { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 },
  radius: { sm: 6, md: 10, lg: 16, pill: 999 },
  shadow: {
    panel: "0 1px 0 rgba(255,255,255,.04) inset, 0 6px 20px rgba(0,0,0,.45)",
    glow: "0 0 0 1px rgba(214,178,94,.5), 0 0 18px rgba(214,178,94,.35)",
    text: "0 1px 2px rgba(0,0,0,.8)",
  },
  font: {
    brush: "'Yuji Syuku', 'Hiragino Mincho ProN', 'Yu Mincho', serif",
    body: "'Zen Kaku Gothic New', 'Hiragino Sans', 'Noto Sans JP', sans-serif",
  },
  layout: { maxWidth: 540, navHeight: 64 },
  motion: { fast: "120ms", base: "220ms", slow: "480ms", ease: "cubic-bezier(.2,.8,.2,1)" },
} as const;

export const elementColor = (e: Element) => TOKENS.element[e];
export const rarityColor = (r: Rarity) => TOKENS.rarity[r];

/** TOKENS を CSS 変数に変換して :root に設定する */
export function applyTokens(root: HTMLElement = document.documentElement) {
  const set = (k: string, v: string | number) => root.style.setProperty(`--k-${k}`, typeof v === "number" ? `${v}px` : v);
  for (const [k, v] of Object.entries(TOKENS.color)) set(k, v);
  for (const [k, v] of Object.entries(TOKENS.element)) set(`el-${k}`, v);
  for (const [k, v] of Object.entries(TOKENS.rarity)) set(`r-${k}`, v);
  for (const [k, v] of Object.entries(TOKENS.space)) set(`sp-${k}`, v);
  for (const [k, v] of Object.entries(TOKENS.radius)) set(`rad-${k}`, v);
  for (const [k, v] of Object.entries(TOKENS.shadow)) set(`sh-${k}`, v);
  for (const [k, v] of Object.entries(TOKENS.motion)) set(`m-${k}`, v);
  set("font-brush", TOKENS.font.brush);
  set("font-body", TOKENS.font.body);
  set("max-w", TOKENS.layout.maxWidth);
  set("nav-h", TOKENS.layout.navHeight);
}
