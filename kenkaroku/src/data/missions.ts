// 初心者任務。条件はセーブデータの集計値で判定する（判定は core/missions.ts）

export type MissionCond =
  | { type: "stageCleared"; n: number } // クリア済みステージ数
  | { type: "pulls"; n: number } // 花結びの累計回数
  | { type: "maxLevel"; n: number } // 所持剣華の最高レベル
  | { type: "blooms"; n: number } // 開花の累計回数
  | { type: "teamSize"; n: number } // 編成人数
  | { type: "idleClaims"; n: number } // 放置報酬の受け取り回数
  | { type: "trials"; n: number } // 開花任務の挑戦回数
  | { type: "owned"; n: number }; // 所持剣華数

export interface MissionDef {
  id: string;
  title: string;
  cond: MissionCond;
  reward: { gems?: number; gold?: number };
}

export const BEGINNER_MISSIONS: MissionDef[] = [
  { id: "b01", title: "五人の剣華で編成を組む", cond: { type: "teamSize", n: 5 }, reward: { gems: 100 } },
  { id: "b02", title: "ステージ1-1を突破する", cond: { type: "stageCleared", n: 1 }, reward: { gems: 100, gold: 1000 } },
  { id: "b03", title: "放置報酬を受け取る", cond: { type: "idleClaims", n: 1 }, reward: { gold: 2000 } },
  { id: "b04", title: "花結びを1回行う", cond: { type: "pulls", n: 1 }, reward: { gems: 150 } },
  { id: "b05", title: "剣華をLv.10まで育てる", cond: { type: "maxLevel", n: 10 }, reward: { gems: 150, gold: 2000 } },
  { id: "b06", title: "ステージ1-5を突破する", cond: { type: "stageCleared", n: 5 }, reward: { gems: 300 } },
  { id: "b07", title: "開花任務に挑む", cond: { type: "trials", n: 1 }, reward: { gems: 150 } },
  { id: "b08", title: "剣華を1回開花させる", cond: { type: "blooms", n: 1 }, reward: { gems: 300 } },
  { id: "b09", title: "花結びを累計10回行う", cond: { type: "pulls", n: 10 }, reward: { gems: 500 } },
  { id: "b10", title: "剣華を8人集める", cond: { type: "owned", n: 8 }, reward: { gems: 500 } },
  { id: "b11", title: "剣華をLv.30まで育てる", cond: { type: "maxLevel", n: 30 }, reward: { gems: 500, gold: 10000 } },
  { id: "b12", title: "第一章を踏破する（1-10）", cond: { type: "stageCleared", n: 10 }, reward: { gems: 1500 } },
];
