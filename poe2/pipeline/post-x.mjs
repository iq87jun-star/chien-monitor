// フェーズ2-B: X(Twitter)速報bot
// 新しいパッチノート検知時と新記事公開時に自動ポストする。
// X APIの認証情報が未設定なら何もせず正常終了する。
// 必要な環境変数: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { SITE_DIR, CONTENT_DIR } from "./config.mjs";

const SITE_URL = "https://game-souba.com/poe2/";
const MAX_POSTS_PER_RUN = 2;

// --- OAuth 1.0a 署名(依存ライブラリなし) ---
const pctEncode = (s) =>
  encodeURIComponent(s).replace(
    /[!'()*]/g,
    (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase(),
  );

function oauth1Header(method, url, creds) {
  const oauth = {
    oauth_consumer_key: creds.apiKey,
    oauth_nonce: crypto.randomBytes(16).toString("hex"),
    oauth_signature_method: "HMAC-SHA1",
    oauth_timestamp: String(Math.floor(Date.now() / 1000)),
    oauth_token: creds.accessToken,
    oauth_version: "1.0",
  };
  const paramString = Object.keys(oauth)
    .sort()
    .map((k) => `${pctEncode(k)}=${pctEncode(oauth[k])}`)
    .join("&");
  const baseString = [method, pctEncode(url), pctEncode(paramString)].join("&");
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

async function postTweet(text, creds) {
  const url = "https://api.twitter.com/2/tweets";
  const res = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: oauth1Header("POST", url, creds),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ text }),
  });
  const body = await res.text();
  if (!res.ok) throw new Error(`tweet failed: HTTP ${res.status} ${body.slice(0, 200)}`);
  return JSON.parse(body);
}

async function readJson(file, fallback = null) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return fallback;
  }
}

export async function postToX() {
  const { X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET } = process.env;
  if (!X_API_KEY || !X_API_SECRET || !X_ACCESS_TOKEN || !X_ACCESS_TOKEN_SECRET) {
    console.log("x-bot: X API credentials not set — skipping");
    return;
  }
  const creds = {
    apiKey: X_API_KEY,
    apiSecret: X_API_SECRET,
    accessToken: X_ACCESS_TOKEN,
    accessSecret: X_ACCESS_TOKEN_SECRET,
  };

  const news = await readJson(path.join(SITE_DIR, "news.json"), { items: [] });
  const articles = (await readJson(path.join(CONTENT_DIR, "articles.json"), { articles: [] }))
    .articles;
  const statePath = path.join(SITE_DIR, "posted.json");
  const state = await readJson(statePath, { newsGids: [], articleIds: [] });

  const queue = [];

  // 1. 未ポストのパッチ関連ニュース(新しい順に1件だけ)
  const newPatch = news.items.find((n) => n.isPatch && !state.newsGids.includes(n.gid));
  if (newPatch) {
    queue.push({
      kind: "news",
      key: newPatch.gid,
      text: `【PoE2 パッチ情報】\n${newPatch.title}\n\n公式: ${newPatch.url}\n日本語の相場への影響は当サイトで自動解説します→ ${SITE_URL}\n#PoE2 #PathofExile2`,
    });
  }

  // 2. 未ポストの新着記事(最新1件だけ)
  const newArticle = articles.find((a) => !state.articleIds.includes(a.id));
  if (newArticle) {
    queue.push({
      kind: "article",
      key: newArticle.id,
      text: `📊 ${newArticle.title}\n\n${newArticle.summary.slice(0, 80)}…\n\n全文→ ${SITE_URL}\n#PoE2 #PathofExile2`,
    });
  }

  if (queue.length === 0) {
    console.log("x-bot: nothing new to post");
    return;
  }

  for (const item of queue.slice(0, MAX_POSTS_PER_RUN)) {
    try {
      const result = await postTweet(item.text, creds);
      console.log(`x-bot: posted ${item.kind} (tweet id: ${result.data?.id})`);
      if (item.kind === "news") state.newsGids.push(item.key);
      else state.articleIds.push(item.key);
    } catch (err) {
      // 認証エラーや制限は警告に留め、他の処理を巻き添えにしない
      console.warn(`x-bot: post failed — ${err.message}`);
      break;
    }
  }

  // 状態は直近200件だけ保持
  state.newsGids = state.newsGids.slice(-200);
  state.articleIds = state.articleIds.slice(-200);
  await fs.writeFile(statePath, JSON.stringify(state, null, 1));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  postToX().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
