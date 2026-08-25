// CS2スキン相場モニター パイプライン設定
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = path.resolve(__dirname, "..");
export const RAW_DIR = path.join(ROOT, "data", "raw");
export const SITE_DIR = path.join(ROOT, "data", "site");
export const CONTENT_DIR = path.join(ROOT, "content");

export const USER_AGENT =
  "cs2-skin-market-monitor/0.1 (personal project; contact: iq87jun@gmail.com)";

// Skinport: キー不要の公開API。CS2全スキンの出品価格(最安値・中央値・出品数)を
// 1リクエストで取得できる。レスポンスは5分キャッシュ・レート制限は8リクエスト/5分
export const SKINPORT_ITEMS_URL = "https://api.skinport.com/v1/items?app_id=730&currency=USD";

// 為替(ECB公表レート・キー不要)。USD建て価格の円換算に使う
export const FX_URL = "https://api.frankfurter.dev/v1/latest?base=USD&symbols=JPY,EUR";

// 価格履歴を保持する最低価格(USD)・最低出品数。少額スキンや板の無いスキンを
// 除外してデータ量を抑える(この条件でも約1万スキンを追跡できる)
export const MIN_TRACK_USD = 5;
export const MIN_TRACK_QTY = 2;

// 騰落ランキングの最低価格(USD)と最低出品数(薄い板の変動率ノイズを除外する)
export const MIN_RANKING_USD = 5;
export const MIN_RANKING_QTY = 3;

// 騰落率の計算窓(7日)と履歴の保持期間(30日)
export const CHANGE_WINDOW_DAYS = 7;
export const HISTORY_KEEP_DAYS = 30;

// 変動率がこの閾値(%)を超えるスキンがあれば「大きな変化あり」と判定
export const SIGNIFICANT_CHANGE_PCT = 20;

// 記事の最大保持件数
export const MAX_ARTICLES = 30;
