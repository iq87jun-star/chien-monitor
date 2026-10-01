// ゲームトレード(gametrade.jp)の出品一覧を見て、新規出品と値下げを Discord に通知する処理の本体。
// 実行環境に依存しない(Cloudflare Worker と手元の Node の両方から使う)。

const MAX_PRICES = 5000;
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36";

const decode = (s) =>
  s
    .replace(/&quot;/g, '"')
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&amp;/g, "&");

// 一覧ページの HTML から出品を取り出す
export function parseExhibits(html, origin) {
  const items = [];
  // 一覧部分だけを見る(Cloudflare Worker の CPU 時間を節約)
  const start = html.indexOf('<ul class="exhibits');
  const end = html.indexOf("</ul></div>", html.lastIndexOf('name="exhibit_data"'));
  html = html.slice(Math.max(start, 0), end > 0 ? end : undefined);
  const re = /<input id="exhibit_(\d+)_deta" name="exhibit_data" type="hidden" value="([^"]*)" \/>([\s\S]*?)(?=<input id="exhibit_\d+_deta"|$)/g;
  for (const m of html.matchAll(re)) {
    let data;
    try {
      data = JSON.parse(decode(m[2]));
    } catch {
      continue;
    }
    const block = m[3];
    const img = /<img [^>]*src="([^"]+)"/.exec(block)?.[1];
    const href = /<a class="exhibit-link" href="([^"]+)"/.exec(block)?.[1] ?? "";
    const info = [...block.matchAll(/<div class="sub_form_values">([\s\S]*?)<\/div>/g)]
      .flatMap((x) => [...x[1].matchAll(/<p>([\s\S]*?)<\/p>/g)].map((p) => decode(p[1]).trim()));
    items.push({
      id: m[1],
      name: data.name,
      price: Number(data.price),
      url: new URL(href || `exhibits/${m[1]}`, origin).href,
      image: img && !img.includes("no-image") ? img : null,
      // 値下げされた出品は一覧に元の価格が出る
      previousPrice: Number(/<li class="previous_price"><p>[^0-9]*([\d,]+)/.exec(block)?.[1].replace(/,/g, "")) || null,
      info,
    });
  }
  return items;
}

// 通知する出品を決める。
//   新規出品: 前回までに見た最大の出品IDより新しいID(出品IDは作成順に増える)
//   値下げ  : 記録した価格より下がった / 記録がなく一覧に「元の価格」が出ている
// 古い出品が説明文の編集などで一覧の上に来ただけのものは通知しない
export function pick(all, low, high, state) {
  const out = [];
  for (const it of all) {
    if (it.price < low || it.price > high) continue;
    const known = state.prices[it.id];
    if (known !== undefined) {
      if (it.price < known) out.push({ ...it, kind: "drop", before: known });
    } else if (BigInt(it.id) > BigInt(state.maxId)) {
      out.push({ ...it, kind: "new" });
    } else if (it.previousPrice && it.previousPrice > it.price) {
      out.push({ ...it, kind: "drop", before: it.previousPrice });
    }
  }
  return out;
}

// 一覧に出た出品の現在価格を記録(価格帯外も。後で価格帯に下がってきた時に値下げと分かるように)
export function nextState(state, all, now = new Date()) {
  const prices = { ...(state?.prices ?? {}) };
  for (const it of all) prices[it.id] = it.price;
  const kept = Object.keys(prices)
    .sort((a, b) => (BigInt(b) > BigInt(a) ? 1 : -1))
    .slice(0, MAX_PRICES);
  const maxId = all.reduce((m, it) => (BigInt(it.id) > BigInt(m) ? it.id : m), state?.maxId ?? "0");
  return { maxId, prices: Object.fromEntries(kept.map((id) => [id, prices[id]])), updatedAt: now.toISOString() };
}

const yen = (n) => `¥${n.toLocaleString("ja-JP")}`;

export const priceText = (it) =>
  it.kind === "drop" && it.before
    ? `${yen(it.before)} → **${yen(it.price)}**(${Math.round((1 - it.price / it.before) * 100)}%OFF)`
    : yen(it.price);

// Discord に送る内容(1投稿あたり埋め込み10件まで)
export function discordPayloads(items, label) {
  const counts = [
    ["new", "新規出品"],
    ["drop", "値下げ"],
  ]
    .map(([k, name]) => [name, items.filter((it) => it.kind === k).length])
    .filter(([, n]) => n)
    .map(([name, n]) => `${name} ${n}件`)
    .join(" / ");
  const payloads = [];
  for (let i = 0; i < items.length; i += 10) {
    payloads.push({
      username: "ゲームトレード新着",
      allowed_mentions: { parse: [] },
      content: i === 0 ? `🆕 ${label ?? "新着"}: ${counts}` : undefined,
      embeds: items.slice(i, i + 10).map((it) => ({
        title: `${it.kind === "drop" ? "【値下げ】" : "【新規】"}${it.name}`.slice(0, 250),
        url: it.url,
        description: [priceText(it), ...it.info].join("\n").slice(0, 4000),
        color: it.kind === "drop" ? 0xdc2626 : 0x2563eb,
        thumbnail: it.image ? { url: it.image } : undefined,
      })),
    });
  }
  return payloads;
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// 連続で取りに行くと 403 が返ることがあるので、間を空けて数回やり直す
async function fetchPage(fetchImpl, url, sleep) {
  for (let attempt = 0; ; attempt++) {
    const res = await fetchImpl(url, {
      headers: {
        "user-agent": UA,
        accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "ja,en-US;q=0.9,en;q=0.8",
      },
      signal: AbortSignal.timeout(20000),
    });
    if (res.ok) return res.text();
    if (attempt >= 2 || ![403, 429, 500, 502, 503, 504].includes(res.status)) {
      throw new Error(`${res.status} ${res.statusText}: ${url}`);
    }
    await sleep(3000 * 2 ** attempt);
  }
}

// 1回分のチェック。state は前回の状態(無ければ初回=記録だけ)。
// 返り値: { state: 次の状態, hits: 通知する出品, total: 取得した件数, notified: 送ったか }
// 監視する一覧の各ページのURL
export function pageUrls(config) {
  const base = new URL(config.url);
  base.searchParams.delete("page");
  return Array.from({ length: config.pages ?? 3 }, (_, i) => {
    const url = new URL(base);
    url.searchParams.set("page", String(i + 1));
    return url.href;
  });
}

// 一覧の各ページを取ってくる(間を空けて)
export async function fetchPages(config, { fetchImpl = fetch, sleep = wait } = {}) {
  const pages = [];
  for (const url of pageUrls(config)) {
    if (pages.length) await sleep(2000);
    pages.push(await fetchPage(fetchImpl, url, sleep));
  }
  return pages;
}

// 1回分のチェック。state は前回の状態(無ければ初回=記録だけ)。
// pages(取得済みの一覧ページの HTML)を渡すとそれを使い、無ければ自分で取りに行く。
// 返り値: { state: 次の状態, hits: 通知する出品, total: 取得した件数, first: 初回か, notified: 送ったか }
export async function runCheck({ config, state, webhook, pages, fetchImpl = fetch, sleep = wait, dryRun = false }) {
  const base = new URL(config.url);
  // サイト側が価格の絞り込みを無視することがあるので、こちらでも絞り込む
  const low = Number(base.searchParams.get("low_price")) || 0;
  const high = Number(base.searchParams.get("high_price")) || Infinity;

  pages ??= await fetchPages(config, { fetchImpl, sleep });
  const found = new Map();
  for (const html of pages) for (const it of parseExhibits(html, base.origin)) found.set(it.id, it);
  if (found.size === 0) throw new Error("出品を1件も読み取れませんでした(サイトの構造が変わった可能性)");

  const all = [...found.values()];
  const prev = state?.maxId ? state : null; // 古い形式の状態は初回扱い
  const hits = prev ? pick(all, low, high, prev) : [];
  let notified = false;
  if (!dryRun && hits.length && webhook) {
    for (const payload of discordPayloads(hits, config.label)) {
      const res = await fetchImpl(webhook, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Discord への送信に失敗: ${res.status} ${await res.text()}`);
      await sleep(1000);
    }
    notified = true;
  }
  return { state: nextState(prev, all), hits, total: all.length, first: !prev, notified };
}
