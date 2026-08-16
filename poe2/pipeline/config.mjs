// PoE2メタ・経済統計サイト パイプライン設定
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = path.resolve(__dirname, "..");
export const RAW_DIR = path.join(ROOT, "data", "raw");
export const SITE_DIR = path.join(ROOT, "data", "site");
export const CONTENT_DIR = path.join(ROOT, "content");

// poe.ninjaのAPI利用ガイドライン: 説明的なUser-Agentを送る・キャッシュ(約5分)を尊重する
export const USER_AGENT =
  "poe2-jp-meta-monitor/0.1 (personal project; contact: iq87jun@gmail.com)";

export const NINJA_BASE = "https://poe.ninja/poe2/api/economy";

// ユニークアイテムのカテゴリ(poe.ninjaのstash item overviewのtype)
export const UNIQUE_TYPES = [
  "UniqueWeapons",
  "UniqueArmours",
  "UniqueAccessories",
  "UniqueJewels",
];

// Path of Exile 2 のSteam AppID(Steam News API用)
export const STEAM_APPID = 2694490;

// 変動率がこの閾値(%)を超えるアイテムがあれば「大きな変化あり」と判定
export const SIGNIFICANT_CHANGE_PCT = 15;

// 記事の最大保持件数
export const MAX_ARTICLES = 30;
