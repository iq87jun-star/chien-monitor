// parser.js の単体テスト。「実例」は不動産ポータルの物件詳細ページ(2026-09-23 閲覧)の
// 項目の表記をそのまま使っている(金額・面積の書き方の揺れを確かめるため)。
import { test } from "node:test";
import assert from "node:assert/strict";
import "../src/parser.js";

const R = globalThis.RealtyParser;

test("金額の表記揺れを円に直す", () => {
  assert.equal(R.parseYen("14万円"), 140000);
  assert.equal(R.parseYen("7.5万円"), 75000);
  assert.equal(R.parseYen("10000円"), 10000);
  assert.equal(R.parseYen("1万4800円／月（自主管理(管理員なし)）"), 14800);
  assert.equal(R.parseYen("3,230万円"), 32300000);
  assert.equal(R.parseYen("1億2000万円"), 120000000);
  assert.equal(R.parseYen("1億円"), 100000000);
  assert.equal(R.parseYen("-"), null);
});

test("面積の表記揺れを㎡に直す", () => {
  assert.equal(R.parseArea("20m2"), 20);
  assert.equal(R.parseArea("56.88m² （バルコニー 2m²）"), 56.88);
  assert.equal(R.parseArea("51.58m2（壁芯）"), 51.58);
  assert.equal(R.parseArea("48.5㎡"), 48.5);
  assert.ok(Math.abs(R.parseArea("10坪") - 10 / 0.3025) < 1e-9);
});

test("元利均等の毎月返済額", () => {
  // 2880万円・年1%・35年 ≒ 81,298円(一般的なローン計算機と同じ値)
  assert.equal(Math.round(R.monthlyPayment(28_800_000, 0.01, 35)), 81298);
  assert.equal(R.monthlyPayment(1_200_000, 0, 10), 10000);
});

test("実例(賃貸): 実質月額・単価・初期費用", () => {
  const r = R.analyze({
    rent: "14万円",
    fee: "10000円",
    depositKey: "14万円 / 14万円",
    area: "20m2",
  });
  assert.equal(r.kind, "rent");
  assert.equal(r.monthly, 150000);
  assert.equal(r.perM2, 7500);
  assert.equal(r.perTsubo, Math.round(150000 / (20 * 0.3025)));
  // 敷金14万+礼金14万+仲介手数料15.4万+前家賃15万
  assert.equal(r.initialCost, 140000 + 140000 + 154000 + 150000);
});

test("敷金・礼金の「ヶ月」「なし」「-」表記", () => {
  const r = R.analyze({ rent: "8万円", depositKey: "1ヶ月 / なし", area: "25m2" });
  assert.equal(r.deposit, 80000);
  assert.equal(r.keyMoney, 0);
  const r2 = R.analyze({ rent: "8万円", deposit: "-", keyMoney: "2ヵ月", area: "25m2" });
  assert.equal(r2.deposit, 0);
  assert.equal(r2.keyMoney, 160000);
});

test("敷金・礼金が読めなければ初期費用は出さない", () => {
  const r = R.analyze({ rent: "8万円", area: "25m2" });
  assert.equal(r.initialCost, null);
  assert.deepEqual(r.assumptions, []);
});

test("実例(中古マンション): 単価と月々の支払い(管理費・修繕積立金が別欄)", () => {
  const r = R.analyze(
    {
      price: "2880万円 [ □支払シミュレーション ]",
      area: "51.58m2（壁芯）",
      fee: "1万4800円／月（自主管理(管理員なし)）",
      repair: "5980円／月",
    },
    { loanRate: 0.01, loanYears: 35 },
  );
  assert.equal(r.kind, "sale");
  assert.equal(r.perM2, Math.round(28_800_000 / 51.58));
  assert.equal(r.loanPayment, 81298);
  assert.equal(r.monthlyTotal, 81298 + 14800 + 5980);
  assert.equal(r.grossYield, null);
});

test("実例(投資): 利回りから年間収入を逆算し、簡易実質利回りを出す(管理費/修繕積立が1欄)", () => {
  const r = R.analyze({
    price: "3,230万円",
    yield: "5.05％ 利回りの詳細を問い合わせる",
    feeRepair: "6,000円 / 8,870円",
    area: "56.88m² （バルコニー 2m²）",
  });
  assert.equal(r.fee, 6000);
  assert.equal(r.repair, 8870);
  assert.equal(r.annualIncome, Math.round(32_300_000 * 0.0505));
  assert.ok(Math.abs(r.netYield - (r.annualIncome - 14870 * 12) / 32_300_000) < 1e-12);
});

test("年間収入から表面利回りを計算する", () => {
  const r = R.analyze({ price: "5000万円", income: "400万円" });
  assert.equal(r.grossYield, 0.08);
  assert.equal(r.netYield, null, "管理費等が無ければ簡易実質は出さない");
});

test("ローン条件はオプションで変えられる", () => {
  const r = R.analyze({ price: "3000万円" }, { loanRate: 0.02, loanYears: 25 });
  assert.equal(r.loanPayment, Math.round(R.monthlyPayment(30_000_000, 0.02, 25)));
  assert.match(r.assumptions[0], /金利2%・25年/);
});

test("賃料・価格が読めなければ null", () => {
  assert.equal(R.analyze({ area: "20m2" }), null);
  assert.equal(R.analyze({ price: "価格未定" }), null);
});
