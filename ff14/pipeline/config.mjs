// FF14マーケットモニター パイプライン設定
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = path.resolve(__dirname, "..");
export const DATA_DIR = path.join(ROOT, "data");
export const RAW_DIR = path.join(DATA_DIR, "raw");
export const SITE_DIR = path.join(DATA_DIR, "site");
export const CONTENT_DIR = path.join(ROOT, "content");

// UniversalisのAPI利用マナー: 説明的なUser-Agentを送る・リクエスト数は最小限にする
export const USER_AGENT =
  "game-market-monitor/0.1 (contact: iq87jun@gmail.com)";

export const UNIVERSALIS_BASE = "https://universalis.app/api/v2";

// 集計対象リージョン(日本DC統合)
export const REGION = "Japan";

// 集計APIは1リクエストあたり最大100アイテムまで
export const BATCH_SIZE = 100;

// 価格履歴の保持期間(7日) — change7d の計算窓
export const HISTORY_WINDOW_MS = 7 * 24 * 3600e3;

// 変動率がこの閾値(%)を超えるアイテムがあれば「大きな変化あり」と判定
export const SIGNIFICANT_CHANGE_PCT = 10;

// 記事の最大保持件数
export const MAX_ARTICLES = 30;
