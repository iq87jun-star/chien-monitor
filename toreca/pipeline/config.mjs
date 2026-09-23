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

// 監視対象: セット一覧の末尾から候補を取り、発売日の新しい順に並べて
// 「発売済みかつCardmarket価格が付いている」直近Nセットを選ぶ
// (一覧APIの末尾は発売順とは限らないため、発売日で並べ直してから選ぶ)
// (最新セットは価格マッピングが数週間〜数ヶ月遅れるため候補は広めに取る)
export const SET_CANDIDATES = 14; // 一覧末尾から候補にする数
export const MONITOR_SETS = 6; // 自動選択する直近セット数(1セット100〜250枚)

// 自動選択の直近セットに加えて常に監視する人気セット(TCGdexのセットID)。
// ブラウザ拡張でフリマ出品と照合する対象を広げるため、出品・取引の多い旧セットを入れている。
// 価格が付いているカードだけが集計されるので、価格マッピングが無いセットを入れても害はない。
// (イーブイヒーローズ S6a・シャイニースターV S4a はTCGdexにカードデータが無く対象外)
export const EXTRA_SETS = [
  "SV2a", // ポケモンカード151
  "S12a", // VSTARユニバース
  "SV4a", // シャイニートレジャーex
  "SV8a", // テラスタルフェスex
  "S8b", // VMAXクライマックス
  "SM12a", // タッグオールスターズ
  "S10a", // ダークファンタズマ
  "S11a", // 白熱のアルカナ
  "SV6a", // ナイトワンダラー
  "SV7a", // 楽園ドラゴーナ
  "SV5a", // クリムゾンヘイズ
  "SV2D", // クレイバースト
  "SV3", // 黒炎の支配者
  "SV1a", // トリプレットビート
  "M2a", // MEGAドリームex
  "SV-P", // スカーレット&バイオレット プロモカード
  "M-P", // メガ プロモカード
];

// TCGdex側のセット名が誤っているものの補正(セット名はサイト表示と拡張の絞り込みに使う)
export const SET_NAME_OVERRIDES = {
  SV4a: "シャイニートレジャーex", // TCGdexでは「レイジングサーフ」(SV3a の名前)になっている
};
export const PROBE_CARDS = 6; // 価格の有無を確かめるためにセットから試し取りする枚数

// カード取得の同時リクエスト数(CDN相手でも行儀よく)
export const FETCH_CONCURRENCY = 6;

// 騰落ランキングの最低価格(EUR)。少額カードの変動率ノイズを除外する
export const MIN_RANKING_EUR = 2;

// 変動率がこの閾値(%)を超えるカードがあれば「大きな変化あり」と判定
export const SIGNIFICANT_CHANGE_PCT = 25;

// 記事の最大保持件数
export const MAX_ARTICLES = 30;
