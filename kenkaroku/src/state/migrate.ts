// セーブデータのバージョン移行。古い形式を読み込んだら順番に変換して最新にする。
import { DEFAULT_SETTINGS, newSave, SAVE_VERSION, type SaveData } from "../core/game";

type AnySave = Record<string, unknown> & { version?: number };

/** version → version+1 への変換 */
const MIGRATIONS: Record<number, (s: AnySave) => AnySave> = {
  // v1：設定項目が無く、所持キャラの花片が別テーブル（shardsById）だった
  1: (s) => {
    const roster = { ...(s.roster as Record<string, { level: number; star: number; shards?: number }>) };
    const shardsById = (s.shardsById as Record<string, number> | undefined) ?? {};
    for (const id of Object.keys(roster)) roster[id] = { ...roster[id], shards: roster[id].shards ?? shardsById[id] ?? 0 };
    const { shardsById: _drop, ...rest } = s;
    void _drop;
    return { ...rest, roster, settings: { ...DEFAULT_SETTINGS }, version: 2 };
  },
};

export function migrate(raw: unknown, now: number): SaveData {
  if (!raw || typeof raw !== "object") return newSave(now);
  let s = raw as AnySave;
  let v = typeof s.version === "number" ? s.version : 1;
  if (v > SAVE_VERSION) {
    // 新しいバージョンのデータ：壊さないよう既定値で補うだけにする
    return { ...newSave(now), ...(s as unknown as SaveData) };
  }
  while (v < SAVE_VERSION) {
    const step = MIGRATIONS[v];
    if (!step) return newSave(now);
    s = step(s);
    v = s.version as number;
  }
  // 欠けている項目は既定値で補完（項目追加に強くする）
  const base = newSave(now);
  const merged = { ...base, ...(s as unknown as SaveData) };
  merged.settings = { ...base.settings, ...merged.settings };
  merged.counters = { ...base.counters, ...merged.counters };
  return merged;
}
