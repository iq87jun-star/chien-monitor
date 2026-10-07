// ゲームトレード(gametrade.jp)の出品一覧を見て、新規出品と値下げを Discord に通知する処理の本体。
// 実行環境に依存しない(Cloudflare Worker と手元の Node の両方から使う)。

const MAX_PRICES = 5000;
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36";

export const decode = (s) =>
  s
    .replace(/&quot;/g, '"')
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&#x([0-9a-f]+);/gi, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&yen;/g, "¥")
    .replace(/&nbsp;/g, " ")
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
      // 取引が終わった出品(SOLD)も一覧に残る。売れたアカウントの記録(sold.js)で使う
      sold: block.includes("sales-done"),
    });
  }
  return items;
}

// ゲームクラブ(gameclub.jp)の一覧ページから出品を取り出す(販売済みは除く)
export function parseGameclub(html, origin) {
  const items = [];
  for (const block of html.split('<div class="item-row ').slice(1)) {
    if (block.includes("product-statuses sold")) continue;
    const id = /href="\/[\w-]+\/(\d+)"/.exec(block)?.[1];
    const name = /<h3>\s*<a [^>]*>([\s\S]*?)<\/a>/.exec(block)?.[1];
    const price = /class="price">([^<]+)</.exec(block)?.[1];
    if (!id || !name || !price) continue;
    const href = /<h3>\s*<a href="([^"]+)"/.exec(block)?.[1] ?? "";
    const img = /<img\s+src="([^"]+)"/.exec(block)?.[1];
    const date = /fa-history"><\/i>([^<]+)</.exec(block)?.[1]?.trim();
    const info = [...block.matchAll(/<div class="item-title">([\s\S]*?)<\/div>\s*<div class="item-content">([\s\S]*?)<\/div>/g)].map(
      (m) => `${decode(m[1]).trim()}：${decode(m[2]).trim()}`,
    );
    const type = /account-type">([^<]+)</.exec(block)?.[1]?.trim();
    items.push({
      id,
      name: decode(name).trim(),
      price: Number(decode(price).replace(/[^\d]/g, "")),
      url: new URL(href || `/${id}`, origin).href,
      image: img ?? null,
      previousPrice: null,
      info: [type && `種類：${type}`, date && `出品・更新：${date}`, ...info].filter(Boolean),
    });
  }
  return items;
}

// 通知する出品を決める。
//   新規出品: 前回までに見た最大の出品IDより新しいID(出品IDは作成順に増える)
//   値下げ  : 記録した価格より下がった / 記録がなく一覧に「元の価格」が出ている
//   価格変更: fullRange(価格帯の出品を毎回すべて見ているサイト)で、記録のない古いIDが価格帯に現れた
//            = 価格帯の外から価格を変えて入ってきた
// 古い出品が説明文の編集などで一覧の上に来ただけのものは通知しない
export function pick(all, low, high, state, { fullRange = false } = {}) {
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
    } else if (fullRange) {
      out.push({ ...it, kind: "changed" });
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
const KINDS = {
  new: { name: "新規出品", tag: "【新規】", color: 0x2563eb },
  drop: { name: "値下げ", tag: "【値下げ】", color: 0xdc2626 },
  changed: { name: "価格変更で該当", tag: "【価格変更】", color: 0xd97706 },
};

// Discord は https 以外(相対パス・data: など)の URL を含む埋め込みを 400 で拒否する
const httpsUrl = (u) => (typeof u === "string" && /^https:\/\/[^\s"<>]+$/.test(u) && u.length < 2000 ? u : undefined);

export function discordPayloads(items, label, username = "ゲームトレード新着") {
  const counts = Object.entries(KINDS)
    .map(([k, { name }]) => [name, items.filter((it) => it.kind === k).length])
    .filter(([, n]) => n)
    .map(([name, n]) => `${name} ${n}件`)
    .join(" / ");
  const payloads = [];
  for (let i = 0; i < items.length; i += 10) {
    payloads.push({
      username,
      allowed_mentions: { parse: [] },
      content: i === 0 ? `🆕 ${label ?? "新着"}: ${counts}` : undefined,
      embeds: items.slice(i, i + 10).map((it) => ({
        title: `${KINDS[it.kind].tag}${it.name}`.slice(0, 250),
        url: httpsUrl(it.url),
        description: [priceText(it), ...it.info].join("\n").slice(0, 4000),
        color: KINDS[it.kind].color,
        thumbnail: httpsUrl(it.image) ? { url: it.image } : undefined,
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

// サイトごとの違い: 解析・価格帯の URL パラメータ・価格帯の出品を毎回すべて見ているか
const SITES = {
  gametrade: { parse: parseExhibits, low: "low_price", high: "high_price", fullRange: false },
  // ゲームクラブは価格帯の絞り込みが効き、該当は数ページなので全ページを送ってもらう
  gameclub: { parse: parseGameclub, low: "search[priceMin]", high: "search[priceMax]", fullRange: true },
};

// 1回分のチェック。state は前回の状態(無ければ初回=記録だけ)。
// pages(取得済みの一覧ページの HTML)を渡すとそれを使い、無ければ自分で取りに行く。
// 返り値: { state: 次の状態, hits: 通知する出品, total: 取得した件数, first: 初回か, notified: 送ったか,
//          skipped: Discord に拒否されて送れなかった出品 }
// complete === false: 価格帯の全ページは読めていない(ページ数の上限で打ち切った)。fullRange の前提が崩れるので
// 「記録のない古い出品 = 価格変更」の判定をしない
export async function runCheck({ config, state, webhook, pages, complete, fetchImpl = fetch, sleep = wait, dryRun = false }) {
  const base = new URL(config.url);
  const site = SITES[config.site ?? "gametrade"];
  // サイト側が価格の絞り込みを無視することがあるので、こちらでも絞り込む
  const low = Number(base.searchParams.get(site.low)) || 0;
  const high = Number(base.searchParams.get(site.high)) || Infinity;

  pages ??= await fetchPages(config, { fetchImpl, sleep });
  const found = new Map();
  for (const html of pages) for (const it of site.parse(html, base.origin)) found.set(it.id, it);
  if (found.size === 0) throw new Error("出品を1件も読み取れませんでした(サイトの構造が変わった可能性)");

  const all = [...found.values()];
  const prev = state?.maxId ? state : null; // 古い形式の状態は初回扱い
  const fullRange = site.fullRange && complete !== false;
  const hits = prev ? pick(all, low, high, prev, { fullRange }) : [];
  let notified = false;
  const skipped = [];
  if (!dryRun && hits.length && webhook) {
    const post = async (payload) => {
      for (let attempt = 0; ; attempt++) {
        const res = await fetchImpl(webhook, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res.status === 429 && attempt < 2) {
          // 送りすぎ: Discord が指定する秒数だけ待ってやり直す
          const wait = Number((await res.json().catch(() => ({}))).retry_after) || 2;
          await sleep(Math.min(wait, 30) * 1000);
          continue;
        }
        return { ok: res.ok, status: res.status, text: res.ok ? "" : await res.text() };
      }
    };
    for (const payload of discordPayloads(hits, config.label, config.username)) {
      const r = await post(payload);
      if (r.ok) {
        notified = true;
      } else if (r.status === 400) {
        // どれか1件の形が Discord に拒否された: 1件ずつ送り直し、それでも駄目なら画像とリンクを外し、
        // なお駄目なものだけ飛ばす(1件のせいで全部が届かないことがないように)
        let content = payload.content;
        for (const embed of payload.embeds) {
          let one = await post({ ...payload, content, embeds: [embed] });
          if (!one.ok && one.status === 400) {
            const { thumbnail, url, ...plain } = embed;
            one = await post({ ...payload, content, embeds: [plain] });
          }
          if (one.ok) {
            notified = true;
            content = undefined;
          } else if (one.status === 400) {
            skipped.push({ title: embed.title, error: one.text.slice(0, 300) });
          } else {
            throw new Error(`Discord への送信に失敗: ${one.status} ${one.text}`);
          }
          await sleep(1000);
        }
      } else {
        throw new Error(`Discord への送信に失敗: ${r.status} ${r.text}`);
      }
      await sleep(1000);
    }
  }
  // 確認用: 読んだページ数・価格帯に入っていた件数・読んだ出品の最安と最高(サイト側の絞り込みが効いているか)
  const prices = all.map((it) => it.price);
  const summary = {
    pages: pages.length,
    complete: complete ?? null,
    inRange: all.filter((it) => it.price >= low && it.price <= high).length,
    priceMin: Math.min(...prices),
    priceMax: Math.max(...prices),
  };
  return { state: nextState(prev, all), hits, total: all.length, first: !prev, notified, skipped, summary };
}
