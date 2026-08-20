// ステップ4: スコアリングとレポート生成
// 空きドメインを「運用歴(中古度)・被リンク・名前の質・ニッチ一致」で採点し、
// リスク(商標・履歴汚染)をフラグ化して data/site/ に書き出す。
// report.js はダッシュボード(index.html)がビルド無しで読むためのデータ。
import path from "node:path";
import {
  SITE_DIR,
  TLD_WEIGHTS,
  NICHE_KEYWORDS,
  RISK_BRAND_TERMS,
  RISK_SENSITIVE_TERMS,
} from "./config.mjs";
import { writeJson } from "./util.mjs";

function scoreDomain(domain, wayback, oprRank) {
  const [label, ...tldParts] = domain.split(".");
  const tld = tldParts.join(".");
  const parts = {};
  const flags = [];

  // --- 運用歴(中古ドメインとしての価値の核心)最大35点 ---
  const { months = 0, firstYear = null, lastYear = null } = wayback ?? {};
  parts.history = Math.min(20, Math.round(months / 3)); // 3スナップ月=1点
  const nowYear = new Date().getFullYear();
  if (lastYear && nowYear - lastYear <= 3) parts.history += 10; // 最近までの運用=被リンクが生きている可能性
  if (firstYear && firstYear <= nowYear - 10) parts.history += 5; // 10年以上前からの歴史

  // --- 被リンク(Open PageRank 0〜10)最大30点 ---
  parts.backlink = Math.round(Math.min(10, oprRank ?? 0) * 3);

  // --- 名前の質 最大25点 ---
  parts.name = TLD_WEIGHTS[tld] ?? 0;
  if (label.length <= 8) parts.name += 10;
  else if (label.length <= 12) parts.name += 6;
  else if (label.length <= 16) parts.name += 3;
  if (!/[-0-9]/.test(label)) parts.name += 5;

  // --- ニッチ一致 最大10点 ---
  parts.niche = NICHE_KEYWORDS.some((k) => label.includes(k)) ? 10 : 0;

  // --- リスク(減点+フラグ) ---
  let penalty = 0;
  if (RISK_BRAND_TERMS.some((t) => label.includes(t))) {
    flags.push("商標");
    penalty += 30;
  }
  if (RISK_SENSITIVE_TERMS.some((t) => label.includes(t))) {
    flags.push("要履歴確認");
    penalty += 20;
  }

  const score = Math.max(
    0,
    parts.history + parts.backlink + parts.name + parts.niche - penalty,
  );
  return { score, parts, flags, months, firstYear, lastYear };
}

export async function aggregate({ domains, watchlist }, checked, { wayback, ranks }) {
  const statusOf = (d) => checked[d]?.status ?? "unknown";

  const available = domains
    .filter(({ domain }) => statusOf(domain) === "available")
    .map(({ domain, source }) => ({
      domain,
      source,
      droppedAt: checked[domain]?.droppedAt ?? null,
      opr: ranks[domain] ?? null,
      ...scoreDomain(domain, wayback[domain], ranks[domain]),
    }))
    .sort((a, b) => b.score - a.score);

  const watch = watchlist.map((domain) => ({
    domain,
    status: statusOf(domain),
    checkedAt: checked[domain]?.checkedAt ?? null,
    droppedAt: checked[domain]?.droppedAt ?? null,
  }));

  const counts = { available: 0, registered: 0, unknown: 0 };
  for (const { domain } of domains) counts[statusOf(domain)]++;

  const report = {
    updatedAt: new Date().toISOString(),
    counts: { ...counts, candidates: domains.length, watchlist: watchlist.length },
    oprEnabled: Object.keys(ranks).length > 0,
    available,
    watchlist: watch,
  };
  await writeJson(path.join(SITE_DIR, "report.json"), report);
  // file://で直接開いてもfetch制限に掛からないよう、JSとしても書き出す
  const fs = await import("node:fs/promises");
  await fs.writeFile(
    path.join(SITE_DIR, "report.js"),
    `window.DOMAIN_REPORT = ${JSON.stringify(report)};\n`,
  );
  console.log(
    `aggregate: done (${available.length} available scored, top: ${available[0]?.domain ?? "-"})`,
  );
  return report;
}
