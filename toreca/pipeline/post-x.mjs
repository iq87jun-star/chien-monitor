// X(Twitter)速報bot
// 急騰カードの検知時と新しいAI記事の公開時に自動ポストする。
// 認証情報が未設定なら何もせず正常終了する。
// 必要な環境変数: TORECA_X_API_KEY, TORECA_X_API_SECRET(toreca専用アプリのキー。
//                未設定ならゲーム系ボット共通の X_API_KEY / X_API_SECRET を使う)、
//                TORECA_X_ACCESS_TOKEN, TORECA_X_ACCESS_TOKEN_SECRET(bot垢のトークン)
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { SITE_DIR, CONTENT_DIR, SIGNIFICANT_CHANGE_PCT } from "./config.mjs";

const SITE_URL = "https://pokeca-kaigai.com/";
// GAでX bot経由の流入を判別するためのUTMパラメータ(t.coで短縮されるため文字数コストなし)
const UTM = (campaign) => `?utm_source=x&utm_medium=social&utm_campaign=${campaign}`;
const MAX_POSTS_PER_RUN = 2;
const HASHTAGS = "#ポケカ #ポケモンカード";

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
  // toreca専用アプリのキーを優先し、無ければゲーム系ボット共通のアプリキーを使う。
  // Access Tokenは「apiKey側のアプリで発行されたもの」でないと認証が通らない点に注意。
  const apiKey = process.env.TORECA_X_API_KEY || process.env.X_API_KEY;
  const apiSecret = process.env.TORECA_X_API_SECRET || process.env.X_API_SECRET;
  const { TORECA_X_ACCESS_TOKEN, TORECA_X_ACCESS_TOKEN_SECRET } = process.env;
  if (!apiKey || !apiSecret || !TORECA_X_ACCESS_TOKEN || !TORECA_X_ACCESS_TOKEN_SECRET) {
    console.log("x-bot: X API credentials not set — skipping");
    return;
  }
  const creds = {
    apiKey,
    apiSecret,
    accessToken: TORECA_X_ACCESS_TOKEN,
    accessSecret: TORECA_X_ACCESS_TOKEN_SECRET,
  };

  const economy = await readJson(path.join(SITE_DIR, "economy.json"), {});
  const articles = (await readJson(path.join(CONTENT_DIR, "articles.json"), { articles: [] }))
    .articles;
  const statePath = path.join(SITE_DIR, "posted.json");
  const state = await readJson(statePath, { cardIds: [], articleIds: [] });

  const queue = [];

  // 1. 未ポストの急騰カード(閾値超えの上昇率トップ1件だけ)
  const spike = (economy.gainers ?? []).find(
    (c) => c.change7d >= SIGNIFICANT_CHANGE_PCT && !state.cardIds.includes(c.id),
  );
  if (spike) {
    const jpy = spike.jpy != null ? `約${Math.round(spike.jpy).toLocaleString("ja-JP")}円` : "";
    queue.push({
      kind: "spike",
      key: spike.id,
      text: `📈【ポケカ海外相場 急騰】\n${spike.name}(${spike.set})\n€${spike.eur}(${jpy})・7日平均比 +${spike.change7d}%\n\n海外市場(Cardmarket)の値動きを毎日自動集計→ ${SITE_URL}${UTM("spike")}\n${HASHTAGS}`,
    });
  }

  // 2. 未ポストの新着記事(最新1件だけ)
  const newArticle = articles.find((a) => !state.articleIds.includes(a.id));
  if (newArticle) {
    queue.push({
      kind: "article",
      key: newArticle.id,
      // 記事の個別ページへ直リンク(OGPカード表示でCTRを上げる)
      text: `📊 ${newArticle.title}\n\n${newArticle.summary.slice(0, 80)}…\n\n全文→ ${SITE_URL}articles/${newArticle.id}/${UTM("article")}\n${HASHTAGS}`,
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
      if (item.kind === "spike") state.cardIds.push(item.key);
      else state.articleIds.push(item.key);
    } catch (err) {
      // 認証エラーや制限は警告に留め、他の処理を巻き添えにしない
      console.warn(`x-bot: post failed — ${err.message}`);
      break;
    }
  }

  // 状態は直近200件だけ保持
  state.cardIds = state.cardIds.slice(-200);
  state.articleIds = state.articleIds.slice(-200);
  await fs.writeFile(statePath, JSON.stringify(state, null, 1));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  postToX().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
