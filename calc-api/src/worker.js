// Cloudflare Worker: 日本の求人の給与・物件情報の計算API。API マーケット経由で販売する。
//   POST /v1/salary/analyze   求人の給与の文章 → 年収の目安・時給換算・固定残業代
//   POST /v1/realty/analyze   物件の賃料・価格・面積等 → 単価・実質月額・初期費用・ローン返済・利回り
//   GET  /v1/health           稼働確認(認証不要)
//   GET  /openapi.json        API の仕様(マーケットへの登録に使う)
// APIキーの発行・回数制限・課金はマーケットが行う。こちらはマーケットが付ける秘密のヘッダーを確かめ、
// マーケットを通さない直接の呼び出しを断る。MARKETPLACE_SECRETS が未設定なら計算APIは使えない
// (設定し忘れて無料で公開されないように)。ローカル開発だけ ALLOW_UNAUTHENTICATED=true で確かめない。
import { InputError, analyzeRealty, analyzeSalary } from "./calc.js";
import openapi from "./openapi.json" with { type: "json" };

const MAX_BODY = 16 * 1024;

const json = (status, body) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
const error = (status, code, message, extra = {}) =>
  json(status, { error: { code, message, ...extra } });

// MARKETPLACE_SECRETS: 「ヘッダー名:値」をカンマ区切りで複数(マーケットごと)
//   例: x-rapidapi-proxy-secret:abc123,x-zyla-secret:def456
export function parseSecrets(value) {
  return String(value ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => {
      const i = s.indexOf(":");
      return i > 0 ? [s.slice(0, i).trim().toLowerCase(), s.slice(i + 1).trim()] : null;
    })
    .filter((p) => p && p[1]);
}

function safeEqual(a, b) {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function fromMarketplace(request, secrets) {
  return secrets.some(([header, value]) => {
    const got = request.headers.get(header);
    return got != null && safeEqual(got, value);
  });
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

const ROUTES = {
  "POST /v1/salary/analyze": analyzeSalary,
  "POST /v1/realty/analyze": analyzeRealty,
};

export async function handle(request, env = {}) {
  const url = new URL(request.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const route = `${request.method} ${path}`;

  if (route === "GET /v1/health") return json(200, { status: "ok" });
  if (route === "GET /openapi.json") return json(200, openapi);
  if (route === "GET /") {
    return json(200, {
      name: openapi.info.title,
      version: openapi.info.version,
      docs: "/openapi.json",
    });
  }

  const fn = ROUTES[route];
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
  if (secrets.length > 0 && !fromMarketplace(request, secrets)) {
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
