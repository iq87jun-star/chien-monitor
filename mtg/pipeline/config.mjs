// MTG海外相場モニター パイプライン設定
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = path.resolve(__dirname, "..");
export const RAW_DIR = path.join(ROOT, "data", "raw");
export const SITE_DIR = path.join(ROOT, "data", "site");
export const CONTENT_DIR = path.join(ROOT, "content");

export const USER_AGENT =
  "mtg-kaigai-monitor/0.1 (personal project; contact: iq87jun@gmail.com)";

// Scryfall: キー不要の公開API。全カードのTCGplayer(USD)/Cardmarket(EUR)価格を持つ
export const SCRYFALL_BASE = "https://api.scryfall.com";

// Scryfallのお願い(50〜100ms間隔)に従うリクエスト間ディレイ
export const REQUEST_DELAY_MS = 120;

// 為替(ECB公表レート・キー不要)。USD建て価格の円換算に使う
export const FX_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=JPY,EUR";

// 監視対象: 紙で発売済みの直近Nセット(エキスパンション等)を新しい順に選ぶ
export const MONITOR_SETS = 4;
export const SET_CANDIDATES = 12; // 候補として見るセット数(価格未整備のセットを飛ばすため広めに)
export const MONITOR_SET_TYPES = ["expansion", "core", "masters", "draft_innovation", "commander"];
export const MIN_PRICED_CARDS = 10; // これ未満しか価格が付いていないセットは監視対象外

// 価格履歴を保持する最低価格(USD)。バルクカードを除外してデータ量を抑える
export const MIN_TRACK_USD = 0.5;

// 騰落ランキングの最低価格(USD)。少額カードの変動率ノイズを除外する
export const MIN_RANKING_USD = 2;

// 騰落率の計算窓(7日)と履歴の保持期間(30日)
export const CHANGE_WINDOW_DAYS = 7;
export const HISTORY_KEEP_DAYS = 30;

// 変動率がこの閾値(%)を超えるカードがあれば「大きな変化あり」と判定
export const SIGNIFICANT_CHANGE_PCT = 25;

// 記事の最大保持件数
export const MAX_ARTICLES = 30;
