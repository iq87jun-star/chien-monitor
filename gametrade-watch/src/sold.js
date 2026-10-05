// 売れたアカウント(一覧に SOLD と出る出品)を集める処理。査定ツールの値付けを学習するためのデータ。
// ゲームトレードは取引が終わった出品も一覧に価格付きで残すので、それを読み取って Worker の D1 に貯める。
// 実行環境に依存しない(Cloudflare Worker と手元の Node の両方から使う)。

import { decode, parseExhibits } from "./core.js";

export const ORIGIN = "https://gametrade.jp";

// 一覧の URL(全ての商品・新着順・価格帯)
export function listUrl(game, { low, high }) {
  const url = new URL(`/${game}/exhibits`, ORIGIN);
  url.searchParams.set("filter", "all");
  url.searchParams.set("sort", "new");
  url.searchParams.set("low_price", String(low));
  url.searchParams.set("high_price", String(high));
  return url.href;
}

// 一覧ページから売れた出品だけを取り出す
export const parseSold = (html) => parseExhibits(html, ORIGIN).filter((it) => it.sold);

// 出品ページから説明文の全文と画像(原寸)を取り出す。一覧の説明文は途中で切れているため
export function parseDetail(html) {
  const body = /<div class="item-description">([\s\S]*?)<\/div>/.exec(html)?.[1] ?? "";
  const description = decode(
    body
      .replace(/\s*<br\s*\/?>\s*/g, "\n")
      .replace(/<\/p>\s*<p>/g, "\n\n")
      .replace(/<[^>]+>/g, ""),
  ).trim();
  // 出品の画像は原寸の URL で並ぶ(下の「関連する出品」は small_thumb_ だけなので混ざらない)
  const images = [
    ...new Set([...html.matchAll(/https:\/\/cdn\.gametrade\.jp\/[^"' ]*?exhibit_image\/file\/\d+\/[0-9a-f-]+\.(?:jpe?g|png|webp)/g)].map((m) => m[0])),
  ];
  return { description, images, done: html.includes("取引が終了しました") };
}

// Worker に送る1件分(D1 の sold テーブルの列に合わせる)
export const soldRecord = (it) => ({
  id: it.id,
  name: it.name,
  price: it.price,
  url: it.url,
  image: it.image,
  info: it.info,
});

// Worker 側の受け付け: 形を確かめて、保存できるものだけ返す
export function validRecords(items) {
  if (!Array.isArray(items)) return [];
  return items.filter(
    (it) =>
      /^\d+$/.test(String(it?.id ?? "")) &&
      typeof it.name === "string" &&
      Number.isInteger(it.price) &&
      it.price >= 0 &&
      (it.url == null || typeof it.url === "string") &&
      (it.image == null || typeof it.image === "string") &&
      (it.info == null || (Array.isArray(it.info) && it.info.every((x) => typeof x === "string"))),
  );
}
