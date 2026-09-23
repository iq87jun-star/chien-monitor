// ビルド後処理: ブラウザ拡張「トレカ海外相場チェッカー」用の軽量価格データを
// dist/api/cards.json に書き出す。拡張はこのURLを数時間おきに取得し、
// メルカリ等の商品ページのタイトルとカード名を突き合わせて海外相場を表示する。
// 形式を変える時は extension/src/matcher.js と FORMAT_VERSION を合わせて更新すること。
import fs from "node:fs/promises";
import path from "node:path";
import { ROOT, RAW_DIR } from "./config.mjs";

const FORMAT_VERSION = 1;
const OUT_DIR = path.join(ROOT, "dist", "api");

async function readJson(file) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return null;
  }
}

export async function exportExt() {
  const raw = await readJson(path.join(RAW_DIR, "cards.json"));
  const fx = await readJson(path.join(RAW_DIR, "fx.json"));
  const eurJpy = fx?.rates?.JPY ?? null;
  await fs.mkdir(OUT_DIR, { recursive: true });

  if (!raw || !Array.isArray(raw.cards) || raw.cards.length === 0 || !eurJpy) {
    // データ欠如時は available:false を出す(拡張側は前回キャッシュを使い続ける)
    await fs.writeFile(
      path.join(OUT_DIR, "cards.json"),
      JSON.stringify({ v: FORMAT_VERSION, available: false }),
    );
    console.warn("export-ext: raw data missing — wrote available:false");
    return;
  }

  // 容量節約のため配列形式: [setId, localId, name, eur, avg7, avg30]
  const cards = raw.cards
    .filter((c) => c.eur != null && c.eur > 0)
    .map((c) => [c.setId, c.localId, c.name, c.eur, c.avg7 ?? null, c.avg30 ?? null]);

  const out = {
    v: FORMAT_VERSION,
    available: true,
    fetchedAt: raw.fetchedAt,
    eurJpy,
    sets: raw.sets.map((s) => ({ id: s.id, name: s.name, cardCount: s.cardCount })),
    cards,
  };
  await fs.writeFile(path.join(OUT_DIR, "cards.json"), JSON.stringify(out));
  console.log(`export-ext: ${cards.length} cards → dist/api/cards.json`);
}

// 単体実行(npm run build から呼ばれる)
if (import.meta.url === `file://${process.argv[1]}`) {
  await exportExt();
}
