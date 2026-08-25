// 限定コスメ相場モニター パイプライン設定
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = path.resolve(__dirname, "..");
export const RAW_DIR = path.join(ROOT, "data", "raw");
export const SITE_DIR = path.join(ROOT, "data", "site");
export const CONTENT_DIR = path.join(ROOT, "content");

export const USER_AGENT =
  "cosme-souba-monitor/0.1 (personal project; contact: iq87jun@gmail.com)";

// 楽天市場商品検索API(要アプリID・無料)。ウォッチリストの各アイテムを検索し
// 出品価格の分布(最安・中央値・件数)を記録する
export const RAKUTEN_API =
  "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601";

// 楽天ジャンル「美容・コスメ・香水」。検索ノイズ(関係ない雑貨等)を減らす
export const RAKUTEN_GENRE_BEAUTY = "100939";

// 1アイテムあたり取得する出品数(価格分布のサンプル)。APIの1ページ上限は30
export const HITS_PER_ITEM = 30;

// 楽天APIのレート制限(1req/秒)を守るためのリクエスト間隔
export const REQUEST_INTERVAL_MS = 1200;

// 出品タイトルにこれらを含むものは価格集計から除外する(相場のノイズ源)
export const NG_WORDS =
  /空箱|箱のみ|サンプル|試供品|お試し|小分け|量り売り|ムエット|テスター|ポーチのみ|ショッパー|紙袋|袋のみ/;

// この価格未満の出品はノイズ(付属品・ミニサイズ等)とみなして除外する(円)
export const MIN_LISTING_JPY = 500;

// 騰落ランキングの最低価格(円)。少額品の変動率ノイズを除外する
export const MIN_RANKING_JPY = 1000;

// 「出品僅少」とみなす出品件数の上限
export const SCARCE_MAX_COUNT = 3;

// 騰落率の計算窓(7日)と履歴の保持期間(60日)
export const CHANGE_WINDOW_DAYS = 7;
export const HISTORY_KEEP_DAYS = 60;

// 変動率がこの閾値(%)を超えるアイテムがあれば「大きな変化あり」と判定
export const SIGNIFICANT_CHANGE_PCT = 20;

// 記事の最大保持件数
export const MAX_ARTICLES = 30;
