// ビルド後処理: ブラウザ拡張「トレカ海外相場チェッカー」用のワンピースカード価格データを
// dist/api/onepiece.json に書き出す(拡張の v1 形式・ワンピース専用の項目つき)。
// ワンピースカードは日本語版と英語版でカード番号(OP05-119 等)が共通なので、
// 名前ではなくカード番号で出品と照合する。価格は optcgapi.com(キー不要の公開API)の
// TCGplayer 市場価格=英語版カードの米国相場(USD)で、日本語版の相場ではない点に注意。
// 同じカード番号でもパラレル・コミパラ・SP等で価格が大きく違うため、版(variant)ごとに持つ。
// ポケカのサイトに同居させているのは、ワンピース用サイト(opcg/)が未公開のため。
// 取得に失敗してもサイトのビルドは止めない(available:false を書き、拡張は前回キャッシュを使う)。
import fs from "node:fs/promises";
import path from "node:path";
import { ROOT, RAW_DIR, USER_AGENT } from "./config.mjs";

const FORMAT_VERSION = 1;
const OUT_FILE = path.join(ROOT, "dist", "api", "onepiece.json");
const API = "https://optcgapi.com/api";
const ENDPOINTS = ["allSetCards", "allSTCards"]; // ブースター・エクストラ+スタートデッキ

// optcgapi のカード名の括弧書きから版を判定する(判定順が大事: コミパラは「Alternate Art」も含む)
function variantOf(name) {
  if (/\(SP\)/.test(name) && /Gold/.test(name)) return "sp-gold";
  if (/\(SP\)/.test(name)) return "sp";
  if (/\(Manga\)/.test(name)) return "manga";
  if (/Signature/.test(name)) return "signature";
  if (/Wanted Poster/.test(name)) return "wanted";
  if (/\((Alternate Art|Parallel|Full Art)\)/.test(name)) return "parallel";
  if (/\((Pirate Foil|Jolly Roger Foil|Textured Foil|Box Topper|Dash Pack|SPR)\)/.test(name)) {
    return "other";
  }
  return "normal"; // 番号のみ・再録(Reprint)は通常版
}

// 表示用の英語名: 「Monkey.D.Luffy (119) (Alternate Art)」→「Monkey.D.Luffy」
const baseName = (name) => name.replace(/\s*\(.*$/, "").trim();

async function fetchJson(url) {
  const res = await fetch(url, {
    headers: { Accept: "application/json", "User-Agent": USER_AGENT },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.json();
}

async function writeUnavailable(reason) {
  await fs.writeFile(OUT_FILE, JSON.stringify({ v: FORMAT_VERSION, available: false }));
  console.warn(`export-onepiece: ${reason} — wrote available:false`);
}

export async function exportOnePiece() {
  await fs.mkdir(path.dirname(OUT_FILE), { recursive: true });
  let fx;
  try {
    fx = JSON.parse(await fs.readFile(path.join(RAW_DIR, "fx.json"), "utf8"));
  } catch {
    return writeUnavailable("fx.json missing");
  }
  // fx.json は EUR 基準(JPY・USD)なので USD/JPY に換算する
  const usdJpy = fx?.rates?.JPY && fx?.rates?.USD ? fx.rates.JPY / fx.rates.USD : null;
  if (!usdJpy) return writeUnavailable("fx rates missing");

  let raw;
  try {
    raw = (await Promise.all(ENDPOINTS.map((e) => fetchJson(`${API}/${e}/`)))).flat();
  } catch (err) {
    return writeUnavailable(`optcgapi unavailable (${err.message})`);
  }

  // [setId, localId(カード番号), 英語名, 価格(USD), avg7, avg30, 補足, 版]
  const cards = raw
    .filter((c) => c.card_set_id && typeof c.market_price === "number" && c.market_price > 0)
    .map((c) => [
      "",
      c.card_set_id.toUpperCase(),
      baseName(c.card_name),
      c.market_price,
      null,
      null,
      null,
      variantOf(c.card_name),
    ]);
  if (cards.length === 0) return writeUnavailable("no priced cards");

  const out = {
    v: FORMAT_VERSION,
    available: true,
    game: "onepiece",
    label: "ワンピース・英語版",
    source: "TCGplayer",
    currency: "USD",
    rateJpy: Math.round(usdJpy * 100) / 100,
    disclaimer: "英語版カードの米国相場を円換算した参考値です(日本語版の相場ではありません)",
    siteUrl: null,
    keywords: ["ワンピースカード", "ワンピカ", "onepiececard", "optcg"],
    // カード番号で照合する(番号は日本語版・英語版で共通)
    matchBy: "code",
    codePattern: "\\b(?:(?:OP|ST|EB|PRB)\\d{2}|P)-\\d{3}\\b",
    // タイトルの語→版。上から順に判定し、どれにも当たらなければ defaultVariant
    variantRules: [
      ["sp-gold", "金sp|ゴールドsp|gold"],
      ["sp", "(?:^|[^a-z])sp(?:[^a-z]|$)|スペシャル"],
      ["manga", "コミパラ|コミック|マンガ|漫画|manga"],
      ["signature", "サイン|signature"],
      ["wanted", "手配書|wanted"],
      ["parallel", "パラレル|パラ|アルトアート|alt"],
    ],
    defaultVariant: "normal",
    variantLabels: {
      normal: "通常版",
      parallel: "パラレル",
      manga: "コミパラ",
      sp: "SP",
      "sp-gold": "金SP",
      signature: "サイン入り",
      wanted: "手配書",
      other: "特殊加工版",
    },
    fetchedAt: new Date().toISOString(),
    sets: [],
    cards,
  };
  await fs.writeFile(OUT_FILE, JSON.stringify(out));
  console.log(`export-onepiece: ${cards.length} cards → dist/api/onepiece.json`);
}

// 単体実行(npm run build から呼ばれる)。どんな失敗でもビルドを止めない
if (import.meta.url === `file://${process.argv[1]}`) {
  await exportOnePiece().catch((err) => writeUnavailable(`unexpected error (${err.message})`));
}
