#!/usr/bin/env node
/**
 * X API 認証情報の診断ツール(値は画面に出しません)
 *
 * 4つの値の「形式」と、実際に X API へ署名付きリクエストを送って
 * 認証が通るかを確認します。
 *
 * 使い方(PowerShell):
 *   $env:X_API_KEY = Read-Host "API Key"
 *   $env:X_API_SECRET = Read-Host "API Key Secret"
 *   $env:X_ACCESS_TOKEN = Read-Host "Access Token"
 *   $env:X_ACCESS_TOKEN_SECRET = Read-Host "Access Token Secret"
 *   node x-check-creds.mjs
 */
import crypto from "node:crypto";

const K = process.env.X_API_KEY || "";
const S = process.env.X_API_SECRET || "";
const T = process.env.X_ACCESS_TOKEN || "";
const TS = process.env.X_ACCESS_TOKEN_SECRET || "";
const LABEL = process.argv[2] || "";
if (LABEL) console.log(`\n######## ${LABEL} ########`);

const enc = (s) =>
  encodeURIComponent(s).replace(/[!*'()]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase());

function mark(ok) { return ok ? "✅" : "❌"; }
function ws(s) { return s !== s.trim(); }

console.log("=== 1. 形式チェック(値は表示しません) ===");
const checks = [
  ["X_API_KEY", K, K.length === 25, "25文字の英数字(OAuth 1.0 コンシューマーキー)"],
  ["X_API_SECRET", S, S.length === 50, "50文字の英数字(OAuth 1.0 コンシューマーシークレット)"],
  ["X_ACCESS_TOKEN", T, /^\d{5,}-[A-Za-z0-9]+$/.test(T), "「数字-英数字」の形(例: 2089226763654021120-xxxx)"],
  ["X_ACCESS_TOKEN_SECRET", TS, TS.length === 45, "45文字の英数字"],
];
let formatBad = 0;
for (const [name, v, ok, hint] of checks) {
  const extra = [];
  if (!v) extra.push("未設定");
  if (ws(v)) extra.push("前後に空白あり");
  if (v.includes("\n") || v.includes("\r")) extra.push("改行を含む");
  if (!ok) formatBad++;
  console.log(`${mark(ok && extra.length === 0)} ${name.padEnd(22)} 長さ=${String(v.length).padStart(3)}  期待: ${hint}${extra.length ? "  ⚠ " + extra.join(", ") : ""}`);
}

// よくある取り違えのヒント
if (K.length >= 30 && /^[A-Za-z0-9_-]+$/.test(K) && K.length < 40) {
  console.log("   ヒント: X_API_KEY が OAuth 2.0 の「クライアントID」になっていませんか？ 必要なのは OAuth 1.0 の「コンシューマーキー」です。");
}
if (T && !T.includes("-")) {
  console.log("   ヒント: X_ACCESS_TOKEN にハイフンがありません。OAuth 2.0 のトークンや、別の値を貼っていませんか？");
}
if (K.length === 50 && S.length === 25) {
  console.log("   ヒント: X_API_KEY と X_API_SECRET が逆になっている可能性があります。");
}
if (T.length === 45 && TS.includes("-")) {
  console.log("   ヒント: X_ACCESS_TOKEN と X_ACCESS_TOKEN_SECRET が逆になっている可能性があります。");
}

if (!K || !S || !T || !TS) {
  console.log("\n4つすべて設定してから再実行してください。");
  process.exit(0);
}

console.log("\n=== 2. 実際に X API へ問い合わせ(GET /2/users/me) ===");
const url = "https://api.twitter.com/2/users/me";
const oauth = {
  oauth_consumer_key: K.trim(),
  oauth_nonce: crypto.randomBytes(16).toString("hex"),
  oauth_signature_method: "HMAC-SHA1",
  oauth_timestamp: String(Math.floor(Date.now() / 1000)),
  oauth_token: T.trim(),
  oauth_version: "1.0",
};
const paramStr = Object.keys(oauth).sort().map((k) => `${enc(k)}=${enc(oauth[k])}`).join("&");
const base = ["GET", enc(url), enc(paramStr)].join("&");
const key = `${enc(S.trim())}&${enc(TS.trim())}`;
oauth.oauth_signature = crypto.createHmac("sha1", key).update(base).digest("base64");
const header = "OAuth " + Object.keys(oauth).sort().map((k) => `${enc(k)}="${enc(oauth[k])}"`).join(", ");

try {
  const res = await fetch(url, { headers: { Authorization: header } });
  const body = await res.text();
  if (res.ok) {
    const j = JSON.parse(body);
    console.log(`✅ 認証成功: @${j.data?.username}(${j.data?.name})`);
    console.log("   → この4つの値で投稿できます。GitHub Secrets に同じ値が入っているか確認してください。");
  } else {
    console.log(`❌ HTTP ${res.status}`);
    console.log("   " + body.slice(0, 200));
    if (res.status === 401) {
      console.log("\n   401 = 4つの組み合わせが一致していません。上の形式チェックで ❌ や ⚠ が付いた項目を見直してください。");
      console.log("   すべて ✅ なのに 401 の場合は、アクセストークンを再生成した後にコンシューマーキーを再生成した可能性があります。");
      console.log("   その場合は「アクセストークン」をもう一度再生成してください(順番: コンシューマーキー → アクセストークン)。");
    } else if (res.status === 402) {
      console.log("\n   402 = 認証は通っていますがクレジットが不足しています。");
    } else if (res.status === 403) {
      console.log("\n   403 = 認証は通っていますが権限不足です。アプリの権限が「読み取りと書き込み」か確認してください。");
    }
  }
} catch (e) {
  console.log("❌ 通信エラー: " + e.message);
}
