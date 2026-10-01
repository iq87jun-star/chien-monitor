// Cloudflare Worker: 10分ごと(wrangler.toml の crons)にゲームトレードの一覧を確認して Discord に通知する。
// GitHub Actions のサーバーからはサイトに接続できない(403/応答なし)ため Cloudflare で動かす。
//
// バインディング:
//   DB                        … D1(前回の状態。kv テーブル)
//   GAMETRADE_DISCORD_WEBHOOK … Secret(通知先の Discord ウェブフックURL)
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

async function check(env) {
  const startedAt = new Date().toISOString();
  let status;
  try {
    const state = JSON.parse((await get(env, KEY)) ?? "null");
    const r = await runCheck({ config, state, webhook: env.GAMETRADE_DISCORD_WEBHOOK });
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
  if (!status.ok) throw new Error(status.error);
  return status;
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(check(env));
  },
  async fetch(req, env) {
    const { pathname } = new URL(req.url);
    if (pathname === "/status") {
      return new Response((await get(env, "status")) ?? "{}", {
        headers: { "content-type": "application/json; charset=utf-8" },
      });
    }
    return new Response("gametrade-watch", { status: 404 });
  },
};
