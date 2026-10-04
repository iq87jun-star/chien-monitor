// Cloudflare Worker: ゲームトレードの一覧ページを受け取り、新規出品と値下げを Discord に通知する。
// ゲームトレードはクラウドのサーバー(GitHub Actions・Cloudflare)からのアクセスを拒否するため、
// 一覧の取得は Claude の定期実行(1時間ごと)が relay.mjs で行い、ここに POST /ingest で送る。
//
// バインディング:
//   DB                        … D1(前回の状態。kv テーブル)
//   GAMETRADE_DISCORD_WEBHOOK … Secret(通知先の Discord ウェブフックURL)
//   INGEST_TOKEN_SHA256       … POST /ingest の合言葉の SHA-256(wrangler.toml の vars)
// GET /status(?site=gameclub)で最後の実行結果を確認できる。/sample は新しいサイトの下調べ用(合言葉が必要)。POST /ingest に {"test": true} でテスト投稿。

import gametrade from "../config.json";
import gameclub from "../config.gameclub.json";
import { runCheck } from "./core.js";

const CONFIGS = { gametrade, gameclub };
// D1 のキー(ゲームトレードは最初からある "state" / "status" のまま)
// fullRange のサイト(ゲームクラブ)は価格帯ごとに状態を分ける。価格帯を広げた時に、新しく入った既存の出品が
// すべて【価格変更】として通知されないよう、価格帯を変えたら初回(記録のみ)からやり直す
const keys = (site) => {
  if (site === "gametrade") return { state: "state", status: "status" };
  const q = new URL(CONFIGS[site].url).searchParams;
  return { state: `state:${site}:${q.get("search[priceMin]")}-${q.get("search[priceMax]")}`, status: `status:${site}` };
};

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

async function check(env, site, pages) {
  const config = CONFIGS[site];
  const KEY = keys(site).state;
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
  await put(env, keys(site).status, JSON.stringify(status));
  return status;
}

const authorized = async (req, env) => {
  const token = (req.headers.get("authorization") ?? "").replace(/^Bearer /, "");
  return Boolean(env.INGEST_TOKEN_SHA256) && (await sha256(token)) === env.INGEST_TOKEN_SHA256;
};

export default {
  async fetch(req, env) {
    const { pathname } = new URL(req.url);
    if (pathname === "/status") {
      const site = new URL(req.url).searchParams.get("site") ?? "gametrade";
      if (!Object.hasOwn(CONFIGS, site)) return json({ ok: false, error: "unknown site" }, 404);
      const status = JSON.parse((await get(env, keys(site).status)) ?? "{}");
      // PC から送るサイトは、PC 側で起きた最後のエラーも見せる
      const pcError = await get(env, `pcerror:${site}`);
      return json(pcError ? { ...status, lastPcError: JSON.parse(pcError) } : status);
    }
    // 新しいサイトに対応する時の下調べ用: ページの HTML を一時的に保存し(POST)、読み出す(GET)
    if (pathname === "/sample") {
      if (!(await authorized(req, env))) return json({ ok: false, error: "unauthorized" }, 401);
      if (req.method === "POST") {
        const text = await req.text();
        await put(env, "sample", text);
        return json({ ok: true, bytes: text.length });
      }
      return new Response((await get(env, "sample")) ?? "", { headers: { "content-type": "text/plain; charset=utf-8" } });
    }
    if (pathname === "/reject") return json(JSON.parse((await get(env, "reject")) ?? "{}"));
    if (pathname === "/ingest" && req.method === "POST") {
      if (!(await authorized(req, env))) return json({ ok: false, error: "unauthorized" }, 401);
      const raw = await req.text();
      let body = null;
      try {
        body = JSON.parse(raw);
      } catch {}
      // 受け付けなかった理由を残す(GET /reject で見られる。中身は形と長さだけで HTML は残さない)
      const reject = async (error) => {
        const shape = {
          bytes: raw.length,
          head: raw.slice(0, 80),
          parsed: body !== null,
          keys: body && typeof body === "object" ? Object.keys(body) : null,
          site: body?.site ?? null,
          pages: Array.isArray(body?.pages)
            ? body.pages.map((p) => (typeof p === "string" ? `string(${p.length})` : `${typeof p}:${Object.keys(p ?? {}).join(",")}`))
            : typeof body?.pages,
        };
        await put(env, "reject", JSON.stringify({ at: new Date().toISOString(), error, ...shape }));
        return json({ ok: false, error, ...shape }, 400);
      };
      // 通知先の確認用: {"test": true} で Discord にテスト投稿だけする
      // PC 側のエラー報告: {"site": "gameclub", "error": "..."}(取得に失敗した時など。/status に出る)
      if (typeof body?.error === "string" && Object.hasOwn(CONFIGS, body.site ?? "")) {
        await put(env, `pcerror:${body.site}`, JSON.stringify({ at: new Date().toISOString(), error: body.error.slice(0, 2000) }));
        return json({ ok: true, recorded: true });
      }
      if (body?.test === true) {
        const res = await fetch(env.GAMETRADE_DISCORD_WEBHOOK, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ username: "ゲームトレード新着", content: "✅ テスト通知です。ここに新着が届きます。" }),
        });
        return json({ ok: res.ok, status: res.status }, res.ok ? 200 : 502);
      }
      if (!Array.isArray(body?.pages) || !body.pages.every((p) => typeof p === "string")) {
        return reject("pages (HTML の配列) が必要です");
      }
      // site を省くとゲームトレード(既存の定期実行はこれ)
      const site = body.site ?? "gametrade";
      if (!Object.hasOwn(CONFIGS, site)) return reject(`unknown site: ${site}`);
      const status = await check(env, site, body.pages);
      return json(status, status.ok ? 200 : 500);
    }
    return new Response("gametrade-watch", { status: 404 });
  },
};
