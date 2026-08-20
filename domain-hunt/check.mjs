#!/usr/bin/env node
// 中古・キーワードドメイン発掘チェッカー
//
// candidates.txt のドメインを1件ずつ調べて results.json に保存する。
//   1. 空き状況 — .com/.net は Verisign RDAP、.tokyo は GMOレジストリ RDAP、
//      .jp / .co.jp は JPRS WHOIS(Web版) で判定
//   2. 取得可能なものは Wayback Machine の availability API で
//      過去の運用履歴(最古・最新スナップショット)を照会
//      → 履歴がある=失効した中古ドメイン(被リンク・指名検索が残っている可能性)
//   3. 登録済みの .jp 系は WHOIS の [状態] から有効期限を拾い、
//      失効間近(90日以内)なら watchlist として報告
//
// 使い方: node domain-hunt/check.mjs
//   ローカル(プロキシ環境)では NODE_USE_ENV_PROXY=1 を付ける。
//   各レジストリのレート制限が厳しいため、実行には候補数×数秒かかる。

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = dirname(fileURLToPath(import.meta.url));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// レジストリごとの問い合わせ間隔(ミリ秒)。GMOとJPRSは特に厳しい
const WAIT = { com: 500, net: 500, tokyo: 8000, jp: 3000, wayback: 6000 };

async function fetchText(url) {
  for (let attempt = 1; ; attempt++) {
    try {
      const res = await fetch(url, { headers: { 'user-agent': 'domain-hunt/1.0' } });
      return { status: res.status, body: await res.text() };
    } catch (e) {
      if (attempt >= 3) return { status: 0, body: '', error: String(e.cause ?? e) };
      await sleep(2000 * attempt);
    }
  }
}

async function checkAvailability(domain) {
  const tld = domain.split('.').pop();
  if (tld === 'com' || tld === 'net') {
    const { status } = await fetchText(`https://rdap.verisign.com/${tld}/v1/domain/${domain}`);
    await sleep(WAIT.com);
    return status === 404 ? { state: 'available' } : status === 200 ? { state: 'registered' } : { state: `error:${status}` };
  }
  if (tld === 'tokyo') {
    const { status } = await fetchText(`https://rdap.gmoregistry.net/rdap/domain/${domain}`);
    await sleep(WAIT.tokyo);
    return status === 404 ? { state: 'available' } : status === 200 ? { state: 'registered' } : { state: `error:${status}` };
  }
  if (tld === 'jp') {
    const { body } = await fetchText(`https://whois.jprs.jp/?key=${domain}&type=DOM`);
    await sleep(WAIT.jp);
    if (body.includes('該当するデータがありません')) return { state: 'available' };
    if (body.includes('Domain Information')) {
      // [状態]  Connected (2026/09/30) 等から有効期限を抽出
      const m = body.match(/\[状態\]\s*([A-Za-z]+)\s*\((\d{4}\/\d{2}\/\d{2})\)/);
      return { state: 'registered', jpState: m?.[1], expires: m?.[2] };
    }
    return { state: 'error:jprs' };
  }
  return { state: 'skip:unsupported-tld' };
}

async function waybackSnapshot(domain, timestamp) {
  const ts = timestamp ? `&timestamp=${timestamp}` : '';
  const { status, body } = await fetchText(`https://archive.org/wayback/available?url=${domain}${ts}`);
  await sleep(WAIT.wayback);
  if (status !== 200) return null;
  try {
    return JSON.parse(body).archived_snapshots?.closest?.timestamp ?? null;
  } catch {
    return null;
  }
}

// 使い方: node check.mjs [候補ファイル] [結果JSON](省略時は candidates.txt / results.json)
const candidatesFile = process.argv[2] ?? join(DIR, 'candidates.txt');
const outputFile = process.argv[3] ?? join(DIR, 'results.json');
const candidates = readFileSync(candidatesFile, 'utf8')
  .split('\n')
  .map((l) => l.replace(/#.*/, '').trim())
  .filter(Boolean);

const results = [];
for (const domain of candidates) {
  const row = { domain, ...(await checkAvailability(domain)) };
  // archive.org へ直接届かない環境では SKIP_WAYBACK=1 で空き判定のみ行う
  if (row.state === 'available' && !process.env.SKIP_WAYBACK) {
    row.waybackFirst = await waybackSnapshot(domain, '1996');
    row.waybackLast = await waybackSnapshot(domain);
  }
  results.push(row);
  console.log(
    `${domain}\t${row.state}` +
      (row.expires ? `\texpires:${row.expires}` : '') +
      (row.waybackLast ? `\thistory:${row.waybackFirst?.slice(0, 8)}-${row.waybackLast.slice(0, 8)}` : ''),
  );
}

const summary = {
  checkedAt: new Date().toISOString(),
  available: results.filter((r) => r.state === 'available'),
  // 履歴つきで空いている=中古ドメインの掘り出し物候補
  availableWithHistory: results.filter((r) => r.state === 'available' && r.waybackLast),
  // 失効90日以内の登録済み.jp系=ドロップ待ち監視対象
  watchlist: results.filter((r) => {
    if (!r.expires) return false;
    const exp = new Date(r.expires.replaceAll('/', '-'));
    return exp - Date.now() < 90 * 24 * 3600 * 1000;
  }),
  all: results,
};
writeFileSync(outputFile, JSON.stringify(summary, null, 2));

console.log(`\n取得可能: ${summary.available.length} / ${results.length}`);
console.log(`うち運用履歴あり(中古候補): ${summary.availableWithHistory.map((r) => r.domain).join(', ') || 'なし'}`);
console.log(`失効間近の監視対象: ${summary.watchlist.map((r) => `${r.domain}(${r.expires})`).join(', ') || 'なし'}`);
