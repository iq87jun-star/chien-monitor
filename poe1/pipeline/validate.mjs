// 生成記事の自動検品ゲート
// 記事本文に登場する数値が、集計データ由来の「許可された数値」に含まれるかを照合する。
// ハルシネーションで数値を捏造した記事を公開前に落とすための仕組み。

// データから許可数値集合を作る(丸め違いも許容できるよう複数表現を登録)
export function collectAllowedNumbers(obj, set = new Set()) {
  if (typeof obj === "number" && Number.isFinite(obj)) {
    const variants = [
      obj,
      Math.round(obj),
      Math.round(obj * 10) / 10,
      Math.round(obj * 100) / 100,
      Math.abs(Math.round(obj * 10) / 10),
      Math.round(Math.abs(obj)),
    ];
    for (const v of variants) set.add(String(v));
  } else if (Array.isArray(obj)) {
    for (const v of obj) collectAllowedNumbers(v, set);
  } else if (obj && typeof obj === "object") {
    for (const v of Object.values(obj)) collectAllowedNumbers(v, set);
  }
  return set;
}

// 記事テキスト中の数値を抽出して照合。違反リストを返す(空なら合格)
export function validateArticleNumbers(article, allowed) {
  const texts = [
    article.title,
    article.summary,
    ...(article.sections ?? []).flatMap((s) => [s.heading, s.body]),
  ].join("\n");

  const violations = [];
  for (const m of texts.matchAll(/\d+(?:\.\d+)?/g)) {
    const numStr = m[0];
    const num = Number(numStr);
    // 文章表現上の小さい数(「3つの要因」等)・年・バージョン番号断片は許容
    if (num <= 12) continue;
    if (num >= 2024 && num <= 2030) continue;
    if (!allowed.has(numStr) && !allowed.has(String(Math.round(num)))) {
      violations.push(numStr);
    }
  }
  return violations;
}

// スキーマの最低限チェック
export function validateArticleShape(article) {
  return (
    article &&
    typeof article.title === "string" &&
    article.title.length > 0 &&
    typeof article.summary === "string" &&
    Array.isArray(article.sections) &&
    article.sections.length > 0 &&
    article.sections.every(
      (s) => typeof s.heading === "string" && typeof s.body === "string",
    )
  );
}
