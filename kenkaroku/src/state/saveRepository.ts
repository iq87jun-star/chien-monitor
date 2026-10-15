import type { SaveData } from "../core/game";

/** 保存先の抽象。将来サーバー同期に差し替えられるようにしておく */
export interface SaveRepository {
  load(): unknown | null;
  save(data: SaveData): void;
  clear(): void;
}

export const STORAGE_KEY = "kenkaroku.save";

export class LocalStorageSaveRepository implements SaveRepository {
  constructor(private key = STORAGE_KEY) {}

  load(): unknown | null {
    try {
      const raw = localStorage.getItem(this.key);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  save(data: SaveData): void {
    try {
      localStorage.setItem(this.key, JSON.stringify(data));
    } catch {
      // 容量超過やプライベートモードでは保存できないが、遊ぶことはできる
    }
  }

  clear(): void {
    try {
      localStorage.removeItem(this.key);
    } catch {
      /* noop */
    }
  }
}

/** テストやサーバー同期前の確認用 */
export class MemorySaveRepository implements SaveRepository {
  data: unknown | null = null;
  load() {
    return this.data;
  }
  save(d: SaveData) {
    this.data = JSON.parse(JSON.stringify(d));
  }
  clear() {
    this.data = null;
  }
}
