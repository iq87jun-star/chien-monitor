// パイプライン一括実行: 収集 → 集計・差分検知 → AI記事生成
import { fetchAll } from "./fetch-data.mjs";
import { aggregate } from "./aggregate.mjs";
import { generateArticles } from "./generate-articles.mjs";

try {
  await fetchAll();
  await aggregate();
} catch (err) {
  // データ更新の失敗はCIを落とす(前回データのままサイトは生き続ける)
  console.error("pipeline failed:", err);
  process.exit(1);
}

try {
  await generateArticles();
} catch (err) {
  // 記事生成の失敗はデータ更新を巻き添えにしない
  console.warn("article generation failed (non-fatal):", err.message);
}

console.log("pipeline: complete");
