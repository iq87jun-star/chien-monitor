// Warframe相場モニター パイプライン設定
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = path.resolve(__dirname, "..");
export const RAW_DIR = path.join(ROOT, "data", "raw");
export const SITE_DIR = path.join(ROOT, "data", "site");
export const CONTENT_DIR = path.join(ROOT, "content");

export const USER_AGENT =
  "warframe-market-monitor/0.1 (personal project; contact: iq87jun@gmail.com)";

// warframe.market: キー不要の公開API。
// 品目一覧はv2、品目別の日次取引統計(90日分)はv1で取得する
export const WFM_ITEMS_URL = "https://api.warframe.market/v2/items";
export const WFM_STATS_URL = (slug) =>
  `https://api.warframe.market/v1/items/${encodeURIComponent(slug)}/statistics`;

// アイコン画像のCDNベース
export const WFM_ASSET_BASE = "https://warframe.market/static/assets/";

// レート制限(約3リクエスト/秒)に収める同時実行数とリクエスト間ディレイ
export const FETCH_CONCURRENCY = 2;
export const REQUEST_DELAY_MS = 350;

// 監視対象: 全プライムセット(自動検出)+ 定番の高額トレード品(アルケイン/Primed MOD)。
// 一覧に存在しないスラッグは自動で読み飛ばす
export const WATCH_EXTRAS = [
  "arcane_energize",
  "arcane_grace",
  "arcane_barrier",
  "arcane_avenger",
  "arcane_velocity",
  "arcane_strike",
  "arcane_guardian",
  "arcane_fury",
  "primed_continuity",
  "primed_flow",
  "primed_reach",
  "primed_sure_footed",
];

// 統計はアイテムごとに直近N日分だけ保持する(騰落率と取引量の計算用)
export const KEEP_DAYS = 10;

// 監視アイテムのうち統計をこれ以上取得できなければ障害とみなし、既存データを保持する
export const MIN_FETCHED_ITEMS = 30;

// 騰落ランキングの最低価格(プラチナ)と直近7日の最低取引数(薄い板のノイズを除外する)
export const MIN_RANKING_PLAT = 10;
export const MIN_VOLUME_7D = 15;

// 騰落率の計算窓(7日)
export const CHANGE_WINDOW_DAYS = 7;

// 変動率がこの閾値(%)を超えるアイテムがあれば「大きな変化あり」と判定
export const SIGNIFICANT_CHANGE_PCT = 15;

// 記事の最大保持件数
export const MAX_ARTICLES = 30;
