import { test } from "node:test";
import assert from "node:assert/strict";
import { handle, parseSecrets } from "../src/worker.js";
import openapi from "../src/openapi.json" with { type: "json" };

const SECRET = "x-rapidapi-proxy-secret:s3cr3t,x-other-market:abc";
const LOCAL = { ALLOW_UNAUTHENTICATED: "true" }; // ローカル開発と同じ(秘密ヘッダーを確かめない)

async function call(method, path, { body, headers = {}, env = LOCAL } = {}) {
  const res = await handle(
    new Request(`https://api.example${path}`, {
      method,
      headers: { "content-type": "application/json", ...headers },
      body: body === undefined ? undefined : typeof body === "string" ? body : JSON.stringify(body),
    }),
    env,
  );
  return { status: res.status, body: await res.json() };
}
const salary = (body) => call("POST", "/v1/salary/analyze", { body });
const realty = (body) => call("POST", "/v1/realty/analyze", { body });

// 出力のキーが仕様書(OpenAPI)に書かれたものと一致するか
function matchesSchema(result, schemaName) {
  const schema = openapi.components.schemas[schemaName];
  for (const k of Object.keys(result)) {
    assert.ok(k in schema.properties, `${schemaName}: "${k}" が仕様書にない`);
  }
  for (const k of schema.required ?? []) assert.ok(k in result, `${schemaName}: "${k}" がない`);
}

test("給与: 月給の幅・賞与・年収例・実働時間(求人ページの実例)", async () => {
  const { status, body } = await salary({
    salary:
      "給与：月給24万2000円～46万8700円＋各種手当＋賞与年2回（昨年度実績：6.2ヶ月分） 年収例 550万円／30歳 850万円／40歳",
    workConditions: "勤務時間：9：00～17：30（実働7時間30分）",
  });
  assert.equal(status, 200);
  matchesSchema(body, "SalaryResult");
  assert.equal(body.found, true);
  assert.deepEqual(body.basis, { code: "monthly_salary", ja: "月給" });
  assert.deepEqual(body.monthly, { min: 242000, max: 468700 });
  assert.equal(body.bonusMonths, 6.2);
  assert.deepEqual(body.annual, {
    min: Math.round(242000 * 18.2),
    max: Math.round(468700 * 18.2),
    openEnded: false,
    bonusIncluded: true,
  });
  assert.equal(body.statedAnnual.type, "example");
  assert.equal(body.statedAnnual.min, 5500000);
  assert.equal(body.hoursPerDay, 7.5);
  assert.deepEqual(
    body.assumptions.map((a) => a.code),
    ["holidays_default_120"],
  );
  assert.match(body.assumptions[0].en, /120 annual holidays/);
});

test("給与: 固定残業代を除いた月給・時給、会社の平均年収の区別", async () => {
  const fixed = (
    await salary({
      salary: "月給30万円（固定残業代40時間分・5万円を含む）",
      workConditions: "実働8時間 年間休日125日",
    })
  ).body;
  assert.deepEqual(fixed.fixedOvertime, { hours: 40, amount: 50000 });
  assert.equal(fixed.withoutFixedOvertime.monthly, 250000);
  assert.equal(fixed.annualHolidays, 125);
  assert.deepEqual(fixed.assumptions, []);

  const avg = (await salary({ salary: "給与：月給25万円 平均年収：700万円" })).body;
  assert.equal(avg.statedAnnual.type, "company_average");
  assert.equal(avg.statedAnnual.companyAverage, true);

  const none = (await salary({ salary: "経験・能力を考慮の上、当社規定により優遇" })).body;
  assert.equal(none.found, false);
  assert.equal(none.annual, null);
});

test("給与: 時給・年俸も扱う", async () => {
  const hourly = (await salary({ salary: "時給1,500円" })).body;
  assert.equal(hourly.basis.code, "hourly_wage");
  assert.ok(hourly.monthly.min > 200000);
  assert.equal(hourly.hourlyEquivalent, null);
  const yearly = (await salary({ salary: "年俸600万円～900万円" })).body;
  assert.equal(yearly.basis, null);
  assert.deepEqual([yearly.annual.min, yearly.annual.max], [6000000, 9000000]);
});

test("物件: 賃貸(文字列の表記)", async () => {
  const { status, body } = await realty({
    rent: "12.5万円",
    managementFee: "8000円",
    depositAndKeyMoney: "1ヶ月 / 1ヶ月",
    area: "40.5m2",
  });
  assert.equal(status, 200);
  matchesSchema(body, "RealtyResult");
  assert.equal(body.type, "rent");
  assert.equal(body.monthlyTotal, 133000);
  assert.equal(body.pricePerSquareMeter, 3284);
  assert.equal(body.initialCostEstimate, 520500); // 12.5万×2 + 13.75万 + 13.3万
  assert.equal(body.assumptions[0].code, "initial_cost_basis");
});

test("物件: 数値で渡すと円・㎡・%として扱う", async () => {
  const text = (
    await realty({
      price: "1,850万円",
      grossYield: "5.8%",
      area: "25.2m²",
      managementFeeAndRepairReserve: "9,000円 / 6,500円",
    })
  ).body;
  const nums = (
    await realty({
      price: 18500000,
      grossYield: 5.8,
      area: 25.2,
      managementFeeAndRepairReserve: "9,000円 / 6,500円",
    })
  ).body;
  assert.deepEqual(nums, text);
  matchesSchema(nums, "RealtyResult");
  assert.equal(nums.type, "sale");
  assert.equal(nums.grossYieldPercent, 5.8);
  assert.equal(nums.annualIncome, 1073000);
  assert.equal(nums.netYieldPercent, 4.79);
});

test("物件: ローン条件の指定と既定値", async () => {
  const def = (await realty({ price: "3000万円" })).body;
  assert.deepEqual([def.loan.ratePercent, def.loan.years], [1, 35]);
  const custom = (await realty({ price: "3000万円", loanRatePercent: 2, loanYears: 25 })).body;
  assert.deepEqual([custom.loan.ratePercent, custom.loan.years], [2, 25]);
  assert.ok(custom.loan.monthlyPayment > def.loan.monthlyPayment);
  assert.match(custom.assumptions[0].en, /2% for 25 years/);
});

test("物件: 読めない時は found=false", async () => {
  assert.deepEqual((await realty({ price: "価格未定" })).body, {
    found: false,
    type: null,
    currency: "JPY",
  });
});

test("入力の誤りは 400 と項目名を返す", async () => {
  const cases = [
    [salary({}), "salary"],
    [salary({ salary: 300000 }), "salary"],
    [salary({ salary: "x".repeat(2001) }), "salary"],
    [realty({ rent: -1 }), "rent"],
    [realty({ depositAndKeyMoney: 1 }), "depositAndKeyMoney"],
    [realty({ price: "3000万円", loanRatePercent: 50 }), "loanRatePercent"],
    [realty({ price: "3000万円", loanYears: 1.5 }), "loanYears"],
  ];
  for (const [p, field] of cases) {
    const { status, body } = await p;
    assert.equal(status, 400);
    assert.equal(body.error.code, "invalid_input");
    assert.equal(body.error.field, field);
  }
  const broken = await call("POST", "/v1/salary/analyze", { body: "{not json" });
  assert.equal(broken.status, 400);
  const array = await call("POST", "/v1/salary/analyze", { body: "[]" });
  assert.equal(array.status, 400);
  const big = await call("POST", "/v1/salary/analyze", {
    body: JSON.stringify({ salary: "x".repeat(17000) }),
  });
  assert.equal(big.status, 400);
});

test("マーケットの秘密ヘッダーが無い・違う呼び出しは断る", async () => {
  const env = { MARKETPLACE_SECRETS: SECRET };
  const body = { salary: "月給30万円" };
  const path = "/v1/salary/analyze";
  assert.equal((await call("POST", path, { body, env })).status, 403);
  assert.equal(
    (await call("POST", path, { body, env, headers: { "x-rapidapi-proxy-secret": "wrong" } }))
      .status,
    403,
  );
  assert.equal(
    (await call("POST", path, { body, env, headers: { "X-RapidAPI-Proxy-Secret": "s3cr3t" } }))
      .status,
    200,
  );
  assert.equal(
    (await call("POST", path, { body, env, headers: { "x-other-market": "abc" } })).status,
    200,
  );
  // 稼働確認と仕様書は認証なしで見られる
  assert.equal((await call("GET", "/v1/health", { env })).status, 200);
  assert.equal((await call("GET", "/openapi.json", { env })).body.openapi, "3.1.0");
});

test("秘密ヘッダーが未設定なら、既定では計算APIを使えない(無料で公開されないように)", async () => {
  const res = await call("POST", "/v1/salary/analyze", { body: { salary: "月給30万円" }, env: {} });
  assert.equal(res.status, 503);
  assert.equal(res.body.error.code, "not_configured");
  assert.equal((await call("GET", "/v1/health", { env: {} })).status, 200);
});

test("秘密ヘッダーの設定の読み取り", () => {
  assert.deepEqual(parseSecrets(" X-RapidAPI-Proxy-Secret : abc , bad, x-b:c:d ,"), [
    ["x-rapidapi-proxy-secret", "abc"],
    ["x-b", "c:d"],
  ]);
  assert.deepEqual(parseSecrets(undefined), []);
});

test("存在しないパス・メソッド違い", async () => {
  assert.equal((await call("GET", "/nope")).status, 404);
  assert.equal((await call("GET", "/v1/salary/analyze")).status, 405);
  assert.equal(
    (await call("POST", "/v1/salary/analyze/", { body: { salary: "月給30万円" } })).status,
    200,
  );
});

test("仕様書のパスと実装のルートが一致する", () => {
  assert.deepEqual(Object.keys(openapi.paths).sort(), [
    "/v1/health",
    "/v1/realty/analyze",
    "/v1/salary/analyze",
  ]);
});
