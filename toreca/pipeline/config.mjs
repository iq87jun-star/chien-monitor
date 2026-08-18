// トレカ海外相場モニター(ポケカ日本語版) パイプライン設定
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = path.resolve(__dirname, "..");
export const RAW_DIR = path.join(ROOT, "data", "raw");
export const SITE_DIR = path.join(ROOT, "data", "site");
export const CONTENT_DIR = path.join(ROOT, "content");

export const USER_AGENT =
  "toreca-kaigai-monitor/0.1 (personal project; contact: iq87jun@gmail.com)";

// TCGdex: キー不要の公開API。日本語版セットのカード名と
// Cardmarket(欧州最大のトレカ市場)/TCGplayer(米国)の価格が取れる
export const TCGDEX_BASE = "https://api.tcgdex.net/v2/ja";

// 為替(ECB公表レート・キー不要)。EUR建て価格の円換算に使う
export const FX_URL = "https://api.frankfurter.dev/v1/latest?base=EUR&symbols=JPY,USD";

// 監視対象: セット一覧の末尾(新しい順)から候補を取り、
// 「発売済みかつCardmarket価格が付いている」直近Nセットを選ぶ
// (最新セットは価格マッピングが数週間〜数ヶ月遅れるため候補は広めに取る)
export const SET_CANDIDATES = 14; // 一覧末尾から候補にする数
export const MONITOR_SETS = 4; // 実際に監視するセット数(1セット150〜250枚)
export const PROBE_CARDS = 6; // 価格の有無を確かめるためにセットから試し取りする枚数

// カード取得の同時リクエスト数(CDN相手でも行儀よく)
export const FETCH_CONCURRENCY = 6;

// 騰落ランキングの最低価格(EUR)。少額カードの変動率ノイズを除外する
export const MIN_RANKING_EUR = 2;

// 変動率がこの閾値(%)を超えるカードがあれば「大きな変化あり」と判定
export const SIGNIFICANT_CHANGE_PCT = 25;

// 記事の最大保持件数
export const MAX_ARTICLES = 30;
