// Cloudflare Worker: 日本の給与・物件・手取り・暦の計算API。API マーケット経由で販売する。
// 出品(product)ごとにマーケットへ別々に掲載できるよう、呼び出し口を4つに分けている:
//   salary   POST /v1/salary/analyze        求人の給与の文章 → 年収の目安・時給換算・固定残業代
//   realty   POST /v1/realty/analyze        物件の賃料・価格・面積等 → 単価・実質月額・初期費用・ローン・利回り
//   takehome POST /v1/takehome/calculate    月給・賞与 → 社会保険料・所得税・住民税・手取り
//   calendar POST /v1/calendar/*・/v1/wareki/convert  祝日・営業日・和暦
//   GET  /v1/health                         稼働確認(認証不要)
//   GET  /openapi.json[?product=takehome]   API の仕様(出品ごとに絞れる。マーケットへの登録に使う)
// APIキーの発行・回数制限・課金はマーケットが行う。こちらはマーケットが付ける秘密のヘッダーを確かめ、
// マーケットを通さない直接の呼び出しを断る。MARKETPLACE_SECRETS が未設定なら計算APIは使えない
// (設定し忘れて無料で公開されないように)。ローカル開発だけ ALLOW_UNAUTHENTICATED=true で確かめない。
import { InputError, analyzeRealty, analyzeSalary } from "./calc.js";
import {
  addBusinessDays,
  calendarDay,
  calendarHolidays,
  convertWareki,
  countBusinessDays,
} from "./calendar.js";
import { calculateTakeHome } from "./takehome.js";
import openapi from "./openapi.json" with { type: "json" };

const MAX_BODY = 16 * 1024;

const json = (status, body) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
const error = (status, code, message, extra = {}) =>
  json(status, { error: { code, message, ...extra } });

// 呼び出し口 → 計算と、どの出品(product)に属するか
const ROUTES = {
  "POST /v1/salary/analyze": [analyzeSalary, "salary"],
  "POST /v1/realty/analyze": [analyzeRealty, "realty"],
  "POST /v1/takehome/calculate": [calculateTakeHome, "takehome"],
  "POST /v1/calendar/day": [calendarDay, "calendar"],
  "POST /v1/calendar/holidays": [calendarHolidays, "calendar"],
  "POST /v1/calendar/add-business-days": [addBusinessDays, "calendar"],
  "POST /v1/calendar/count-business-days": [countBusinessDays, "calendar"],
  "POST /v1/wareki/convert": [convertWareki, "calendar"],
};
export const PRODUCTS = [...new Set(Object.values(ROUTES).map(([, p]) => p))];

// MARKETPLACE_SECRETS: 「ヘッダー名:値」をカンマ区切りで複数(マーケット・出品ごと)。
// 「@出品名+出品名」を付けると、その秘密の値で使える出品を絞れる(付けなければ全部):
//   例: x-rapidapi-proxy-secret:abc@salary+realty,x-rapidapi-proxy-secret:def@takehome
// マーケットは出品ごとに別の秘密の値を発行するので、出品を分けたらそれぞれに対応する出品を書く
export function parseSecrets(value) {
  return String(value ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      const i = s.indexOf(":");
      if (i <= 0) return null;
      const rest = s.slice(i + 1).trim();
      const at = rest.lastIndexOf("@");
      const secret = at >= 0 ? rest.slice(0, at).trim() : rest;
      const products =
        at >= 0
          ? rest
              .slice(at + 1)
              .split("+")
              .map((p) => p.trim())
          : null;
      return { header: s.slice(0, i).trim().toLowerCase(), secret, products };
    })
    .filter((p) => p && p.secret);
}

function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

// 秘密の値が一致し、かつその値で使える出品か
function fromMarketplace(request, secrets, product) {
  return secrets.some(({ header, secret, products }) => {
    const got = request.headers.get(header);
    return got != null && safeEqual(got, secret) && (!products || products.includes(product));
  });
}

// 出品ごとの仕様書: その出品の呼び出し口と稼働確認だけを残し、使われない部品を除く
export function specFor(product) {
  if (!product) return openapi;
  const paths = Object.fromEntries(
    Object.entries(openapi.paths).filter(
      ([, ops]) =>
        Object.values(ops)[0]["x-product"] === product || ops.get?.operationId === "health",
    ),
  );
  const used = new Set();
  const walk = (node) => {
    if (Array.isArray(node)) return node.forEach(walk);
    if (!node || typeof node !== "object") return;
    for (const [k, v] of Object.entries(node)) {
      if (k === "$ref" && typeof v === "string") {
        const [, kind, name] = v.split("/").slice(1);
        if (!used.has(`${kind}/${name}`)) {
          used.add(`${kind}/${name}`);
          walk(openapi.components[kind][name]);
        }
      } else walk(v);
    }
  };
  walk(paths);
  const components = { securitySchemes: openapi.components.securitySchemes };
  for (const kind of ["schemas", "responses"]) {
    components[kind] = Object.fromEntries(
      Object.entries(openapi.components[kind]).filter(([name]) => used.has(`${kind}/${name}`)),
    );
  }
  const info = { ...openapi.info, ...(openapi["x-products"][product] ?? {}) };
  return { ...openapi, info, paths, components };
}

async function readJson(request) {
  const raw = await request.text();
  if (raw.length > MAX_BODY) throw new InputError("Request body is too large (max 16KB)");
  try {
    const body = JSON.parse(raw || "{}");
    if (!body || typeof body !== "object" || Array.isArray(body)) throw new Error();
    return body;
  } catch {
    throw new InputError("Request body must be a JSON object");
  }
}

export async function handle(request, env = {}) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const route = `${request.method} ${path}`;

  if (route === "GET /v1/health") return json(200, { status: "ok" });
  if (route === "GET /openapi.json") {
    const product = url.searchParams.get("product");
    if (product && !PRODUCTS.includes(product)) {
      return error(404, "not_found", `Unknown product (${PRODUCTS.join(", ")})`);
    }
    return json(200, specFor(product));
  }
  if (route === "GET /") {
    return json(200, {
      name: openapi.info.title,
      version: openapi.info.version,
      docs: "/openapi.json",
    });
  }

  const [fn, product] = ROUTES[route] ?? [];
  if (!fn) {
    const known = Object.keys(ROUTES).some((r) => r.endsWith(` ${path}`));
    return known
      ? error(405, "method_not_allowed", "Use POST")
      : error(404, "not_found", "Unknown endpoint");
  }
  const secrets = parseSecrets(env.MARKETPLACE_SECRETS);
  if (secrets.length === 0 && env.ALLOW_UNAUTHENTICATED !== "true") {
    return error(503, "not_configured", "This API is not available yet");
  }
  if (secrets.length > 0 && !fromMarketplace(request, secrets, product)) {
    return error(403, "forbidden", "Please subscribe to this API on the marketplace");
  }
  try {
    return json(200, fn(await readJson(request)));
  } catch (err) {
    if (err instanceof InputError) {
      return error(400, "invalid_input", err.message, err.field ? { field: err.field } : {});
    }
    console.error(err);
    return error(500, "internal_error", "Unexpected error");
  }
}

export default { fetch: handle };
