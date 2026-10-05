// Cloudflare Worker「メルル査定」。画面(public/)は静的アセットとして配り、ここでは /api/* だけを扱う。
//
//   POST /api/read  {game, images: [{media_type, data(base64)}]}
//     → キャラ一覧・武器(光円錐)のスクショを Claude に読ませ、星5キャラの凸数と餅を返す
//       画像は読み取りにだけ使い、保存しない
//
// バインディング:
//   ANTHROPIC_API_KEY … Secret(未設定なら /api/read は 503。画面は手入力だけで動く)
//   DB                … D1(1日あたりの利用回数。IP はハッシュにして保存)
//   DAILY_LIMIT_PER_IP / DAILY_LIMIT_TOTAL … 1日の上限(wrangler.toml の vars)

import Anthropic from "@anthropic-ai/sdk";
import { CHARS } from "../public/lib/chars.js";

const MODEL = "claude-opus-5-5";
const MAX_IMAGES = 6;
const MAX_BASE64 = 5_000_000; // 1枚あたり(画面側で縮小してから送る)
const TYPES = ["image/jpeg", "image/png", "image/webp"];
const GAME_LABEL = { "genshin-impact": "原神", houkaistarrail: "崩壊:スターレイル" };

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
const SCHEMA = {
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
          cons: { type: "integer", minimum: 0, maximum: 6 },
          mochi: { type: "boolean" },
        },
      },
    },
    uid_visible: { type: "boolean" },
  },
};

export function prompt(game) {
  const names = Object.keys(CHARS[game]).join("、");
  const cons = game === "houkaistarrail" ? "星魂(凸数)" : "命ノ星座(凸数)";
  const weapon = game === "houkaistarrail" ? "光円錐" : "武器";
  return `${GAME_LABEL[game]}のアカウントのスクリーンショットです(キャラ一覧、${weapon}一覧など)。
星5キャラクターだけを列挙してください。星4キャラ・主人公(旅人/開拓者)は含めないでください。

- name: キャラ名。次の一覧にあるキャラはこの表記にそろえる。一覧にないキャラは画面の表記のまま。
  ${names}
- cons: ${cons}。0〜6 の整数。キャラ一覧のアイコン右上などの数字で、数字が無ければ 0。
- mochi: そのキャラのモチーフ${weapon}(専用の星5${weapon})を持っていれば true。${weapon}一覧で装備キャラのアイコンや名前から判断し、分からなければ false。
- uid_visible: 画像に UID が写っていれば true。

同じキャラが複数の画像に出ていたら1つにまとめ、凸数は大きい方にしてください。読み取れないものを推測で足さないでください。`;
}

async function read(env, body, ip) {
  const game = body?.game;
  if (!CHARS[game]) return json({ ok: false, error: "game が不正です" }, 400);
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
      output_config: { effort: "medium", format: { type: "json_schema", schema: SCHEMA } },
      messages: [
        {
          role: "user",
          content: [
            ...images.map((im) => ({ type: "image", source: { type: "base64", media_type: im.media_type, data: im.data } })),
            { type: "text", text: prompt(game) },
          ],
        },
      ],
    });
  } catch (err) {
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
  // 辞書にあるキャラを先に、凸数の大きい順
  const known = new Set(Object.keys(CHARS[game]));
  const characters = out.characters
    .map((c) => ({ name: c.name.trim(), cons: Math.min(6, Math.max(0, c.cons | 0)), mochi: Boolean(c.mochi), known: known.has(c.name.trim()) }))
    .sort((a, b) => Number(b.known) - Number(a.known) || b.cons - a.cons);
  return json({ ok: true, characters, uid_visible: Boolean(out.uid_visible) });
}

export default {
  async fetch(req, env) {
    const { pathname } = new URL(req.url);
    if (pathname === "/api/read" && req.method === "POST") {
      if (!env.ANTHROPIC_API_KEY) return json({ ok: false, error: "画像の読み取りは準備中です。手入力で査定できます" }, 503);
      let body = null;
      try {
        body = await req.json();
      } catch {}
      return read(env, body, req.headers.get("cf-connecting-ip") ?? "unknown");
    }
    if (pathname.startsWith("/api/")) return json({ ok: false, error: "not found" }, 404);
    return env.ASSETS.fetch(req);
  },
};
