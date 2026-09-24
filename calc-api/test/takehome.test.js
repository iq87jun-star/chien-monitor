import { test } from "node:test";
import assert from "node:assert/strict";
import {
  calculateTakeHome,
  incomeTax,
  prefectureKey,
  salaryIncomeForIncomeTax2026,
  salaryIncomeStandard,
  standardMonthly,
} from "../src/takehome.js";
import openapi from "../src/openapi.json" with { type: "json" };

test("月給30万円・賞与なし・東京・30歳(手計算と一致)", () => {
  const r = calculateTakeHome({ monthlySalary: 300000 });
  // 健康保険 300,000×9.85%÷2=14,775 / 子ども・子育て支援金 345 / 厚生年金 27,450 / 雇用保険 1,500(各×12)
  assert.deepEqual(
    [
      r.socialInsurance.healthInsurance,
      r.socialInsurance.childSupportLevy,
      r.socialInsurance.pension,
      r.socialInsurance.employmentInsurance,
    ],
    [177300, 4140, 329400, 18000],
  );
  assert.equal(r.socialInsurance.nursingCareInsurance, 0);
  assert.equal(r.socialInsurance.total, 528840);
  // 所得税: 給与所得244万 − 社保528,840 − 基礎控除104万 = 871,000 × 5% × 1.021 → 44,400
  assert.equal(r.incomeTax, 44400);
  // 住民税: (244万 − 528,840 − 43万) → 1,481,000 × 10% − 調整控除2,500 + 均等割5,000
  assert.equal(r.residentTax, 150600);
  assert.equal(r.takeHomeAnnual, 2876160);
  assert.equal(r.takeHomeMonthlyAverage, 239680);
  const schema = openapi.components.schemas.TakeHomeResult;
  for (const k of Object.keys(r)) assert.ok(k in schema.properties, `仕様書に ${k} がない`);
});

test("2026年の改正: 給与収入178万円までは所得税がかからない", () => {
  // 特例で給与所得控除は74万円、基礎控除は104万円(合計178万円)
  assert.equal(salaryIncomeForIncomeTax2026(1_780_000), 1_040_000);
  assert.equal(salaryIncomeForIncomeTax2026(690_000), 0);
  assert.equal(salaryIncomeForIncomeTax2026(2_195_000), 1_453_000);
  assert.equal(salaryIncomeForIncomeTax2026(2_200_000), 1_460_000); // 本則 0.7×220万−8万
  const r = calculateTakeHome({ monthlySalary: 150000 });
  assert.equal(r.incomeTax, 0);
  assert.ok(r.residentTax > 0, "住民税(基礎控除43万円)はかかる");
});

test("給与所得の本則(4千円単位)と所得税の税率表", () => {
  assert.equal(salaryIncomeStandard(3_600_000), 2_440_000);
  assert.equal(salaryIncomeStandard(5_003_999), 5_000_000 * 0.8 - 440_000);
  assert.equal(salaryIncomeStandard(7_000_000), 5_200_000);
  assert.equal(salaryIncomeStandard(10_000_000), 8_050_000);
  assert.equal(salaryIncomeStandard(1_000_000), 310_000); // 最低69万円
  assert.equal(incomeTax(1_000_000), Math.floor((50_000 * 1.021) / 100) * 100);
  assert.equal(incomeTax(5_000_000), Math.floor(((5_000_000 * 0.2 - 427_500) * 1.021) / 100) * 100);
  assert.equal(incomeTax(-5), 0);
});

test("標準報酬月額の等級と上限", () => {
  assert.equal(standardMonthly(62_999), 58_000);
  assert.equal(standardMonthly(300_000), 300_000);
  assert.equal(standardMonthly(309_999), 300_000);
  assert.equal(standardMonthly(310_000), 320_000);
  assert.equal(standardMonthly(5_000_000), 1_390_000);
  const high = calculateTakeHome({ monthlySalary: 1_000_000 });
  assert.equal(high.socialInsurance.standardMonthlyRemuneration.pension, 650_000); // 厚生年金の上限
  assert.equal(high.socialInsurance.pension, 650_000 * 0.0915 * 12);
});

test("40歳以上は介護保険、都道府県で健康保険料率が変わる", () => {
  const tokyo = calculateTakeHome({ monthlySalary: 400000, age: 45 });
  // 月給40万円は標準報酬月額41万円の等級(39.5万〜42.5万円)
  assert.equal(tokyo.socialInsurance.standardMonthlyRemuneration.health, 410000);
  assert.equal(tokyo.socialInsurance.nursingCareInsurance, ((410000 * 0.0162) / 2) * 12);
  const saga = calculateTakeHome({ monthlySalary: 400000, age: 45, prefecture: "佐賀県" });
  assert.equal(saga.rates.healthInsurancePercent, 10.55);
  assert.ok(saga.takeHomeAnnual < tokyo.takeHomeAnnual);
  assert.equal(
    calculateTakeHome({ monthlySalary: 400000, age: 65 }).socialInsurance.nursingCareInsurance,
    0,
  );
});

test("賞与: 回数で分けて保険料を計算し、厚生年金は1回150万円が上限", () => {
  const r = calculateTakeHome({ monthlySalary: 500000, annualBonus: 4_000_000, bonusTimes: 2 });
  assert.equal(r.grossAnnual, 10_000_000);
  // 厚生年金: 毎月 500,000×9.15%×12 + 賞与(150万×9.15%)×2
  assert.equal(r.socialInsurance.pension, 45750 * 12 + 137250 * 2);
  assert.ok(r.assumptions.some((a) => a.code === "bonus_split"));
});

test("都道府県の書き方と入力の検査", () => {
  assert.equal(prefectureKey("東京都"), "東京");
  assert.equal(prefectureKey("Osaka-fu"), "大阪");
  assert.equal(prefectureKey("北海道"), "北海道");
  assert.equal(prefectureKey("hokkaido"), "北海道");
  assert.equal(prefectureKey("京都府"), "京都");
  assert.equal(prefectureKey("Kyoto"), "京都");
  assert.equal(prefectureKey("Tokyo-to"), "東京");
  assert.equal(prefectureKey("Aichi Prefecture"), "愛知");
  assert.equal(prefectureKey("aichi-ken"), "愛知");
  assert.equal(prefectureKey("どこか"), null);
  for (const [body, field] of [
    [{}, "monthlySalary"],
    [{ monthlySalary: "30万" }, "monthlySalary"],
    [{ monthlySalary: 300000, prefecture: "Atlantis" }, "prefecture"],
    [{ monthlySalary: 300000, age: 10 }, "age"],
    [{ monthlySalary: 300000, year: 2025 }, "year"],
    [{ monthlySalary: 300000, annualBonus: 100, bonusTimes: 0 }, "bonusTimes"],
  ]) {
    assert.throws(
      () => calculateTakeHome(body),
      (e) => e.field === field,
    );
  }
});
