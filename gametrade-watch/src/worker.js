// Cloudflare Worker: ゲームトレードの一覧ページを受け取り、新規出品と値下げを Discord に通知する。
// ゲームトレードはクラウドのサーバー(GitHub Actions・Cloudflare)からのアクセスを拒否するため、
// 一覧の取得は Claude の定期実行(1時間ごと)が relay.mjs で行い、ここに POST /ingest で送る。
//
// バインディング:
//   DB                        … D1(前回の状態。kv テーブル)
//   GAMETRADE_DISCORD_WEBHOOK … Secret(通知先の Discord ウェブフックURL)
//   INGEST_TOKEN_SHA256       … POST /ingest の合言葉の SHA-256(wrangler.toml の vars)
// GET /status で最後の実行結果を確認できる。

import config from "../config.json";
import { runCheck } from "./core.js";

const KEY = "state";

const get = async (env, key) => {
  const row = await env.DB.prepare("SELECT value FROM kv WHERE key = ?").bind(key).first();
  return row ? row.value : null;
};
const put = (env, key, value) =>
  env.DB.prepare("INSERT INTO kv (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value")
    .bind(key, value)
    .run();

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8" } });

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function check(env, pages) {
  const startedAt = new Date().toISOString();
  let status;
  try {
    const state = JSON.parse((await get(env, KEY)) ?? "null");
    const r = await runCheck({ config, state, pages, webhook: env.GAMETRADE_DISCORD_WEBHOOK });
    await put(env, KEY, JSON.stringify(r.state));
    status = {
      ok: true,
      startedAt,
      total: r.total,
      hits: r.hits.length,
      first: r.first,
      notified: r.notified,
      webhook: Boolean(env.GAMETRADE_DISCORD_WEBHOOK),
    };
  } catch (err) {
    status = { ok: false, startedAt, error: String(err?.message ?? err) };
  }
  await put(env, "status", JSON.stringify(status));
  return status;
}

export default {
  async fetch(req, env) {
    const { pathname } = new URL(req.url);
    if (pathname === "/status") return json(JSON.parse((await get(env, "status")) ?? "{}"));
    if (pathname === "/ingest" && req.method === "POST") {
      const token = (req.headers.get("authorization") ?? "").replace(/^Bearer /, "");
      if (!env.INGEST_TOKEN_SHA256 || (await sha256(token)) !== env.INGEST_TOKEN_SHA256) {
        return json({ ok: false, error: "unauthorized" }, 401);
      }
      const body = await req.json().catch(() => null);
      if (!Array.isArray(body?.pages) || !body.pages.every((p) => typeof p === "string")) {
        return json({ ok: false, error: "pages (HTML の配列) が必要です" }, 400);
      }
      const status = await check(env, body.pages);
      return json(status, status.ok ? 200 : 500);
    }
    return new Response("gametrade-watch", { status: 404 });
  },
};
