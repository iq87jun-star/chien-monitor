// ステップ3: 空きドメインの価値評価データ収集
// Wayback Machine CDXで過去の運用歴(初出年・最終年・スナップショット月数)を、
// Open PageRank(任意・OPR_API_KEY設定時)で被リンク由来のドメインランクを取得する。
// 過去の履歴は変わらないためWayback結果は長期キャッシュする。
import path from "node:path";
import {
  RAW_DIR,
  WAYBACK_CDX,
  OPR_URL,
  MAX_ENRICH_PER_RUN,
  WAYBACK_CACHE_DAYS,
  CONCURRENCY,
} from "./config.mjs";
import { readJson, writeJson, fetchWithRetry, mapLimit, sleep } from "./util.mjs";

const CACHE_FILE = path.join(RAW_DIR, "wayback.json");

async function fetchWayback(domain) {
  // 月単位にcollapseして運用期間を軽量に把握する(200応答のみ=実体のあったページ)
  const url =
    `${WAYBACK_CDX}?url=${encodeURIComponent(domain)}&output=json` +
    `&fl=timestamp,statuscode&filter=statuscode:200&collapse=timestamp:6&limit=500`;
  const res = await fetchWithRetry(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const rows = await res.json();
  const stamps = rows.slice(1).map(([ts]) => ts); // 先頭行はヘッダ
  if (stamps.length === 0) return { months: 0, firstYear: null, lastYear: null };
  return {
    months: stamps.length,
    firstYear: +stamps[0].slice(0, 4),
    lastYear: +stamps[stamps.length - 1].slice(0, 4),
  };
}

async function fetchOpenPageRank(domains) {
  const key = process.env.OPR_API_KEY;
  if (!key || domains.length === 0) return {};
  const ranks = {};
  for (let i = 0; i < domains.length; i += 100) {
    const batch = domains.slice(i, i + 100);
    const qs = batch.map((d) => `domains[]=${encodeURIComponent(d)}`).join("&");
    const res = await fetchWithRetry(`${OPR_URL}?${qs}`, { headers: { "API-OPR": key } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    for (const r of (await res.json()).response ?? []) {
      if (r.status_code === 200) ranks[r.domain.toLowerCase()] = r.page_rank_decimal ?? 0;
    }
  }
  return ranks;
}

export async function enrich(availableDomains) {
  const cache = (await readJson(CACHE_FILE, { domains: {} })).domains;
  const now = Date.now();

  const targets = availableDomains
    .filter((d) => {
      const e = cache[d];
      return !e || now - Date.parse(e.fetchedAt) > WAYBACK_CACHE_DAYS * 24 * 3600e3;
    })
    .slice(0, MAX_ENRICH_PER_RUN);

  await mapLimit(targets, CONCURRENCY, async (domain) => {
    const info = await fetchWayback(domain);
    cache[domain] = { ...info, fetchedAt: new Date().toISOString() };
    await sleep(400 + Math.random() * 400); // Waybackに負荷をかけない
  });
  await writeJson(CACHE_FILE, { updatedAt: new Date().toISOString(), domains: cache }, 0);

  // Open PageRankはキー設定時のみ(失敗しても致命ではない)
  let ranks = {};
  try {
    ranks = await fetchOpenPageRank(availableDomains);
  } catch (err) {
    console.warn(`enrich: open pagerank unavailable (${err.message})`);
  }

  console.log(
    `enrich: done (${targets.length} wayback lookups this run, opr=${Object.keys(ranks).length > 0 ? "on" : "off"})`,
  );
  return { wayback: cache, ranks };
}
