// 価格差リストの設定。金額はすべて円
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = __dirname;
export const DATA_DIR = path.join(ROOT, "data");
// 海外相場は toreca の取得処理が書き出すものを使う
export const OVERSEAS_CARDS = path.join(ROOT, "..", "toreca", "data", "raw", "cards.json");
export const OVERSEAS_FX = path.join(ROOT, "..", "toreca", "data", "raw", "fx.json");

export const USER_AGENT = "pokeca-arbitrage-list/0.1 (personal project; contact: iq87jun@gmail.com)";

// 楽天市場商品検索API(pokeca/ と同じ。アプリIDは RAKUTEN_APP_ID を共用)
export const RAKUTEN_API = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601";
export const HITS_PER_CARD = 30;
// 楽天APIのレート制限(1秒1回)を守る間隔
export const REQUEST_INTERVAL_MS = 1200;

// 調べるカード: 海外相場の円換算がこれ以上のものを高い順に最大 MAX_CARDS 枚
export const MIN_OVERSEAS_JPY = 3000;
export const MAX_CARDS = 200;

export const SETTINGS = {
  // 海外での売却手数料(eBay の落札手数料+決済手数料の目安)
  sellFeeRate: 0.15,
  // 為替の目減り(受け取り時の両替手数料・相場の動きの余裕)
  fxHaircut: 0.03,
  // 1枚あたりの国際送料と梱包(追跡つき小形包装物の目安)
  intlShipping: 1500,
  // 国内の出品が送料別のときに足す送料
  domesticShipping: 300,
  // これ未満の国内出品はノイズ(ストレージ等)とみなす
  minListingJpy: 500,
  // リストに載せる条件
  minProfitJpy: 1000,
  minProfitRate: 10,
};

// レポートに載せる最大行数
export const MAX_ROWS = 30;
