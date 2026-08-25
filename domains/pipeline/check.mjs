// ステップ2: 空き状況チェック
// 一次判定はDNS over HTTPS(NSレコードがあれば登録済み)。NSが無い場合のみ
// 権威ソースで確認する: .jpはJPRS whois(port 43)、gTLDはRDAP(404=未登録)。
// 結果は data/raw/checked.json にキャッシュし、TTL内は再チェックしない
// (登録済みドメインもいずれドロップするため、30日おきに見直す)。
import net from "node:net";
import path from "node:path";
import {
  RAW_DIR,
  DOH_URL,
  RDAP_URL,
  JPRS_WHOIS_HOST,
  MAX_CHECKS_PER_RUN,
  RECHECK_DAYS,
  CONCURRENCY,
} from "./config.mjs";
import { readJson, writeJson, fetchWithRetry, mapLimit, sleep } from "./util.mjs";

const CACHE_FILE = path.join(RAW_DIR, "checked.json");

async function dohHasNs(domain) {
  const res = await fetchWithRetry(
    `${DOH_URL}?name=${encodeURIComponent(domain)}&type=NS`,
    { headers: { Accept: "application/dns-json" } },
  );
  const body = await res.json();
  // Status 0=NOERROR / 3=NXDOMAIN。NXDOMAINでも属性型JP等の例外があるため
  // 「NSあり=登録済み」の判定にだけ使い、無い場合は権威ソースで確認する
  return (body.Answer ?? []).some((a) => a.type === 2);
}

function whoisQuery(host, query, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    const socket = net.createConnection(43, host);
    let buf = "";
    socket.setTimeout(timeoutMs);
    socket.on("connect", () => socket.write(query + "\r\n"));
    socket.on("data", (d) => (buf += d.toString()));
    socket.on("end", () => resolve(buf));
    socket.on("timeout", () => {
      socket.destroy();
      reject(new Error("whois timeout"));
    });
    socket.on("error", reject);
  });
}

// 単一ドメインの空き状況判定: registered / available / unknown
async function checkOne(domain) {
  if (await dohHasNs(domain)) return { status: "registered", via: "dns" };

  if (domain.endsWith(".jp")) {
    try {
      const body = await whoisQuery(JPRS_WHOIS_HOST, `${domain}/e`);
      if (/no match!!/i.test(body)) return { status: "available", via: "jprs" };
      if (/domain information/i.test(body)) return { status: "registered", via: "jprs" };
      return { status: "unknown", via: "jprs" };
    } catch (err) {
      // port 43が塞がれた環境(ローカル実行等)ではunknownとして継続
      return { status: "unknown", via: `jprs-error:${err.message}` };
    }
  }

  const res = await fetchWithRetry(RDAP_URL + encodeURIComponent(domain));
  if (res.status === 404) return { status: "available", via: "rdap" };
  if (res.ok) return { status: "registered", via: "rdap" };
  return { status: "unknown", via: `rdap:${res.status}` };
}

export async function check({ domains, watchlist }) {
  const cache = (await readJson(CACHE_FILE, { domains: {} })).domains;
  const now = Date.now();
  const isStale = (e) =>
    !e ||
    now - Date.parse(e.checkedAt) >
      (RECHECK_DAYS[e.status] ?? 1) * 24 * 3600e3;

  // ウォッチリスト優先(ドロップの瞬間を逃さないよう毎回チェック)、
  // 残り枠で通常候補の未チェック/期限切れ分を処理する
  const targets = [
    ...watchlist.filter((d) => !domains.some((c) => c.domain === d)).map((d) => ({ domain: d })),
    ...domains,
  ]
    .filter((c) => watchlist.includes(c.domain) || isStale(cache[c.domain]))
    .slice(0, MAX_CHECKS_PER_RUN);

  let checked = 0;
  await mapLimit(targets, CONCURRENCY, async ({ domain }) => {
    const result = await checkOne(domain);
    const prev = cache[domain];
    cache[domain] = { ...result, checkedAt: new Date().toISOString() };
    // ドロップ検知: 前回registered→今回availableは見逃したくない変化なので目立たせる
    if (prev?.status === "registered" && result.status === "available") {
      cache[domain].droppedAt = cache[domain].checkedAt;
      console.log(`check: *** DROPPED *** ${domain} is now available`);
    } else if (prev?.droppedAt && result.status === "available") {
      cache[domain].droppedAt = prev.droppedAt;
    }
    checked++;
    await sleep(200 + Math.random() * 300); // 外部サービスへの礼儀としての間隔
  });

  // キャッシュの肥大防止: 候補にもウォッチにも現れない古いエントリを掃除
  const active = new Set([...domains.map((c) => c.domain), ...watchlist]);
  for (const [d, e] of Object.entries(cache)) {
    if (!active.has(d) && now - Date.parse(e.checkedAt) > 90 * 24 * 3600e3) {
      delete cache[d];
    }
  }

  await writeJson(CACHE_FILE, { updatedAt: new Date().toISOString(), domains: cache }, 0);
  const counts = { registered: 0, available: 0, unknown: 0 };
  for (const { domain } of domains) counts[cache[domain]?.status ?? "unknown"]++;
  console.log(
    `check: done (${checked} checked this run; candidates: ${counts.available} available / ${counts.registered} registered / ${counts.unknown} unknown)`,
  );
  return cache;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const { collect } = await import("./collect.mjs");
  check(await collect()).catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
