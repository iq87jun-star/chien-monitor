// E2Eテスト: ローカルで Worker(wrangler dev)を起動し、マーケット経由の呼び出しと同じ形で API を呼ぶ。
import { spawn } from "node:child_process";
import assert from "node:assert/strict";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const SECRET = "e2e-secret";
const CAL_SECRET = "e2e-calendar-only";

const freePort = () =>
  new Promise((resolve) => {
    const srv = http.createServer().listen(0, "127.0.0.1", () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });

const PORT = await freePort();
const BASE = `http://127.0.0.1:${PORT}`;
const worker = spawn(
  path.join(ROOT, "node_modules", ".bin", "wrangler"),
  [
    "dev",
    "--port",
    String(PORT),
    "--ip",
    "127.0.0.1",
    "--inspector-port",
    String(await freePort()),
    "--var",
    `MARKETPLACE_SECRETS:x-rapidapi-proxy-secret:${SECRET},x-rapidapi-proxy-secret:${CAL_SECRET}@calendar`,
  ],
  { cwd: ROOT, stdio: ["ignore", "pipe", "pipe"], detached: true },
);
let log = "";
worker.stdout.on("data", (d) => (log += d));
worker.stderr.on("data", (d) => (log += d));

let failed = false;
try {
  for (let i = 0; ; i++) {
    try {
      if ((await fetch(`${BASE}/v1/health`)).ok) break;
    } catch {}
    if (i > 60) throw new Error(`wrangler dev が起動しません\n${log}`);
    await new Promise((r) => setTimeout(r, 500));
  }
  const post = (p, body, headers = {}) =>
    fetch(`${BASE}${p}`, {
      method: "POST",
      headers: { "content-type": "application/json", ...headers },
      body: JSON.stringify(body),
    });
  const viaMarket = { "X-RapidAPI-Proxy-Secret": SECRET };

  const direct = await post("/v1/salary/analyze", { salary: "月給30万円" });
  assert.equal(direct.status, 403);
  console.log("ok - マーケットを通さない呼び出しは 403");

  const s = await post(
    "/v1/salary/analyze",
    { salary: "月給25万円～＋賞与年2回（計4.5ヵ月分） 固定残業代（30時間分／4万円）を含む" },
    viaMarket,
  );
  assert.equal(s.status, 200);
  const sb = await s.json();
  assert.equal(sb.annual.min, 250000 * 16.5);
  assert.deepEqual(sb.fixedOvertime, { hours: 30, amount: 40000 });
  console.log("ok - 給与の計算(賞与・固定残業代)");

  const r = await post(
    "/v1/realty/analyze",
    { rent: 85000, managementFee: 5000, area: 25 },
    viaMarket,
  );
  const rb = await r.json();
  assert.equal(rb.monthlyTotal, 90000);
  assert.equal(rb.pricePerSquareMeter, 3600);
  console.log("ok - 物件の計算(数値で指定)");

  const t = await post("/v1/takehome/calculate", { monthlySalary: 300000 }, viaMarket);
  assert.equal((await t.json()).takeHomeAnnual, 2876160);
  console.log("ok - 手取りの計算(2026年の率)");

  const viaCalendar = { "X-RapidAPI-Proxy-Secret": CAL_SECRET };
  const c = await post(
    "/v1/calendar/add-business-days",
    { date: "2026-09-18", days: 1 },
    viaCalendar,
  );
  assert.equal((await c.json()).result.date, "2026-09-24");
  const w = await post("/v1/wareki/convert", { wareki: "R6.4.1" }, viaCalendar);
  assert.equal((await w.json()).date, "2024-04-01");
  const denied = await post("/v1/takehome/calculate", { monthlySalary: 300000 }, viaCalendar);
  assert.equal(denied.status, 403);
  console.log("ok - カレンダー専用の秘密の値ではカレンダーだけ使える");

  const spec = await (await fetch(`${BASE}/openapi.json`)).json();
  assert.equal(spec.info.title, "Japan Salary, Tax & Calendar Calculator API");
  const calSpec = await (await fetch(`${BASE}/openapi.json?product=calendar`)).json();
  assert.equal(calSpec.info.title, "Japan Holidays, Business Days & Wareki API");
  console.log("ok - 仕様書(OpenAPI)を配信");
} catch (err) {
  failed = true;
  console.error("not ok -", err.message);
} finally {
  try {
    process.kill(-worker.pid);
  } catch {}
}
process.exit(failed ? 1 : 0);
