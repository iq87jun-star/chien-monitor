// ステップ1: 候補ドメインの収集
// 2系統から集める:
//   a) input/candidates.txt … 手動追加(ExpiredDomains.net等から貼り付け)
//   b) シードURLのリンク切れ発掘 … 古い外部リンクを多く含むページから
//      リンク先ドメインを抽出する(未登録になっていれば「被リンク付き中古」)
// input/watchlist.txt は別枠で常に監視する(取得したい登録済みドメインのドロップ待ち)。
import path from "node:path";
import { RAW_DIR, INPUT_DIR, SEED_URLS, TLD_WEIGHTS, EXCLUDE_DOMAINS } from "./config.mjs";
import { readLines, writeJson, fetchWithRetry, mapLimit } from "./util.mjs";

const TLDS = Object.keys(TLD_WEIGHTS).sort((a, b) => b.length - a.length);

// ホスト名を「登録可能なドメイン」(ラベル1つ+対象TLD)に正規化。対象外はnull
export function normalizeDomain(host) {
  const h = host.toLowerCase().replace(/^www\./, "").replace(/\.$/, "");
  if (!/^[a-z0-9.-]+$/.test(h) || h.startsWith("xn--")) return null; // IDNは対象外
  const tld = TLDS.find((t) => h.endsWith("." + t));
  if (!tld) return null;
  const label = h.slice(0, -(tld.length + 1));
  if (!label || label.includes(".")) return null; // サブドメインは親を拾わない(所有判定が曖昧なため)
  if (!/^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/.test(label)) return null;
  const domain = `${label}.${tld}`;
  return EXCLUDE_DOMAINS.has(domain) ? null : domain;
}

// ページHTMLから外部リンクのホスト名を抽出する。
// Wayback再生ページでは元URLが /web/<timestamp>/http://… に書き換えられるため、
// その内側のホスト名も拾う(こちらが本来の中古候補)
function extractHosts(html) {
  const hosts = new Set();
  for (const m of html.matchAll(/\/web\/\d[^/"']*\/(?:https?:\/\/)?([a-z0-9.-]+\.[a-z]{2,})/gi)) {
    hosts.add(m[1]);
  }
  for (const m of html.matchAll(/href="https?:\/\/([^/"?#]+)/g)) {
    if (m[1] !== "web.archive.org") hosts.add(m[1]);
  }
  return [...hosts];
}

export async function collect() {
  const seen = new Map(); // domain -> source(最初に見つけた供給元)

  // --- a) 手動リスト(URLや大文字が混ざっていても正規化して受け入れる) ---
  for (const line of await readLines(path.join(INPUT_DIR, "candidates.txt"))) {
    const host = line.replace(/^https?:\/\//, "").split("/")[0];
    const d = normalizeDomain(host);
    if (d && !seen.has(d)) seen.set(d, "manual");
  }
  const manualCount = seen.size;

  // --- b) シードページのリンク切れ発掘 ---
  await mapLimit(SEED_URLS, 2, async (url) => {
    const res = await fetchWithRetry(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const hosts = extractHosts(await res.text());
    let added = 0;
    for (const host of hosts) {
      const d = normalizeDomain(host);
      if (d && !seen.has(d)) {
        seen.set(d, "seed");
        added++;
      }
    }
    console.log(`collect: ${added} new domains from ${decodeURIComponent(url).slice(0, 60)}…`);
  });

  // --- ウォッチリスト(候補とは別枠・毎回必ずチェックする) ---
  const watchlist = [];
  for (const line of await readLines(path.join(INPUT_DIR, "watchlist.txt"))) {
    const d = normalizeDomain(line.replace(/^https?:\/\//, "").split("/")[0]);
    if (d && !watchlist.includes(d)) watchlist.push(d);
  }

  const domains = [...seen].map(([domain, source]) => ({ domain, source }));
  await writeJson(path.join(RAW_DIR, "candidates.json"), {
    updatedAt: new Date().toISOString(),
    counts: { manual: manualCount, seed: domains.length - manualCount },
    domains,
    watchlist,
  });
  console.log(
    `collect: done (${domains.length} candidates: manual=${manualCount} seed=${domains.length - manualCount}, watchlist=${watchlist.length})`,
  );
  return { domains, watchlist };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  collect().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
