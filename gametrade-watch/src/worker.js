// Cloudflare Worker: ゲームトレードの一覧ページを受け取り、新規出品と値下げを Discord に通知する。
// ゲームトレードはクラウドのサーバー(GitHub Actions・Cloudflare)からのアクセスを拒否するため、
// 一覧の取得は Claude の定期実行(1時間ごと)が relay.mjs で行い、ここに POST /ingest で送る。
//
// バインディング:
//   DB                        … D1(前回の状態。kv テーブル)
//   GAMETRADE_DISCORD_WEBHOOK … Secret(通知先の Discord ウェブフックURL)
//   INGEST_TOKEN_SHA256       … POST /ingest の合言葉の SHA-256(wrangler.toml の vars)
// 売れたアカウント(査定ツールの学習用。sold-relay.mjs が送る):
//   POST /sold {game, items}・GET /sold/missing・POST /sold/details {details}・GET /sold/export(合言葉が必要)
//   自宅 PC から(読み取りは Worker 側): POST /sold/pages {game, pages: [一覧の HTML]}・POST /sold/detail-html {id, html}
//   GET /sold/stats で件数を確認できる
// GET /status(?site=gameclub / gametrade-zzz など)で最後の実行結果を確認できる。/sample は新しいサイトの下調べ用(合言葉が必要)。POST /ingest に {"test": true} でテスト投稿。

import gametrade from "../config.json";
import gameclub from "../config.gameclub.json";
import targets from "../config.targets.json";
import { runCheck } from "./core.js";
import { validRecords, parseSold, parseDetail, soldRecord } from "./sold.js";

// 監視先。キー(id)は /ingest・/status の site。原神の2つは最初からの id のまま、ほかのゲームは config.targets.json
// (各要素の site は解析の種類 gametrade / gameclub)
const CONFIGS = { gametrade, gameclub, ...Object.fromEntries(targets.map((t) => [t.id, t])) };
// D1 のキー(ゲームトレードの原神は最初からある "state" / "status" のまま)
// fullRange のサイト(ゲームクラブ)は価格帯ごとに状態を分ける。価格帯を広げた時に、新しく入った既存の出品が
// すべて【価格変更】として通知されないよう、価格帯を変えたら初回(記録のみ)からやり直す
const keys = (id) => {
  if (id === "gametrade") return { state: "state", status: "status" };
  const config = CONFIGS[id];
  if ((config.site ?? id) !== "gameclub") return { state: `state:${id}`, status: `status:${id}` };
  const q = new URL(config.url).searchParams;
  return { state: `state:${id}:${q.get("search[priceMin]")}-${q.get("search[priceMax]")}`, status: `status:${id}` };
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
      ...(r.skipped?.length ? { skipped: r.skipped } : {}),
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

const readJson = async (req) => {
  try {
    return await req.json();
  } catch {
    return null;
  }
};

// 売れたアカウントの記録(サイトは今のところゲームトレードだけ)
async function sold(req, env, pathname, params) {
  if (pathname === "/sold/stats") {
    const { results } = await env.DB.prepare(
      "SELECT game, COUNT(*) AS sold, COUNT(detail_at) AS detailed, MIN(price) AS min_price, MAX(price) AS max_price, MAX(first_seen) AS last_seen FROM sold GROUP BY game",
    ).all();
    return json({ ok: true, games: results });
  }
  if (!(await authorized(req, env))) return json({ ok: false, error: "unauthorized" }, 401);
  const now = new Date().toISOString();
  const insert = async (game, items) => {
    const stmt = env.DB.prepare(
      "INSERT OR IGNORE INTO sold (site, id, game, name, price, url, image, info, first_seen) VALUES ('gametrade', ?, ?, ?, ?, ?, ?, ?, ?)",
    );
    const res = items.length
      ? await env.DB.batch(items.map((it) => stmt.bind(it.id, game, it.name, it.price, it.url ?? null, it.image ?? null, JSON.stringify(it.info ?? []), now)))
      : [];
    return res.reduce((n, r) => n + (r.meta?.changes ?? 0), 0);
  };
  const saveDetails = async (details) => {
    const stmt = env.DB.prepare("UPDATE sold SET description = ?, images = ?, detail_at = ? WHERE site = 'gametrade' AND id = ?");
    const res = details.length
      ? await env.DB.batch(details.map((d) => stmt.bind(d.description.slice(0, 20000), JSON.stringify(d.images.filter((x) => typeof x === "string").slice(0, 30)), now, String(d.id))))
      : [];
    return res.reduce((n, r) => n + (r.meta?.changes ?? 0), 0);
  };
  if (pathname === "/sold" && req.method === "POST") {
    const body = await readJson(req);
    if (!/^[a-z0-9-]+$/.test(body?.game ?? "")) return json({ ok: false, error: "game が必要です" }, 400);
    const items = validRecords(body.items).slice(0, 500);
    return json({ ok: true, received: items.length, added: await insert(body.game, items) });
  }
  // 自宅 PC は一覧の HTML をそのまま送る(読み取りはここで)
  if (pathname === "/sold/pages" && req.method === "POST") {
    const body = await readJson(req);
    if (!/^[a-z0-9-]+$/.test(body?.game ?? "")) return json({ ok: false, error: "game が必要です" }, 400);
    if (!Array.isArray(body.pages) || !body.pages.every((p) => typeof p === "string")) return json({ ok: false, error: "pages (HTML の配列) が必要です" }, 400);
    const found = new Map();
    for (const html of body.pages.slice(0, 10)) for (const it of parseSold(html)) found.set(it.id, soldRecord(it));
    const items = validRecords([...found.values()]);
    return json({ ok: true, sold: items.length, added: await insert(body.game, items) });
  }
  if (pathname === "/sold/detail-html" && req.method === "POST") {
    const body = await readJson(req);
    if (!/^\d+$/.test(String(body?.id ?? "")) || typeof body.html !== "string") return json({ ok: false, error: "id と html が必要です" }, 400);
    const d = parseDetail(body.html);
    return json({ ok: true, updated: await saveDetails([{ id: body.id, description: d.description, images: d.images }]) });
  }
  if (pathname === "/sold/missing") {
    const limit = Math.min(Number(params.get("limit")) || 50, 200);
    const { results } = await env.DB.prepare(
      "SELECT id, url FROM sold WHERE site = 'gametrade' AND detail_at IS NULL AND url IS NOT NULL ORDER BY first_seen DESC, id DESC LIMIT ?",
    )
      .bind(limit)
      .all();
    return json({ ok: true, items: results });
  }
  if (pathname === "/sold/details" && req.method === "POST") {
    const body = await readJson(req);
    const details = (Array.isArray(body?.details) ? body.details : [])
      .filter((d) => /^\d+$/.test(String(d?.id ?? "")) && typeof d.description === "string" && Array.isArray(d.images))
      .slice(0, 200);
    return json({ ok: true, updated: await saveDetails(details) });
  }
  // 学習用の書き出し: ?game=genshin-impact&after=<id>&limit=500(id の昇順。続きは最後の id を after に)
  if (pathname === "/sold/export") {
    const limit = Math.min(Number(params.get("limit")) || 500, 2000);
    const { results } = await env.DB.prepare(
      "SELECT * FROM sold WHERE site = 'gametrade' AND game = ? AND CAST(id AS INTEGER) > ? ORDER BY CAST(id AS INTEGER) LIMIT ?",
    )
      .bind(params.get("game") ?? "genshin-impact", Number(params.get("after")) || 0, limit)
      .all();
    const rows = results.map((r) => ({ ...r, info: JSON.parse(r.info ?? "[]"), images: JSON.parse(r.images ?? "[]") }));
    return json({ ok: true, rows, next: rows.length === limit ? rows.at(-1).id : null });
  }
  return json({ ok: false, error: "not found" }, 404);
}

export default {
  async fetch(req, env) {
    const { pathname, searchParams } = new URL(req.url);
    if (pathname === "/sold" || pathname.startsWith("/sold/")) return sold(req, env, pathname, searchParams);
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
