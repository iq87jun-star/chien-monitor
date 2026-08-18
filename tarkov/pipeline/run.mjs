// パイプライン一括実行: 収集 → 集計・差分検知 → AI記事生成
import { fetchAll } from "./fetch-data.mjs";
import { aggregate } from "./aggregate.mjs";
import { generateArticles } from "./generate-articles.mjs";
import { postToX } from "./post-x.mjs";

try {
  // fetchはAPI障害時に警告のみで戻る(既存rawを保持)。aggregateはraw欠如時に
  // メンテナンス用economy.jsonを書くため、どちらの場合もビルド可能な状態を保つ。
  await fetchAll();
  await aggregate();
} catch (err) {
  // 予期しないデータ更新の失敗はCIを落とす(前回データのままサイトは生き続ける)
  console.error("pipeline failed:", err);
  process.exit(1);
}

// 以降のステップは任意機能(認証情報がある時だけ動く)。失敗しても他を巻き添えにしない
for (const [name, step] of [
  ["article generation", generateArticles],
  ["x posting", postToX],
]) {
  try {
    await step();
  } catch (err) {
    console.warn(`${name} failed (non-fatal):`, err.message);
  }
}

console.log("pipeline: complete");
