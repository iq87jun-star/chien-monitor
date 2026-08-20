// 遊戯王海外相場モニター パイプライン設定
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = path.resolve(__dirname, "..");
export const RAW_DIR = path.join(ROOT, "data", "raw");
export const SITE_DIR = path.join(ROOT, "data", "site");
export const CONTENT_DIR = path.join(ROOT, "content");

export const USER_AGENT =
  "duel-kaigai-monitor/0.1 (personal project; contact: iq87jun@gmail.com)";

// YGOPRODeck: キー不要の公開API。全カードのCardmarket(EUR)/TCGplayer(USD)価格を持つ
export const YGO_API = "https://db.ygoprodeck.com/api/v7/cardinfo.php";

// 為替(ECB公表レート・キー不要)。EUR/USD建て価格の円換算に使う
export const FX_URL = "https://api.frankfurter.dev/v1/latest?base=EUR&symbols=JPY,USD";

// 価格履歴を保持する最低価格(EUR)。バルクカードを除外してデータ量を抑える
export const MIN_TRACK_EUR = 0.3;

// 騰落ランキングの最低価格(EUR)。少額カードの変動率ノイズを除外する
export const MIN_RANKING_EUR = 2;

// 騰落率の計算窓(7日)と履歴の保持期間(30日)
export const CHANGE_WINDOW_DAYS = 7;
export const HISTORY_KEEP_DAYS = 30;

// 変動率がこの閾値(%)を超えるカードがあれば「大きな変化あり」と判定
export const SIGNIFICANT_CHANGE_PCT = 25;

// 記事の最大保持件数
export const MAX_ARTICLES = 30;
