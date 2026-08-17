// パイプライン一括実行: 収集 → 集計・差分検知 → ビルドメタ → AI記事生成 → X速報
import { fetchAll } from "./fetch-data.mjs";
import { aggregate } from "./aggregate.mjs";
import { fetchLadder } from "./fetch-ladder.mjs";
import { generateArticles } from "./generate-articles.mjs";
import { postToX } from "./post-x.mjs";

try {
  await fetchAll();
  await aggregate();
} catch (err) {
  // データ更新の失敗はCIを落とす(前回データのままサイトは生き続ける)
  console.error("pipeline failed:", err);
  process.exit(1);
}

// 以降の各ステップは任意機能(認証情報がある時だけ動く)。失敗しても他を巻き添えにしない
for (const [name, step] of [
  ["build meta", fetchLadder],
  ["article generation", generateArticles],
  ["x post", postToX],
]) {
  try {
    await step();
  } catch (err) {
    console.warn(`${name} failed (non-fatal):`, err.message);
  }
}

console.log("pipeline: complete");
