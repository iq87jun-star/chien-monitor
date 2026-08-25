// パイプライン一括実行: 候補収集 → 空き状況チェック → 価値評価 → スコアリング
import { collect } from "./collect.mjs";
import { check } from "./check.mjs";
import { enrich } from "./enrich.mjs";
import { aggregate } from "./aggregate.mjs";

try {
  const candidates = await collect();
  const checked = await check(candidates);
  const availableDomains = candidates.domains
    .map(({ domain }) => domain)
    .filter((d) => checked[d]?.status === "available");
  const enriched = await enrich(availableDomains);
  await aggregate(candidates, checked, enriched);
} catch (err) {
  console.error("pipeline failed:", err);
  process.exit(1);
}

console.log("pipeline: complete");
