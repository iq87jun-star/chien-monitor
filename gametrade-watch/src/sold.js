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

// 売れた記録のキーワード検索(仕入れの相場確認用)。空白で区切った語をすべて含むもの(タイトルか説明文)
// 返り値: D1 に渡す SQL と値。語は 5 つまで、1 語 30 文字まで
export function searchQuery({ game, q, low, high, limit = 300 }) {
  const words = String(q ?? "")
    .normalize("NFKC")
    .split(/[\s　]+/)
    .map((w) => w.trim().slice(0, 30))
    .filter(Boolean)
    .slice(0, 5);
  const where = ["site = 'gametrade'", "name NOT LIKE '%専用%'"];
  const binds = [];
  if (game) where.push("game = ?"), binds.push(game);
  for (const w of words) {
    where.push("(name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\')");
    const like = `%${w.replace(/[\\%_]/g, (c) => `\\${c}`)}%`;
    binds.push(like, like);
  }
  if (Number(low) > 0) where.push("price >= ?"), binds.push(Number(low));
  if (Number(high) > 0) where.push("price <= ?"), binds.push(Number(high));
  const n = Math.min(Math.max(Number(limit) || 300, 1), 1000);
  return {
    words,
    sql: `SELECT id, game, name, price, url, first_seen FROM sold WHERE ${where.join(" AND ")} ORDER BY first_seen DESC, CAST(id AS INTEGER) DESC LIMIT ?`,
    binds: [...binds, n],
  };
}
