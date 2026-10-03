// X(Twitter)投稿の選択削除ツール
// bot垢のタイムラインを遡り、指定サイトURLへのリンクを含む投稿だけを削除する。
// 既定はドライラン(対象を一覧表示するだけ)。DRY_RUN=false で実際に削除する。
//
// 必要な環境変数: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
// 任意:
//   MATCH_URL  … このURLを含む投稿を削除対象にする(既定: https://game-souba.com/poe2/)
//   TWEET_IDS  … カンマ区切りの投稿ID。指定時はタイムラインを読まずにこのIDだけ削除する
//   DRY_RUN    … "false" のときだけ削除を実行
import crypto from "node:crypto";

const API = "https://api.twitter.com/2";
const MATCH_URL = (process.env.MATCH_URL || "https://game-souba.com/poe2/").trim();
const DRY_RUN = process.env.DRY_RUN !== "false";
const TWEET_IDS = (process.env.TWEET_IDS || "")
  .split(/[\s,]+/)
  .map((s) => s.trim())
  .filter(Boolean);

// --- OAuth 1.0a 署名(クエリパラメータも署名に含める) ---
const pctEncode = (s) =>
  encodeURIComponent(s).replace(
    /[!'()*]/g,
    (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase(),
  );

function oauth1Header(method, fullUrl, creds) {
  const u = new URL(fullUrl);
  const baseUrl = `${u.origin}${u.pathname}`;
  const oauth = {
    oauth_consumer_key: creds.apiKey,
    oauth_nonce: crypto.randomBytes(16).toString("hex"),
    oauth_signature_method: "HMAC-SHA1",
    oauth_timestamp: String(Math.floor(Date.now() / 1000)),
    oauth_token: creds.accessToken,
    oauth_version: "1.0",
  };
  const params = [
    ...Object.entries(oauth),
    ...[...u.searchParams.entries()],
  ].map(([k, v]) => [pctEncode(k), pctEncode(v)]);
  params.sort((a, b) => (a[0] === b[0] ? (a[1] < b[1] ? -1 : 1) : a[0] < b[0] ? -1 : 1));
  const paramString = params.map(([k, v]) => `${k}=${v}`).join("&");
  const baseString = [method, pctEncode(baseUrl), pctEncode(paramString)].join("&");
  const signingKey = `${pctEncode(creds.apiSecret)}&${pctEncode(creds.accessSecret)}`;
  oauth.oauth_signature = crypto
    .createHmac("sha1", signingKey)
    .update(baseString)
    .digest("base64");
  return (
    "OAuth " +
    Object.keys(oauth)
      .sort()
      .map((k) => `${pctEncode(k)}="${pctEncode(oauth[k])}"`)
      .join(", ")
  );
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// レート制限(429)に当たったらリセット時刻まで待って再試行する
async function xFetch(method, url, creds) {
  for (;;) {
    const res = await fetch(url, {
      method,
      headers: { Authorization: oauth1Header(method, url, creds) },
    });
    if (res.status === 429) {
      const reset = Number(res.headers.get("x-rate-limit-reset")) * 1000;
      const waitMs = Math.max(reset - Date.now(), 0) + 5000 || 15 * 60 * 1000;
      console.log(`rate limited — waiting ${Math.ceil(waitMs / 1000)}s`);
      await sleep(waitMs);
      continue;
    }
    const body = await res.text();
    if (!res.ok) throw new Error(`${method} ${url} failed: HTTP ${res.status} ${body.slice(0, 300)}`);
    return body ? JSON.parse(body) : {};
  }
}

// 投稿本文のURLは t.co に短縮されるので、展開後URL(entities)で判定する
function matches(tweet) {
  const urls = (tweet.entities?.urls ?? []).flatMap((u) => [u.expanded_url, u.unwound_url]);
  return [tweet.text, ...urls].some((s) => typeof s === "string" && s.includes(MATCH_URL));
}

async function findTargets(creds) {
  const me = await xFetch("GET", `${API}/users/me`, creds);
  console.log(`account: @${me.data.username} (id ${me.data.id})`);
  const targets = [];
  let scanned = 0;
  let token;
  // APIで遡れるのは直近3200件まで
  do {
    const q = new URLSearchParams({
      max_results: "100",
      exclude: "retweets",
      "tweet.fields": "created_at,entities",
    });
    if (token) q.set("pagination_token", token);
    const page = await xFetch("GET", `${API}/users/${me.data.id}/tweets?${q}`, creds);
    for (const t of page.data ?? []) {
      scanned++;
      if (matches(t)) targets.push(t);
    }
    token = page.meta?.next_token;
  } while (token);
  console.log(`scanned ${scanned} posts, ${targets.length} match "${MATCH_URL}"`);
  return targets;
}

async function main() {
  const creds = {
    apiKey: process.env.X_API_KEY,
    apiSecret: process.env.X_API_SECRET,
    accessToken: process.env.X_ACCESS_TOKEN,
    accessSecret: process.env.X_ACCESS_TOKEN_SECRET,
  };
  if (Object.values(creds).some((v) => !v)) {
    throw new Error("X API credentials not set (X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET)");
  }

  const targets = TWEET_IDS.length
    ? TWEET_IDS.map((id) => ({ id, text: "(ID指定)" }))
    : await findTargets(creds);

  for (const t of targets) {
    console.log(`- ${t.id} ${t.created_at ?? ""} ${t.text.replace(/\s+/g, " ").slice(0, 60)}`);
  }
  if (DRY_RUN) {
    console.log(`\nDRY RUN: ${targets.length} posts would be deleted. Re-run with dry_run=false to delete.`);
    return;
  }

  let deleted = 0;
  for (const t of targets) {
    try {
      const r = await xFetch("DELETE", `${API}/tweets/${t.id}`, creds);
      if (r.data?.deleted) deleted++;
      console.log(`deleted ${t.id}`);
    } catch (err) {
      console.warn(`failed ${t.id}: ${err.message}`);
    }
  }
  console.log(`\ndeleted ${deleted}/${targets.length} posts`);
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
