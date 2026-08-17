// タルコフ相場モニター パイプライン設定
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = path.resolve(__dirname, "..");
export const RAW_DIR = path.join(ROOT, "data", "raw");
export const SITE_DIR = path.join(ROOT, "data", "site");
export const CONTENT_DIR = path.join(ROOT, "content");

// tarkov.devのAPI利用マナー: 説明的なUser-Agentを送る
export const USER_AGENT =
  "game-market-monitor/0.1 (contact: iq87jun@gmail.com)";

// tarkov.dev の公開GraphQLエンドポイント
export const TARKOV_GRAPHQL = "https://api.tarkov.dev/graphql";

// アイテム相場クエリ(lang: ja で日本語アイテム名を取得)
export const ITEMS_QUERY =
  "{items(lang: ja){id name shortName avg24hPrice changeLast48hPercent basePrice iconLink types}}";

// 騰落ランキングの対象とする最低価格(₽)。安値アイテムの変動率ノイズを除外する
export const MIN_RANKING_PRICE = 10000;

// 変動率がこの閾値(%)を超えるアイテムがあれば「大きな変化あり」と判定
export const SIGNIFICANT_CHANGE_PCT = 20;

// 記事の最大保持件数
export const MAX_ARTICLES = 30;
