// X(Twitter)速報bot
// 急騰アイテムの検知時と新しいAI記事の公開時に自動ポストする。
// 認証情報が未設定なら何もせず正常終了する。
// 必要な環境変数: OPCG_X_API_KEY, OPCG_X_API_SECRET(ワンピカbot専用アプリのキー。
//                未設定なら共通の X_API_KEY / X_API_SECRET を使う)、
//                OPCG_X_ACCESS_TOKEN, OPCG_X_ACCESS_TOKEN_SECRET(bot垢のトークン)
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { SITE_DIR, CONTENT_DIR, SIGNIFICANT_CHANGE_PCT } from "./config.mjs";

const SITE_URL = "https://opcg-souba.com/";
const MAX_POSTS_PER_RUN = 2;
const HASHTAGS = "#ワンピカ #ワンピースカード";

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
  // ワンピカbot専用アプリのキーを優先し、無ければ共通のアプリキーを使う。
  // Access Tokenは「apiKey側のアプリで発行されたもの」でないと認証が通らない点に注意。
  const apiKey = process.env.OPCG_X_API_KEY || process.env.X_API_KEY;
  const apiSecret = process.env.OPCG_X_API_SECRET || process.env.X_API_SECRET;
  const { OPCG_X_ACCESS_TOKEN, OPCG_X_ACCESS_TOKEN_SECRET } = process.env;
  if (!apiKey || !apiSecret || !OPCG_X_ACCESS_TOKEN || !OPCG_X_ACCESS_TOKEN_SECRET) {
    console.log("x-bot: X API credentials not set — skipping");
    return;
  }
  const creds = {
    apiKey,
    apiSecret,
    accessToken: OPCG_X_ACCESS_TOKEN,
    accessSecret: OPCG_X_ACCESS_TOKEN_SECRET,
  };

  const economy = await readJson(path.join(SITE_DIR, "economy.json"), {});
  const articles = (await readJson(path.join(CONTENT_DIR, "articles.json"), { articles: [] }))
    .articles;
  const statePath = path.join(SITE_DIR, "posted.json");
  const state = await readJson(statePath, { itemIds: [], articleIds: [] });

  const queue = [];

  // 1. 未ポストの急騰アイテム(閾値超えの上昇率トップ1件だけ)
  const spike = (economy.gainers ?? []).find(
    (c) => c.change7d >= SIGNIFICANT_CHANGE_PCT && !state.itemIds.includes(c.id),
  );
  if (spike) {
    queue.push({
      kind: "spike",
      key: spike.id,
      text: `📈【ワンピカ相場 急騰】\n${spike.name}\n出品中央値 ${spike.median.toLocaleString("ja-JP")}円・7日前比 +${spike.change7d}%(最安 ${spike.low.toLocaleString("ja-JP")}円)\n\n未開封BOX・高額シングルの国内相場を毎日自動集計→ ${SITE_URL}\n${HASHTAGS}`,
    });
  }

  // 2. 未ポストの新着記事(最新1件だけ)
  const newArticle = articles.find((a) => !state.articleIds.includes(a.id));
  if (newArticle) {
    queue.push({
      kind: "article",
      key: newArticle.id,
      // 記事の個別ページへ直リンク(OGPカード表示でCTRを上げる)
      text: `📊 ${newArticle.title}\n\n${newArticle.summary.slice(0, 80)}…\n\n全文→ ${SITE_URL}articles/${newArticle.id}/\n${HASHTAGS}`,
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
      if (item.kind === "spike") state.itemIds.push(item.key);
      else state.articleIds.push(item.key);
    } catch (err) {
      // 認証エラーや制限は警告に留め、他の処理を巻き添えにしない
      console.warn(`x-bot: post failed — ${err.message}`);
      break;
    }
  }

  // 状態は直近200件だけ保持
  state.itemIds = state.itemIds.slice(-200);
  state.articleIds = state.articleIds.slice(-200);
  await fs.writeFile(statePath, JSON.stringify(state, null, 1));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  postToX().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
