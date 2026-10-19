// 中古ドメイン発掘パイプライン設定
// 自社サイト(7サイト目以降)用に、テーマが一致し・過去に運用歴があり・
// 現在未登録のドメインを発掘してスコアリングする。pocketduel.tokyo実験の体系化。
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export const ROOT = path.resolve(__dirname, "..");
export const RAW_DIR = path.join(ROOT, "data", "raw");
export const SITE_DIR = path.join(ROOT, "data", "site");
export const INPUT_DIR = path.join(ROOT, "input");

export const USER_AGENT =
  "chien-domain-scout/0.1 (personal project; contact: iq87jun@gmail.com)";

// DNS over HTTPS(キー不要)。NSレコードの有無で「登録済み」を一次判定する
export const DOH_URL = "https://cloudflare-dns.com/dns-query";

// RDAP(キー不要)。gTLD(.com/.net/.tokyo等)の未登録確認。404=未登録
export const RDAP_URL = "https://rdap.org/domain/";

// JPRS whois(port 43)。.jpの未登録確認。"No match!!"=未登録
export const JPRS_WHOIS_HOST = "whois.jprs.jp";

// Wayback Machine CDX API(キー不要)。過去の運用歴(=中古度)の確認
export const WAYBACK_CDX = "https://web.archive.org/cdx/search/cdx";

// Open PageRank(無料APIキー・任意)。被リンク由来のドメインランク(0〜10)
// Secrets/環境変数 OPR_API_KEY を設定した時だけ有効
export const OPR_URL = "https://openpagerank.com/api/v1.0/getPageRank";

// ジャンルプロファイル。ジャンルごとに「シードURL」と「一致キーワード」を持ち、
// レポートでもジャンル別に表示される。新ジャンルはここにブロックを足すだけで増やせる。
//   seeds    … リンク切れ発掘の対象ページ(古い外部リンクを多く含むページ)。
//              Waybackの過去版(web.archive.org/web/<年>/<URL>)をシードにすると、
//              当時貼られていて今は失効したリンク先(=被リンク付き中古の有力候補)が拾える
//   keywords … ドメイン名に含まれるとニッチ一致でスコア加点(ローマ字部分一致)
// トレカ・ゲーム系シード
const SEED_URLS_TCG = [
  "https://ja.wikipedia.org/wiki/%E9%81%8A%E6%88%AF%E7%8E%8B%E3%82%AA%E3%83%95%E3%82%A3%E3%82%B7%E3%83%A3%E3%83%AB%E3%82%AB%E3%83%BC%E3%83%89%E3%82%B2%E3%83%BC%E3%83%A0", // 遊戯王OCG
  "https://ja.wikipedia.org/wiki/%E3%83%9D%E3%82%B1%E3%83%A2%E3%83%B3%E3%82%AB%E3%83%BC%E3%83%89%E3%82%B2%E3%83%BC%E3%83%A0", // ポケモンカードゲーム
  "https://ja.wikipedia.org/wiki/%E3%83%88%E3%83%AC%E3%83%BC%E3%83%87%E3%82%A3%E3%83%B3%E3%82%B0%E3%82%AB%E3%83%BC%E3%83%89%E3%82%B2%E3%83%BC%E3%83%A0", // TCG総論
  "https://ja.wikipedia.org/wiki/%E3%83%95%E3%82%A1%E3%82%A4%E3%83%8A%E3%83%AB%E3%83%95%E3%82%A1%E3%83%B3%E3%82%BF%E3%82%B8%E3%83%BCXIV", // FF14
  "https://en.wikipedia.org/wiki/Path_of_Exile",
  "https://ja.wikipedia.org/wiki/Escape_from_Tarkov",
  // 過去版(2016〜2017年頃): 古い外部リンク・公認ショップ・ファンサイト等が残っている
  "https://web.archive.org/web/2016/https://ja.wikipedia.org/wiki/%E9%81%8A%E6%88%AF%E7%8E%8B%E3%82%AA%E3%83%95%E3%82%A3%E3%82%B7%E3%83%A3%E3%83%AB%E3%82%AB%E3%83%BC%E3%83%89%E3%82%B2%E3%83%BC%E3%83%A0",
  "https://web.archive.org/web/2017/https://ja.wikipedia.org/wiki/%E3%83%9D%E3%82%B1%E3%83%A2%E3%83%B3%E3%82%AB%E3%83%BC%E3%83%89%E3%82%B2%E3%83%BC%E3%83%A0",
  "https://web.archive.org/web/2016/https://ja.wikipedia.org/wiki/%E3%83%88%E3%83%AC%E3%83%BC%E3%83%87%E3%82%A3%E3%83%B3%E3%82%B0%E3%82%AB%E3%83%BC%E3%83%89%E3%82%B2%E3%83%BC%E3%83%A0",
  "https://web.archive.org/web/2016/https://ja.wikipedia.org/wiki/%E3%83%95%E3%82%A1%E3%82%A4%E3%83%8A%E3%83%AB%E3%83%95%E3%82%A1%E3%83%B3%E3%82%BF%E3%82%B8%E3%83%BCXIV",
  // ショップまとめ・アンテナ系(2026-08検証: 店舗・ブログの実ドメインを直リンクで
  // 多数持つページ。閉店マーク付き店舗も含まれる)
  "https://akihabara-bc.jp/akihabara-trading-card-shop/", // 秋葉原トレカ80店舗まとめ(36件)
  "https://esports-ekichika.net/article/osaka-cardshop/", // 大阪カードショップ一覧(16件)
  "https://yugioh-antenna.com/", // 遊戯王ブログアンテナ(11件)
  // 上記の過去版: 現行版で消えた閉店店舗・休止ブログのドメインが残っている
  "https://web.archive.org/web/2022/https://akihabara-bc.jp/akihabara-trading-card-shop/",
  "https://web.archive.org/web/2019/https://yugioh-antenna.com/",
  // FF14個人ブログ一覧の過去版(FF14ブログは2018年前後に大量閉鎖)
  "https://web.archive.org/web/2018/https://ff14.axdx.net/blog.php",
];

// 長野ローカル系シード(2026-08検証: 宿・店舗の実ドメインを直リンクで持つページ)
const SEED_URLS_NAGANO = [
  "https://nozawa.jp/", // 野沢温泉 宿ガイド(宿公式18件)
  "https://www.nagano-sci.or.jp/list/", // 県内商工会一覧(44件)
  "https://www.kisomachi.or.jp/shokokai/sonota/link.html", // 木曽町商工会リンク集(5件)
  // 過去版: 廃業した宿・合併で消えた商工会・移転した店舗のドメインが残っている
  "https://web.archive.org/web/2017/https://nozawa.jp/",
  "https://web.archive.org/web/2016/https://www.nagano-sci.or.jp/list/",
  "https://web.archive.org/web/2016/https://www.kisomachi.or.jp/shokokai/sonota/link.html",
];

export const GENRES = {
  tcg: {
    label: "トレカ・ゲーム",
    keywords: [
      "duel", "card", "cards", "toreca", "tcg", "deck", "poke", "pack",
      "game", "gamer", "ff14", "raid", "loot", "trade", "item",
      "souba", "kakaku", "price", "market", "monitor", "kaigai", "yen",
    ],
    seeds: SEED_URLS_TCG,
  },
  nagano: {
    label: "長野ローカル",
    keywords: [
      "nagano", "shinshu", "hakuba", "nozawa", "kiso", "matsumoto",
      "karuizawa", "azumino", "suwa", "ueda", "iida", "saku", "chino",
      "onsen", "yado", "ryokan", "pension", "minshuku", "soba", "ski",
      "snow", "alps", "kogen",
    ],
    seeds: SEED_URLS_NAGANO,
  },
};

// 候補にしても意味がない定番ドメイン(シード抽出時に除外)
export const EXCLUDE_DOMAINS = new Set([
  "wikipedia.org", "wikimedia.org", "wiktionary.org", "wikidata.org", "mediawiki.org",
  "archive.org", "doi.org", "google.com", "youtube.com", "twitter.com", "x.com",
  "facebook.com", "instagram.com", "amazon.com", "apple.com", "microsoft.com",
]);

// 対象TLDと名前スコアの重み。個人で普通に取得できるTLDのみ
// (co.jp等の属性型JPは法人要件があるため対象外)
export const TLD_WEIGHTS = {
  com: 10,
  jp: 10,
  net: 6,
  org: 5,
  tokyo: 6,
  info: 2,
  biz: 2,
};

// 商標・ブランド語(含まれると大きく減点+要注意フラグ)。
// 転売目的でなくても、公式名そのままのドメインはUDRP/JP-DRPのリスクがある
export const RISK_BRAND_TERMS = [
  "pokemon", "pikachu", "nintendo", "konami", "yugioh", "yu-gi-oh",
  "finalfantasy", "squareenix", "square-enix", "disney", "ghibli",
  "shueisha", "jump",
];

// アダルト・ギャンブル等(過去サイトの履歴汚染リスク。減点+フラグ)
export const RISK_SENSITIVE_TERMS = [
  "casino", "bet", "betting", "porn", "sex", "xxx", "adult",
  "viagra", "loan", "cash", "fx",
];

// 1回の実行で新規チェックする最大数(DoH/RDAP/whoisへの負荷を抑える)
export const MAX_CHECKS_PER_RUN = 150;

// 1回の実行で新規にWayback照会する最大数
export const MAX_ENRICH_PER_RUN = 60;

// 再チェック間隔(日)。登録済みドメインもいずれドロップするため定期的に見直す
export const RECHECK_DAYS = { registered: 30, available: 7, unknown: 1 };

// Wayback照会結果のキャッシュ日数(過去の履歴は変わらないため長め)
export const WAYBACK_CACHE_DAYS = 60;

// 外部APIへの同時リクエスト数
export const CONCURRENCY = 3;
