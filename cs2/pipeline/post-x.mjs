// CS2スキン相場モニター X速報bot
// 新しいAI記事の公開時とデイリー急騰ランキングを自動ポストする。認証情報が未設定なら何もせず正常終了する。
// 必要な環境変数: X_API_KEY, X_API_SECRET(アプリ共通), CS2_X_ACCESS_TOKEN, CS2_X_ACCESS_TOKEN_SECRET
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { SITE_DIR, CONTENT_DIR } from "./config.mjs";

const SITE_URL = "https://game-souba.com/cs2/";
const MAX_POSTS_PER_RUN = 2;
const HASHTAGS = "#CS2 #CS2スキン";

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
  const { X_API_KEY, X_API_SECRET, CS2_X_ACCESS_TOKEN, CS2_X_ACCESS_TOKEN_SECRET } = process.env;
  if (!X_API_KEY || !X_API_SECRET || !CS2_X_ACCESS_TOKEN || !CS2_X_ACCESS_TOKEN_SECRET) {
    console.log("x-bot: X API credentials not set — skipping");
    return;
  }
  const creds = {
    apiKey: X_API_KEY,
    apiSecret: X_API_SECRET,
    accessToken: CS2_X_ACCESS_TOKEN,
    accessSecret: CS2_X_ACCESS_TOKEN_SECRET,
  };

  const economy = await readJson(path.join(SITE_DIR, "economy.json"), null);
  const articles = (await readJson(path.join(CONTENT_DIR, "articles.json"), { articles: [] }))
    .articles;
  const statePath = path.join(SITE_DIR, "posted.json");
  const state = await readJson(statePath, { articleIds: [] });

  const queue = [];

  // 1. 未ポストの新着記事(最新1件だけ)
  const newArticle = articles.find((a) => !state.articleIds.includes(a.id));
  if (newArticle) {
    queue.push({
      kind: "article",
      key: newArticle.id,
      text: `📊 ${newArticle.title}\n\n${newArticle.summary.slice(0, 80)}…\n\n全文→ ${SITE_URL}\n${HASHTAGS}`,
    });
  }

  // 2. デイリー急騰ランキング(日本時間で1日1回・データ取得できている時だけ)
  const todayJst = new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
  const top3 =
    economy?.available !== false
      ? (economy?.gainers ?? []).filter((g) => g.change7d > 0).slice(0, 3)
      : [];
  if (state.lastRankingDate !== todayJst && top3.length === 3) {
    const lines = top3
      .map((g, i) => `${i + 1}. ${g.name} +${g.change7d}%`)
      .join("\n");
    queue.push({
      kind: "ranking",
      key: todayJst,
      text: `📈 CS2スキン本日の急騰TOP3\n\n${lines}\n\n※7日変動率・毎日自動集計(Skinport出品価格)\n詳細→ ${SITE_URL}\n${HASHTAGS}`,
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
      if (item.kind === "ranking") state.lastRankingDate = item.key;
      else state.articleIds.push(item.key);
    } catch (err) {
      console.warn(`x-bot: post failed — ${err.message}`);
      break;
    }
  }

  state.articleIds = state.articleIds.slice(-200);
  await fs.writeFile(statePath, JSON.stringify(state, null, 1));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  postToX().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
