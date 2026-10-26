// Cloudflare Worker「メルル査定」。画面(public/)は静的アセットとして配り、ここでは /api/* だけを扱う。
//
//   POST /api/read  {game, sid, images: [{media_type, data(base64)}]}
//     → キャラ一覧・武器(光円錐)のスクショを Claude に読ませ、星5キャラの凸数と餅を返す
//       グラブル・ウマ娘・第五人格は、チェック式査定の項目の数を返す({values})
//       画像は読み取りにだけ使い、保存しない
//   POST /api/event {kind: estimate|dm, game, sid, chars, low, high} … 利用記録(src/events.js)
//   GET  /api/stats(合言葉が必要)… 利用記録の集計。画面は public/admin.html
//   POST /api/lead {game, handle?, wish?, chars, low, high, sid, detail?} … 査定ページからの相談 → 代理出品の管理に入り、管理番号を返す
//     (detail はチェック式の査定 check.html で答えた内容。メモに残す)
//   /api/consign・/api/templates(合言葉が必要)… 代理出品の一覧・更新・DM の定型文(src/consign.js)
//   /api/stock・/api/split・/api/image・/api/want・/api/follow(合言葉が必要)… 在庫・分割払い・スクショ・購入希望者・フォロー候補の管理(src/stock.js, src/follow.js)
//   GET/POST /api/form/:token … 引き継ぎ情報フォーム(売主が1回だけ記入。public/form.html)
//   /api/sheet(合言葉が必要)… 引き継ぎ情報フォームのリンク作成・回答(src/sheet.js。シートは public/sheet.html)
//   GET /api/catalog・/api/catalog/image/:id … お客様向けの在庫一覧(公開にした在庫・代理出品だけ。public/zaiko.html)
//   /api/caution(合言葉が必要)… 要注意リスト。引き渡し完了は詐欺対策のチェックが全部そろってから(409 で断る)
//
// バインディング:
//   ANTHROPIC_API_KEY … Secret(未設定なら /api/read は 503。画面は手入力だけで動く)
//   DB                … D1(1日あたりの利用回数。IP はハッシュにして保存)
//   DAILY_LIMIT_PER_IP / DAILY_LIMIT_TOTAL … 1日の上限(wrangler.toml の vars)
//   STATS_TOKEN_SHA256 … /api/stats の合言葉の SHA-256(wrangler.toml の vars。gametrade-watch と同じ合言葉)

import Anthropic from "@anthropic-ai/sdk";
import { CHARS, TERMS } from "../public/lib/chars.js";
import { GAMES, ACCOUNTS, gamesOf } from "../public/lib/games.js";
import { CHECK, checkSchema, checkPrompt, checkValues } from "../public/lib/check.js";
import checkModel from "../public/check-model.json" with { type: "json" };
import { validEvent, record, stats } from "./events.js";
import { validStock, validSplit, validPay, createStock, updateStock, listStock, createSplit, updateSplit, listSplit, addPay, updatePay, deletePay, validImage, addImage, listImages, getImage, replaceImage, deleteImage, validWant, createWant, updateWant, listWants, handoverMissing, listCaution, addCaution, deleteCaution, findCaution } from "./stock.js";
import { validSheet, createSheet, listSheets, getSheet, deleteSheet, formInfo, validSubmit, submitSheet } from "./sheet.js";
import { listCatalog, catalogImage } from "./catalog.js";
import { listFollow, importFollow, setFollowStatus } from "./follow.js";
import { validLead, validPatch, normHandle, createLead, listConsign, updateConsign, logDm, getTemplates, saveTemplates, STATUSES } from "./consign.js";

const MODEL = "claude-opus-5-5";
const MAX_IMAGES = 6;
const MAX_BASE64 = 5_000_000; // 1枚あたり(画面側で縮小してから送る)
const TYPES = ["image/jpeg", "image/png", "image/webp"];

// 画面は game-souba.com/hoyo/satei/(GitHub Pages)。そこからの /api/read を受け付ける
const ORIGINS = ["https://game-souba.com", "https://www.game-souba.com"];
const corsHeaders = (req) => {
  const origin = req.headers.get("origin");
  return ORIGINS.includes(origin) ? { "access-control-allow-origin": origin, vary: "origin" } : {};
};
const readJson = async (req, max = 50_000) => {
  const text = await req.text();
  if (text.length > max) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
};
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8" } });

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// 1日の利用回数を数え、上限を超えていれば false
async function allow(env, ip) {
  const day = new Date(Date.now() + 9 * 3600_000).toISOString().slice(0, 10); // 日本時間の日付
  const who = (await sha256(`${day}:${ip}`)).slice(0, 32);
  const perIp = Number(env.DAILY_LIMIT_PER_IP) || 5;
  const total = Number(env.DAILY_LIMIT_TOTAL) || 200;
  const [mine, all] = await env.DB.batch([
    env.DB.prepare("SELECT n FROM usage WHERE day = ? AND who = ?").bind(day, who),
    env.DB.prepare("SELECT COALESCE(SUM(n), 0) AS n FROM usage WHERE day = ?").bind(day),
  ]);
  if ((mine.results[0]?.n ?? 0) >= perIp || (all.results[0]?.n ?? 0) >= total) return false;
  await env.DB.prepare("INSERT INTO usage (day, who, n) VALUES (?, ?, 1) ON CONFLICT(day, who) DO UPDATE SET n = n + 1")
    .bind(day, who)
    .run();
  return true;
}

// Claude に返してもらう形
export const SCHEMA = {
  type: "object",
  additionalProperties: false,
  required: ["characters", "uid_visible"],
  properties: {
    characters: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        required: ["name", "cons", "mochi"],
        properties: {
          name: { type: "string" },
          // 構造化出力は minimum / maximum を受け付けないので、取りうる値を並べる
          cons: { type: "integer", enum: [0, 1, 2, 3, 4, 5, 6] },
          mochi: { type: "boolean" },
        },
      },
    },
    uid_visible: { type: "boolean" },
  },
};

export function prompt(game) {
  const names = Object.keys(CHARS[game]).join("、");
  const { full, cons, weapon, star5 } = TERMS[game];
  return `${full}のアカウントのスクリーンショットです(キャラ一覧、${weapon}一覧など)。
${star5}だけを列挙してください。それより下のレアリティのキャラ・主人公(旅人/開拓者/漂泊者など)は含めないでください。

- name: キャラ名。次の一覧にあるキャラはこの表記にそろえる。一覧にないキャラは画面の表記のまま。
  ${names}
- cons: ${cons}。0〜6 の整数。キャラ一覧のアイコン右上などの数字で、数字が無ければ 0。
- mochi: そのキャラのモチーフ${weapon}(専用の最高レアリティの${weapon})を持っていれば true。${weapon}一覧で装備キャラのアイコンや名前から判断し、分からなければ false。
- uid_visible: 画像に UID が写っていれば true。

同じキャラが複数の画像に出ていたら1つにまとめ、凸数は大きい方にしてください。読み取れないものを推測で足さないでください。`;
}

async function read(env, body, ip, ctx) {
  const game = body?.game;
  // グラブル・ウマ娘・第五人格は、チェック式査定の項目(数)を読む
  const check = Boolean(CHECK[game]);
  // 値段に効く名前(学習で決まる)。写っていれば has で返してもらう
  const pick = check ? (checkModel.games[game]?.pick ?? []) : [];
  if (!CHARS[game] && !check) return json({ ok: false, error: "game が不正です" }, 400);
  const images = Array.isArray(body.images) ? body.images : [];
  if (!images.length || images.length > MAX_IMAGES) return json({ ok: false, error: `画像は1〜${MAX_IMAGES}枚にしてください` }, 400);
  for (const im of images) {
    if (!TYPES.includes(im?.media_type) || typeof im.data !== "string" || im.data.length > MAX_BASE64) {
      return json({ ok: false, error: "画像の形式か大きさが不正です" }, 400);
    }
  }
  // 形の正しい依頼だけを数える
  if (!(await allow(env, ip))) return json({ ok: false, error: "本日の画像読み取りの上限に達しました。手入力で査定できます" }, 429);
  const client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
  let res;
  try {
    res = await client.beta.messages.create({
      model: MODEL,
      max_tokens: 16000,
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      output_config: { effort: "medium", format: { type: "json_schema", schema: check ? checkSchema(game, pick) : SCHEMA } },
      messages: [
        {
          role: "user",
          content: [
            ...images.map((im) => ({ type: "image", source: { type: "base64", media_type: im.media_type, data: im.data } })),
            { type: "text", text: check ? checkPrompt(game, pick) : prompt(game) },
          ],
        },
      ],
    });
  } catch (err) {
    console.error("anthropic", err?.status, err?.message);
    if (err instanceof Anthropic.RateLimitError) return json({ ok: false, error: "混み合っています。少し待ってからお試しください" }, 429);
    if (err instanceof Anthropic.BadRequestError) return json({ ok: false, error: "画像を読み取れませんでした" }, 400);
    if (err instanceof Anthropic.APIError) return json({ ok: false, error: `読み取りに失敗しました(${err.status})` }, 502);
    throw err;
  }
  if (res.stop_reason === "refusal") return json({ ok: false, error: "この画像は読み取れませんでした" }, 422);
  const text = res.content.find((b) => b.type === "text")?.text;
  let out;
  try {
    out = JSON.parse(text ?? "");
  } catch {
    return json({ ok: false, error: "読み取り結果が不正でした。もう一度お試しください" }, 502);
  }
  if (check) {
    const ev = validEvent({ kind: "read", game, sid: body.sid, chars: [] }, Object.keys(GAMES));
    if (ev) ctx.waitUntil(record(env, ev).catch(() => {}));
    const has = (Array.isArray(out.has) ? out.has : []).filter((h) => pick.includes(h));
    return json({ ok: true, values: checkValues(game, out), has, uid_visible: Boolean(out.id_visible) });
  }
  // 辞書にあるキャラを先に、凸数の大きい順
  const known = new Set(Object.keys(CHARS[game]));
  const characters = out.characters
    .map((c) => ({ name: c.name.trim(), cons: Math.min(6, Math.max(0, c.cons | 0)), mochi: Boolean(c.mochi), known: known.has(c.name.trim()) }))
    .sort((a, b) => Number(b.known) - Number(a.known) || b.cons - a.cons);
  const ev = validEvent({ kind: "read", game, sid: body.sid, chars: characters }, Object.keys(CHARS));
  if (ev) ctx.waitUntil(record(env, ev).catch(() => {}));
  return json({ ok: true, characters, uid_visible: Boolean(out.uid_visible) });
}

async function handle(req, env, ctx) {
  const url = new URL(req.url);
  const { pathname } = url;
  if (pathname === "/api/read" && req.method === "POST") {
    if (!env.ANTHROPIC_API_KEY) return json({ ok: false, error: "画像の読み取りは準備中です。手入力で査定できます" }, 503);
    let body = null;
    try {
      body = await req.json();
    } catch {}
    return read(env, body, req.headers.get("cf-connecting-ip") ?? "unknown", ctx);
  }
  // 利用記録。sendBeacon でも送れるよう、本文は content-type に関係なく JSON として読む
  if (pathname === "/api/event" && req.method === "POST") {
    const text = await req.text();
    if (text.length > 20_000) return json({ ok: false }, 413);
    let body = null;
    try {
      body = JSON.parse(text);
    } catch {}
    const ev = validEvent(body, Object.keys(GAMES));
    if (!ev || ev.kind === "read") return json({ ok: false }, 400);
    await record(env, ev);
    return json({ ok: true });
  }
  // 査定ページの「この金額で売りたい」からの相談(誰でも送れるので、1日の件数に上限を置く)
  if (pathname === "/api/lead" && req.method === "POST") {
    const lead = validLead(await readJson(req), Object.keys(GAMES));
    if (!lead) return json({ ok: false, error: "入力を確認してください" }, 400);
    // 要注意リストの人は、メモの先頭に印を付ける(相談は普段どおり受け付ける)
    const hit = await findCaution(env, lead.handle);
    if (hit) lead.memo = `⚠️要注意リスト(${hit.reason ?? "理由なし"}) ${lead.memo ?? ""}`.trim();
    const today = await env.DB.prepare("SELECT COUNT(*) AS n FROM consign WHERE source = 'tool' AND created_at >= ?")
      .bind(new Date(Date.now() - 86400_000).toISOString())
      .first();
    if ((today?.n ?? 0) >= (Number(env.DAILY_LIMIT_LEADS) || 100)) return json({ ok: false, error: "混み合っています。XのDMで直接ご相談ください" }, 429);
    const { id, merged } = await createLead(env, lead);
    return json({ ok: true, no: id, merged });
  }
  // お客様向けの在庫一覧(公開にしたものだけ)
  if (pathname === "/api/catalog" && req.method === "GET") {
    return new Response(JSON.stringify({ ok: true, items: await listCatalog(env) }), { headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=60" } });
  }
  const ci = /^\/api\/catalog\/image\/(\d+)$/.exec(pathname);
  if (ci && req.method === "GET") {
    const img = await catalogImage(env, Number(ci[1]));
    if (!img) return json({ ok: false, error: "not found" }, 404);
    const bin = Uint8Array.from(atob(img.data), (c) => c.charCodeAt(0));
    return new Response(bin, { headers: { "content-type": img.mime, "cache-control": "public, max-age=300" } });
  }
  // 引き継ぎ情報フォーム(リンクの token を知っている売主だけが記入できる)
  const form = /^\/api\/form\/([0-9a-f]{32})$/.exec(pathname);
  if (form && req.method === "GET") {
    const s = await formInfo(env, form[1]);
    return s ? json({ ok: true, label: s.label, game: s.game, submitted: Boolean(s.submitted_at) }) : json({ ok: false, error: "リンクが正しくありません" }, 404);
  }
  if (form && req.method === "POST") {
    const body = validSubmit(await readJson(req, 7_000_000));
    if (!body) return json({ ok: false, error: "入力内容を確認してください" }, 400);
    return (await submitSheet(env, form[1], body)) ? json({ ok: true }) : json({ ok: false, error: "記入済み、またはリンクが正しくありません" }, 409);
  }
  // ここから下は集計画面用(合言葉が必要)
  const admin = pathname === "/api/stats" || /^\/api\/(consign|stock|split|pay|image|want|follow|caution|sheet)/.test(pathname) || pathname === "/api/templates";
  if (admin) {
    const token = (req.headers.get("authorization") ?? "").replace(/^Bearer /, "");
    if (!env.STATS_TOKEN_SHA256 || (await sha256(token)) !== env.STATS_TOKEN_SHA256) return json({ ok: false, error: "合言葉が違います" }, 401);
  }
  if (pathname === "/api/stats" && req.method === "GET") {
    // ?account=genshin|prop で、そのアカウントのゲームだけにする
    const acct = url.searchParams.get("account");
    const games = Object.hasOwn(ACCOUNTS, acct ?? "") ? gamesOf(acct) : null;
    return json({ ok: true, ...(await stats(env, Math.min(Number(url.searchParams.get("days")) || 30, 365), games)) });
  }
  if (pathname === "/api/consign" && req.method === "GET") {
    return json({ ok: true, statuses: STATUSES, items: await listConsign(env), templates: await getTemplates(env) });
  }
  if (pathname === "/api/consign" && req.method === "POST") {
    const body = await readJson(req);
    const handle = body?.handle ? normHandle(body.handle) : null;
    // ユーザー名か呼び名のどちらかは要る
    if ((!handle && !body?.name?.trim()) || (body?.handle && !handle) || !GAMES[body.game]) {
      return json({ ok: false, error: "ユーザー名(または呼び名)とゲームを確認してください" }, 400);
    }
    const { id } = await createLead(env, { handle, game: body.game, chars: [], low: null, high: null, wish: null, sid: "" }, "manual");
    await updateConsign(env, id, validPatch(body));
    return json({ ok: true, no: id });
  }
  const m = /^\/api\/consign\/(\d+)(\/dm)?$/.exec(pathname);
  if (m && req.method === "PATCH" && !m[2]) {
    const patch = validPatch(await readJson(req));
    const missing = await handoverMissing(env, "consign", Number(m[1]), patch);
    if (missing.length) return notYet(missing);
    const ok = await updateConsign(env, Number(m[1]), patch);
    return json({ ok }, ok ? 200 : 404);
  }
  if (m && req.method === "POST" && m[2]) {
    await logDm(env, Number(m[1]), (await readJson(req))?.template);
    return json({ ok: true });
  }
  if (pathname === "/api/sheet" && req.method === "GET") return json({ ok: true, items: await listSheets(env) });
  if (pathname === "/api/sheet" && req.method === "POST") {
    const row = validSheet(await readJson(req), Object.keys(GAMES));
    return row ? json({ ok: true, ...(await createSheet(env, row)) }) : json({ ok: false, error: "bad request" }, 400);
  }
  const sm = /^\/api\/sheet\/(\d+)$/.exec(pathname);
  if (sm && req.method === "GET") {
    const sheet = await getSheet(env, Number(sm[1]));
    return sheet ? json({ ok: true, sheet }) : json({ ok: false, error: "not found" }, 404);
  }
  if (sm && req.method === "DELETE") return json({ ok: await deleteSheet(env, Number(sm[1])) });
  if (pathname === "/api/templates" && req.method === "PUT") {
    const n = await saveTemplates(env, (await readJson(req))?.templates);
    return n ? json({ ok: true, saved: n }) : json({ ok: false, error: "定型文が空です" }, 400);
  }
  const stockRes = await stockApi(env, req, pathname);
  if (stockRes) return stockRes;
  if (pathname.startsWith("/api/")) return json({ ok: false, error: "not found" }, 404);
  // 公開先は game-souba.com に移った。workers.dev のページは移転先へ(モデルなどのデータはそのまま配る)
  if (url.hostname.endsWith(".workers.dev") && (pathname === "/" || pathname === "/index.html")) {
    return Response.redirect("https://game-souba.com/hoyo/satei/", 301);
  }
  return env.ASSETS.fetch(req);
}

// 在庫と分割払い(合言葉の確認は済んでいる)。該当しなければ null
// 詐欺対策のチェックが残っている時の返事
const notYet = (missing) => json({ ok: false, error: `詐欺対策のチェックが残っています: ${missing.join("、")}` }, 409);

async function stockApi(env, req, pathname) {
  const games = Object.keys(GAMES);
  const bad = () => json({ ok: false, error: "入力を確認してください" }, 400);
  const done = (ok) => json({ ok }, ok ? 200 : 404);
  if (pathname === "/api/stock" && req.method === "GET") return json({ ok: true, stock: await listStock(env), split: await listSplit(env), images: await listImages(env), wants: await listWants(env), follow: await listFollow(env), caution: await listCaution(env) });
  if (pathname === "/api/stock" && req.method === "POST") {
    const row = validStock(await readJson(req), games);
    return row?.game ? json({ ok: true, no: await createStock(env, row) }) : bad();
  }
  let m = /^\/api\/stock\/(\d+)$/.exec(pathname);
  if (m && req.method === "PATCH") {
    const patch = validStock(await readJson(req), games);
    if (!patch) return bad();
    const missing = await handoverMissing(env, "stock", Number(m[1]), patch);
    return missing.length ? notYet(missing) : done(await updateStock(env, Number(m[1]), patch));
  }
  if (pathname === "/api/split" && req.method === "POST") {
    const body = await readJson(req);
    const row = validSplit(body, games);
    const pays = (Array.isArray(body?.pays) ? body.pays : []).slice(0, 60).map(validPay);
    if (!row?.game || !row.buyer || row.total == null || pays.some((p) => !p?.due_on || p.amount == null)) return bad();
    return json({ ok: true, no: await createSplit(env, row, pays) });
  }
  m = /^\/api\/split\/(\d+)(\/pay)?$/.exec(pathname);
  if (m && !m[2] && req.method === "PATCH") {
    const patch = validSplit(await readJson(req), games);
    if (!patch) return bad();
    const missing = await handoverMissing(env, "split", Number(m[1]), patch);
    return missing.length ? notYet(missing) : done(await updateSplit(env, Number(m[1]), patch));
  }
  if (m && m[2] && req.method === "POST") {
    const p = validPay(await readJson(req));
    return p?.due_on && p.amount != null ? json({ ok: true, id: await addPay(env, Number(m[1]), p) }) : bad();
  }
  m = /^\/api\/pay\/(\d+)$/.exec(pathname);
  if (m && req.method === "PATCH") {
    const patch = validPay(await readJson(req));
    return patch ? done(await updatePay(env, Number(m[1]), patch)) : bad();
  }
  if (m && req.method === "DELETE") return done(await deletePay(env, Number(m[1])));
  // フォロー候補(表を取り込み・状態を変える)
  if (pathname === "/api/follow/import" && req.method === "POST") {
    const body = await readJson(req, 60_000);
    if (typeof body?.text !== "string") return bad();
    return json({ ok: true, ...(await importFollow(env, body.text)) });
  }
  m = /^\/api\/follow\/(\d+)$/.exec(pathname);
  if (m && req.method === "PATCH") return done(await setFollowStatus(env, Number(m[1]), (await readJson(req))?.status));
  // 要注意リスト
  if (pathname === "/api/caution" && req.method === "GET") return json({ ok: true, items: await listCaution(env) });
  if (pathname === "/api/caution" && req.method === "POST") {
    const body = await readJson(req);
    const handle = normHandle(body?.handle ?? "");
    if (!handle) return json({ ok: false, error: "X の @ID を確認してください" }, 400);
    await addCaution(env, handle, body.reason);
    return json({ ok: true });
  }
  m = /^\/api\/caution\/(\d+)$/.exec(pathname);
  if (m && req.method === "DELETE") return done(await deleteCaution(env, Number(m[1])));
  // 購入希望
  if (pathname === "/api/want" && req.method === "POST") {
    const row = validWant(await readJson(req), games);
    return row?.name && row.game ? json({ ok: true, no: await createWant(env, row) }) : bad();
  }
  m = /^\/api\/want\/(\d+)$/.exec(pathname);
  if (m && req.method === "PATCH") {
    const patch = validWant(await readJson(req), games);
    return patch ? done(await updateWant(env, Number(m[1]), patch)) : bad();
  }
  // 画像(合言葉の付いた fetch で取り、画面で blob にして表示する)
  if (pathname === "/api/image" && req.method === "POST") {
    const img = validImage(await readJson(req, 1_500_000));
    if (!img) return bad();
    const id = await addImage(env, img);
    return id ? json({ ok: true, id }) : json({ ok: false, error: "1件に付けられる画像の上限です" }, 400);
  }
  m = /^\/api\/image\/(\d+)$/.exec(pathname);
  if (m && req.method === "GET") {
    const img = await getImage(env, Number(m[1]));
    if (!img) return done(false);
    const bin = Uint8Array.from(atob(img.data), (c) => c.charCodeAt(0));
    return new Response(bin, { headers: { "content-type": img.mime, "cache-control": "private, no-store" } });
  }
  if (m && req.method === "PUT") {
    const img = validImage({ owner: "stock", owner_id: 0, ...(await readJson(req, 1_500_000)) });
    return img ? done(await replaceImage(env, Number(m[1]), img)) : bad();
  }
  if (m && req.method === "DELETE") return done(await deleteImage(env, Number(m[1])));
  return null;
}

export default {
  async fetch(req, env, ctx) {
    const cors = corsHeaders(req);
    if (req.method === "OPTIONS" && new URL(req.url).pathname.startsWith("/api/")) {
      return new Response(null, {
        status: 204,
        headers: { ...cors, "access-control-allow-methods": "GET, POST, PATCH, PUT, DELETE", "access-control-allow-headers": "content-type, authorization", "access-control-max-age": "86400" },
      });
    }
    const res = await handle(req, env, ctx);
    if (!Object.keys(cors).length || !new URL(req.url).pathname.startsWith("/api/")) return res;
    const out = new Response(res.body, res);
    for (const [k, v] of Object.entries(cors)) out.headers.set(k, v);
    return out;
  },
};
