// タルコフ相場モニター X速報bot
// 新しいAI記事の公開時に自動ポストする。認証情報が未設定なら何もせず正常終了する。
// 必要な環境変数: X_API_KEY, X_API_SECRET(アプリ共通), TARKOV_X_ACCESS_TOKEN, TARKOV_X_ACCESS_TOKEN_SECRET
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { SITE_DIR, CONTENT_DIR } from "./config.mjs";

const SITE_URL = "https://game-souba.com/tarkov/";
const MAX_POSTS_PER_RUN = 1;

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
  const { X_API_KEY, X_API_SECRET, TARKOV_X_ACCESS_TOKEN, TARKOV_X_ACCESS_TOKEN_SECRET } =
    process.env;
  if (!X_API_KEY || !X_API_SECRET || !TARKOV_X_ACCESS_TOKEN || !TARKOV_X_ACCESS_TOKEN_SECRET) {
    console.log("x-bot: X API credentials not set — skipping");
    return;
  }
  const creds = {
    apiKey: X_API_KEY,
    apiSecret: X_API_SECRET,
    accessToken: TARKOV_X_ACCESS_TOKEN,
    accessSecret: TARKOV_X_ACCESS_TOKEN_SECRET,
  };

  const articles = (await readJson(path.join(CONTENT_DIR, "articles.json"), { articles: [] }))
    .articles;
  const statePath = path.join(SITE_DIR, "posted.json");
  const state = await readJson(statePath, { articleIds: [] });

  const newArticle = articles.find((a) => !state.articleIds.includes(a.id));
  if (!newArticle) {
    console.log("x-bot: nothing new to post");
    return;
  }

  const text = `📊 ${newArticle.title}\n\n${newArticle.summary.slice(0, 80)}…\n\n全文→ ${SITE_URL}\n#タルコフ #EFT`;
  try {
    const result = await postTweet(text, creds);
    console.log(`x-bot: posted article (tweet id: ${result.data?.id})`);
    state.articleIds.push(newArticle.id);
    state.articleIds = state.articleIds.slice(-200);
    await fs.writeFile(statePath, JSON.stringify(state, null, 1));
  } catch (err) {
    console.warn(`x-bot: post failed — ${err.message}`);
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  postToX().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
