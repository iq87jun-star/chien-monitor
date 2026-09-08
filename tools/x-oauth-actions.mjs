#!/usr/bin/env node
/**
 * GitHub Actions 上で X の OAuth 1.0a 3-legged 認証を行い、
 * 取得したアクセストークンを GitHub Secrets に直接登録する。
 *
 * 値(API キー・トークン)はワークフローの中だけで扱い、ログには出さない。
 *
 * 流れ:
 *   1. request_token を取得し、認証 URL をログに表示
 *   2. 人が Bot アカウントでその URL を開き「連携アプリを認証」を押す
 *      → コールバック先の URL に oauth_verifier が付く
 *   3. その verifier を、指定 Issue にコメントで投稿する:
 *        verifier <oauth_token> <oauth_verifier>
 *   4. このスクリプトが Issue コメントをポーリングして verifier を受け取り、
 *      access_token に交換 → gh secret set で登録 → コメントを削除
 *
 * 必要な環境変数:
 *   X_API_KEY, X_API_SECRET   … 共有アプリのコンシューマーキー
 *   GH_PAT                    … Secrets を書ける PAT(repo スコープ)
 *   GITHUB_TOKEN              … Issue コメントの読み取り/削除
 *   GITHUB_REPOSITORY         … owner/repo(Actions が自動設定)
 *   X_CALLBACK_URL            … 省略時は既定値
 *
 * 入力ファイル tools/x-oauth-request.json:
 *   { "site": "cosme", "issue": 49 }
 */
import crypto from "node:crypto";
import fs from "node:fs/promises";
import { spawn } from "node:child_process";

const SITES = {
  cosme:  "ilopesalshswinx",
  pokeca: "CchaliemahI",
  opcg:   "MissSalshaWinxs",
  duema:  "IfyblinkOffical",
  gunpla: "Anti_SalshaNyet",
  duel:   null,
  ff14:   "meruru_prop",
  tarkov: "Milky8150983725",
};

const API_KEY = process.env.X_API_KEY || "";
const API_SECRET = process.env.X_API_SECRET || "";
const GH_PAT = process.env.GH_PAT || "";
const GITHUB_TOKEN = process.env.GITHUB_TOKEN || "";
const REPO = process.env.GITHUB_REPOSITORY || "";
const CALLBACK_URL = process.env.X_CALLBACK_URL || "https://iq87jun-star.github.io/chien-monitor/";
const POLL_MS = 15_000;
const POLL_MAX_MIN = Number(process.env.POLL_MAX_MIN || 20);

const req = JSON.parse(await fs.readFile("tools/x-oauth-request.json", "utf8"));
const site = String(req.site || "").toLowerCase();
const issue = Number(req.issue);

const fail = (msg) => { console.log("❌ " + msg); process.exit(1); };

if (!Object.prototype.hasOwnProperty.call(SITES, site)) fail(`site が不正です: ${site}`);
if (!issue) fail("issue 番号が指定されていません");
if (!API_KEY || !API_SECRET) fail("X_API_KEY / X_API_SECRET が未設定です");
if (!GH_PAT) fail("GH_PAT が未設定です");
if (!GITHUB_TOKEN || !REPO) fail("GITHUB_TOKEN / GITHUB_REPOSITORY が未設定です");

const enc = (s) =>
  encodeURIComponent(s).replace(/[!*'()]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase());

function authHeader(method, url, extra, tokenSecret = "") {
  const o = {
    oauth_consumer_key: API_KEY,
    oauth_nonce: crypto.randomBytes(16).toString("hex"),
    oauth_signature_method: "HMAC-SHA1",
    oauth_timestamp: String(Math.floor(Date.now() / 1000)),
    oauth_version: "1.0",
    ...extra,
  };
  const ps = Object.keys(o).map((k) => [enc(k), enc(o[k])]).sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)).map(([k, v]) => `${k}=${v}`).join("&");
  const base = [method.toUpperCase(), enc(url), enc(ps)].join("&");
  o.oauth_signature = crypto.createHmac("sha1", `${enc(API_SECRET)}&${enc(tokenSecret)}`).update(base).digest("base64");
  return "OAuth " + Object.keys(o).sort().map((k) => `${enc(k)}="${enc(o[k])}"`).join(", ");
}

async function xPost(url, extra, tokenSecret = "") {
  const res = await fetch(url, { method: "POST", headers: { Authorization: authHeader("POST", url, extra, tokenSecret) } });
  const text = await res.text();
  if (!res.ok) throw new Error(`${url} → HTTP ${res.status} ${text.slice(0, 160)}`);
  return Object.fromEntries(new URLSearchParams(text));
}

async function gh(path, init = {}) {
  const res = await fetch(`https://api.github.com${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${GITHUB_TOKEN}`, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", ...(init.headers || {}) },
  });
  if (res.status === 204) return null;
  const j = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`GitHub ${path} → HTTP ${res.status} ${JSON.stringify(j).slice(0, 160)}`);
  return j;
}

function ghSecretSet(name, value) {
  return new Promise((resolve, reject) => {
    const p = spawn("gh", ["secret", "set", name, "--repo", REPO], {
      stdio: ["pipe", "inherit", "inherit"],
      env: { ...process.env, GH_TOKEN: GH_PAT },
    });
    p.on("error", reject);
    p.on("close", (c) => (c === 0 ? resolve() : reject(new Error(`gh secret set ${name} → exit ${c}`))));
    p.stdin.write(value);
    p.stdin.end();
  });
}

// ---- 1. request token ----
console.log(`\n=== ${site} のトークン発行 ===`);
if (SITES[site]) console.log(`想定アカウント: @${SITES[site]}`);
const startedAt = new Date().toISOString();
const rt = await xPost("https://api.twitter.com/oauth/request_token", { oauth_callback: CALLBACK_URL });
if (rt.oauth_callback_confirmed !== "true") fail("oauth_callback_confirmed が true ではありません(アプリのコールバック URL 設定を確認)");

const authUrl = `https://api.twitter.com/oauth/authorize?oauth_token=${rt.oauth_token}`;
console.log("\n::notice title=認証URL::" + authUrl);
console.log("\n① 下記 URL を、対象の Bot アカウントでログイン中のブラウザで開き「連携アプリを認証」を押してください:");
console.log("   " + authUrl);
console.log("\n② 遷移後の URL に含まれる oauth_verifier を、Issue #" + issue + " に次の形式でコメントしてください:");
console.log(`   verifier ${rt.oauth_token} <oauth_verifier>`);
console.log(`\n③ 最長 ${POLL_MAX_MIN} 分待ちます…`);

// ---- 2. poll issue comments ----
let verifier = null, commentId = null;
const deadline = Date.now() + POLL_MAX_MIN * 60_000;
while (Date.now() < deadline) {
  await new Promise((r) => setTimeout(r, POLL_MS));
  let comments = [];
  try {
    comments = await gh(`/repos/${REPO}/issues/${issue}/comments?since=${encodeURIComponent(startedAt)}&per_page=50`);
  } catch (e) { console.log("   (コメント取得に失敗、再試行) " + e.message.slice(0, 80)); continue; }
  for (const c of comments) {
    const m = String(c.body || "").match(/verifier\s+(\S+)\s+([A-Za-z0-9_-]+)/);
    if (m && m[1] === rt.oauth_token) { verifier = m[2]; commentId = c.id; break; }
  }
  if (verifier) break;
  process.stdout.write(".");
}
console.log("");
if (!verifier) fail("時間内に verifier が届きませんでした。もう一度実行してください。");
console.log("④ verifier を受信しました。アクセストークンに交換します…");

// ---- 3. exchange ----
const at = await xPost("https://api.twitter.com/oauth/access_token", { oauth_token: rt.oauth_token, oauth_verifier: verifier }, rt.oauth_token_secret);
const handle = at.screen_name;
console.log(`   認証されたアカウント: @${handle}`);

const expected = SITES[site];
if (expected && handle.toLowerCase() !== expected.toLowerCase()) {
  fail(`アカウントが一致しません。期待: @${expected} / 実際: @${handle}。ブラウザのログインを切り替えて再実行してください。`);
}

// ---- 4. write secrets ----
const P = site.toUpperCase();
console.log("⑤ GitHub Secrets に登録します…");
await ghSecretSet(`${P}_X_ACCESS_TOKEN`, at.oauth_token);
console.log(`   ✅ ${P}_X_ACCESS_TOKEN`);
await ghSecretSet(`${P}_X_ACCESS_TOKEN_SECRET`, at.oauth_token_secret);
console.log(`   ✅ ${P}_X_ACCESS_TOKEN_SECRET`);

// ---- 5. cleanup ----
if (commentId) {
  try { await gh(`/repos/${REPO}/issues/comments/${commentId}`, { method: "DELETE" }); console.log("   (verifier コメントを削除しました)"); }
  catch (e) { console.log("   (コメント削除に失敗: " + e.message.slice(0, 80) + ")"); }
}
console.log(`\n完了: ${site} は @${handle} として投稿します。`);
