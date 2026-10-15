import type { Element } from "../core/types";

export interface StageDef {
  id: string; // "1-1"
  index: number; // 0始まりの通し番号
  chapter: number;
  name: string;
  enemyLevel: number;
  recommendedLevel: number;
  /** 5枠：0,1=前列 2,3,4=後列。null は空き */
  enemies: (string | null)[];
  gold: number;
  /** 初回クリア報酬の花玉 */
  firstGems: number;
  boss?: boolean;
}

export const CHAPTERS = [
  { no: 1, title: "城下の鬼火", lead: "城下町に夜な夜な鬼火が灯る。新任の軍師として、まずは足元を固めよう。" },
  { no: 2, title: "霧の山路", lead: "鬼火の出どころは北の山。霧の中に、妖たちの気配が濃くなっていく。" },
  { no: 3, title: "酒呑の宴", lead: "山頂の城で酒呑が宴を開いている。百鬼の夜を終わらせるときだ。" },
];

const NAMES: string[][] = [
  ["提灯横丁", "裏路地の影", "古井戸", "夜鳴き橋", "瓦屋根の上", "朱塗りの鳥居", "火の見櫓", "川辺の葦原", "焼け寺", "鬼火の辻"],
  ["霧の入口", "杉並木", "天狗の腰掛け", "滝つぼ", "吊り橋", "苔むす石段", "山寺の門", "土蜘蛛の洞", "雪の峠", "茨の砦"],
  ["鬼の関所", "髑髏の野", "燃える竹林", "骸の古戦場", "百足坂", "血の池", "大手門", "天守への階", "宴の間", "酒呑童子の座"],
];

// 各ステージの敵配置（5枠：0,1=前列 2,3,4=後列）
const _ = null;
const LAYOUTS: (string | null)[][][] = [
  [
    ["kooni", "kooni", _, _, _],
    ["kooni", "kooni", "kappa", _, _],
    ["kooni", "kappa", "kooni", _, _],
    ["akaoni", "kooni", "kappa", _, _],
    ["akaoni", "aooni", "kooni", _, "kooni"],
    ["aooni", "kooni", "kappa", "kappa", _],
    ["akaoni", "aooni", "kappa", _, "kooni"],
    ["aooni", "akaoni", "kappa", "kooni", "kooni"],
    ["akaoni", "akaoni", "kappa", "kappa", "kooni"],
    ["aooni", "akaoni", "omukade", "kappa", _],
  ],
  [
    ["tsuchigumo", "kamaitachi", "kamaitachi", _, _],
    ["tsuchigumo", "kamaitachi", "tengu", _, _],
    ["kappa", "tsuchigumo", "yukinba", "kamaitachi", _],
    ["tsuchigumo", "hitotsume", "tengu", "kamaitachi", _],
    ["tsuchigumo", "aooni", "yukinba", "tengu", _],
    ["hitotsume", "tsuchigumo", "kamaitachi", "kamaitachi", "tengu"],
    ["tsuchigumo", "tsuchigumo", "yukinba", "yukinba", "tengu"],
    ["hitotsume", "hitotsume", "tengu", "kamaitachi", "yukinba"],
    ["tsuchigumo", "hitotsume", "tengu", "tengu", "yukinba"],
    ["tsuchigumo", "hitotsume", "ibaraki", "kamaitachi", "tengu"],
  ],
  [
    ["akaoni", "aooni", "kasha", "kasha", _],
    ["gashamusha", "akaoni", "kasha", "kasha", _],
    ["gashamusha", "aooni", "kasha", "tengu", "kasha"],
    ["gashamusha", "gashamusha", "kasha", "yukinba", "tengu"],
    ["omukade", "gashamusha", "kasha", "kasha", "tengu"],
    ["hitotsume", "gashamusha", "kasha", "yukinba", "kasha"],
    ["omukade", "hitotsume", "kasha", "tengu", "yukinba"],
    ["gashamusha", "omukade", "kasha", "kasha", "kasha"],
    ["omukade", "omukade", "ibaraki", "tengu", "kasha"],
    ["gashamusha", "gashamusha", "shuten", "ibaraki", "kasha"],
  ],
];

// 敵レベルは初期編成での勝率シミュレーションから調整した値（推奨Lvで8割勝てる目安）
const LEVELS = [
  [3, 3, 5, 6, 10, 12, 13, 14, 22, 18],
  [30, 34, 34, 37, 24, 38, 34, 52, 46, 45],
  [45, 50, 38, 36, 55, 57, 90, 63, 85, 49],
];

/** 推奨レベル（表示用） */
const RECOMMENDED = [
  [1, 1, 2, 3, 5, 7, 9, 11, 13, 16],
  [18, 20, 22, 24, 27, 30, 33, 36, 39, 43],
  [46, 50, 54, 58, 62, 66, 70, 75, 80, 88],
];

function buildStage(chapter: number, num: number): StageDef {
  const index = (chapter - 1) * 10 + (num - 1);
  const boss = num === 10;
  return {
    id: `${chapter}-${num}`,
    index,
    chapter,
    name: NAMES[chapter - 1][num - 1],
    enemyLevel: LEVELS[chapter - 1][num - 1],
    recommendedLevel: RECOMMENDED[chapter - 1][num - 1],
    enemies: LAYOUTS[chapter - 1][num - 1],
    gold: 200 + index * 60,
    firstGems: boss ? 300 : 50,
    boss,
  };
}

export const STAGES: StageDef[] = [];
for (let ch = 1; ch <= 3; ch++) for (let n = 1; n <= 10; n++) STAGES.push(buildStage(ch, n));

/** 開花任務（星上げ専用）：属性ごとの試練 */
export interface TrialDef {
  element: Element;
  name: string;
  enemies: (string | null)[];
}

export const TRIALS: TrialDef[] = [
  { element: "fire", name: "炎華の試練", enemies: ["akaoni", "akaoni", "kasha", null, "kasha"] },
  { element: "water", name: "潮華の試練", enemies: ["kappa", "aooni", "yukinba", "yukinba", null] },
  { element: "wind", name: "嵐華の試練", enemies: ["kamaitachi", "kamaitachi", "tengu", null, "tengu"] },
  { element: "rock", name: "岩華の試練", enemies: ["tsuchigumo", "hitotsume", "gashamusha", null, "gashamusha"] },
];

/** 開花任務の難度：要求クリア段数・敵レベル・報酬花片 */
export const TRIAL_LEVELS = [
  { level: 1, requireStage: 3, enemyLevel: 6, shards: 5 },
  { level: 2, requireStage: 8, enemyLevel: 16, shards: 8 },
  { level: 3, requireStage: 14, enemyLevel: 30, shards: 12 },
  { level: 4, requireStage: 20, enemyLevel: 44, shards: 16 },
  { level: 5, requireStage: 26, enemyLevel: 58, shards: 20 },
];

export const TRIAL_DAILY_LIMIT = 3;
