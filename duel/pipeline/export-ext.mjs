// ビルド後処理: ブラウザ拡張「トレカ海外相場チェッカー」用の軽量価格データを
// dist/api/cards.json に書き出す(toreca/pipeline/export-ext.mjs と同じ v1 形式)。
// 遊戯王は日本のフリマでは日本語(OCG)名で出品されるため、fetch-data.mjs が作る
// 英語名→日本語名の対応表(data/raw/ja-names.json)で照合用の名前を付ける。
// 価格は YGOPRODeck の Cardmarket 価格=英語版(TCG)で最も安い版の相場で、日本語版や
// レアリティ別の相場ではない点に注意(拡張側の表示でもその旨を明記する)。
// 最安版が数円のカード(ブラック・マジシャン等)は高レアの出品に出すと誤解を招くので、
// 履歴追跡と同じ MIN_TRACK_EUR 以上のカードだけを出す。
// 形式を変える時は extension/src/matcher.js と FORMAT_VERSION を合わせて更新すること。
import fs from "node:fs/promises";
import path from "node:path";
import { ROOT, RAW_DIR, MIN_TRACK_EUR } from "./config.mjs";

const FORMAT_VERSION = 1;
const OUT_DIR = path.join(ROOT, "dist", "api");

async function readJson(file) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return null;
  }
}

// 日本語名には正式名と読み仮名(「万物創世龍」と「テンサウザンド・ドラゴン」、
// 「灰流うらら」と「はるうらら」)が混在する。漢字を含む名前→ひらがなの少ない名前の順に並べ、
// 先頭を表示名にする。日本語の文字を含まないもの(TCG専用カードの英語名)は除く
const JA_CHARS = /[ぁ-ヿ一-鿿]/;
const KANJI = /[一-鿿]/;
const hiraganaCount = (s) => (s.match(/[ぁ-ゖ]/g) ?? []).length;
const displayOrder = (a, b) =>
  (KANJI.test(a) ? 0 : 1) - (KANJI.test(b) ? 0 : 1) || hiraganaCount(a) - hiraganaCount(b);

export async function exportExt() {
  const raw = await readJson(path.join(RAW_DIR, "cards.json"));
  const fx = await readJson(path.join(RAW_DIR, "fx.json"));
  const ja = (await readJson(path.join(RAW_DIR, "ja-names.json")))?.names ?? {};
  const eurJpy = fx?.rates?.JPY ?? null;
  await fs.mkdir(OUT_DIR, { recursive: true });

  const cards =
    raw && Array.isArray(raw.cards) && eurJpy
      ? raw.cards
          .map((c) => ({ c, jaNames: (ja[c.name] ?? []).filter((n) => JA_CHARS.test(n)) }))
          .filter(({ c, jaNames }) => c.eur >= MIN_TRACK_EUR && jaNames.length > 0)
          .map(({ c, jaNames }) => {
            const names = [...jaNames].sort(displayOrder);
            // [setId, localId, 照合名(配列・先頭が表示名), eur, avg7, avg30, 補足(英語名)]
            // セット・番号の情報は無い。7日/30日平均も無い(自前履歴は騰落率用)
            return ["", "", names, c.eur, null, null, c.name];
          })
      : [];

  if (cards.length === 0) {
    // データ欠如時は available:false を出す(拡張側は前回キャッシュを使い続ける)
    await fs.writeFile(
      path.join(OUT_DIR, "cards.json"),
      JSON.stringify({ v: FORMAT_VERSION, available: false }),
    );
    console.warn("export-ext: raw data or ja names missing — wrote available:false");
    return;
  }

  const out = {
    v: FORMAT_VERSION,
    available: true,
    game: "yugioh",
    label: "遊戯王・英語版TCG",
    disclaimer:
      "英語版で最も安い版の欧州相場を円換算した参考値です(日本語版・レアリティ別ではありません)",
    siteUrl: "https://pocketduel.tokyo/",
    // 出品タイトルにこれらの語(またはカード番号 QCCP-JP001 形式)があれば遊戯王の出品とみなす
    keywords: ["遊戯王", "yugioh", "ygo", "ocg", "デュエルモンスターズ"],
    codePattern: "[a-z0-9]{2,5}-jp[0-9]{3}",
    fetchedAt: raw.fetchedAt,
    eurJpy,
    sets: [],
    cards,
  };
  await fs.writeFile(path.join(OUT_DIR, "cards.json"), JSON.stringify(out));
  console.log(`export-ext: ${cards.length} cards → dist/api/cards.json`);
}

// 単体実行(npm run build から呼ばれる)
if (import.meta.url === `file://${process.argv[1]}`) {
  await exportExt();
}
