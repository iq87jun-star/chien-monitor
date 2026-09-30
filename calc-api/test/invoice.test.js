import { test } from "node:test";
import assert from "node:assert/strict";
import { holidayRuleOf, parseTerms, paymentDate, withholding, withholdingTax } from "../src/invoice.js";

const fails = (fn, field) => assert.throws(fn, (e) => e.field === field);
const pay = (date, terms, extra = {}) => paymentDate({ date, terms, ...extra });

test("支払条件の文章を読む(表記の揺れ・全角)", () => {
  assert.deepEqual(parseTerms("末締め翌月25日払い"), {
    closingDay: "end",
    paymentMonthOffset: 1,
    paymentDay: 25,
    holidayRule: null,
  });
  assert.deepEqual(parseTerms("月末締め翌々月10日支払"), {
    closingDay: "end",
    paymentMonthOffset: 2,
    paymentDay: 10,
    holidayRule: null,
  });
  assert.deepEqual(parseTerms("２０日締め　翌月末日払い（休日の場合は翌営業日）"), {
    closingDay: 20,
    paymentMonthOffset: 1,
    paymentDay: "end",
    holidayRule: "next",
  });
  assert.equal(parseTerms("15日締め当月末払い").paymentMonthOffset, 0);
  assert.equal(parseTerms("末日締め、3ヶ月後の末日払い").paymentMonthOffset, 3);
  assert.equal(parseTerms("翌月末払い").closingDay, null);
  assert.equal(parseTerms("末締め翌月25日払い、休日は前営業日").holidayRule, "previous");
  assert.equal(parseTerms("よろしくお願いします").paymentDay, null);
  // 「払い」が無い・後ろに括弧が続く書き方
  assert.deepEqual(parseTerms("末締め翌月25日（休日は前営業日）"), {
    closingDay: "end",
    paymentMonthOffset: 1,
    paymentDay: 25,
    holidayRule: "previous",
  });
  assert.equal(parseTerms("毎月20日締め、翌月10日振込").paymentDay, 10);
});

test("支払日: 末締め翌月25日払い。25日が日曜なら前営業日(既定)、指定で翌営業日", () => {
  const r = pay("2026-09-15", "末締め翌月25日払い");
  assert.equal(r.closingDate, "2026-09-30");
  assert.equal(r.scheduledDate, "2026-10-25");
  assert.equal(r.paymentDate.date, "2026-10-23");
  assert.equal(r.paymentDate.weekdayJa, "金");
  assert.equal(r.adjusted, true);
  assert.equal(r.daysUntilPayment, 38);
  assert.deepEqual(r.terms, {
    closingDay: "end",
    paymentMonthOffset: 1,
    paymentDay: 25,
    holidayRule: "previous",
  });
  assert.equal(pay("2026-09-15", "末締め翌月25日払い(休日の場合は翌営業日)").paymentDate.date, "2026-10-26");
  // 文章より項目の指定を優先する
  assert.equal(pay("2026-09-15", "末締め翌月25日払い", { holidayRule: "none" }).paymentDate.date, "2026-10-25");
});

test("支払日: 締め日をまたぐ・月末・2月・祝日の連続", () => {
  // 20日を過ぎたら次の締め(10/20)→ 翌月末(11/30 月曜)
  const late = pay("2026-09-25", "20日締め翌月末払い");
  assert.equal(late.closingDate, "2026-10-20");
  assert.equal(late.paymentDate.date, "2026-11-30");
  assert.equal(late.adjusted, false);
  // 締め日当日はその締めに入る。10/31 は土曜 → 10/30
  assert.equal(pay("2026-09-20", "20日締め翌月末払い").paymentDate.date, "2026-10-30");
  assert.equal(pay("2026-11-05", "15日締め当月末払い").paymentDate.date, "2026-11-30");
  // 2月に30日は無い → 2/28(日)→ 前営業日 2/26
  assert.equal(pay("2027-01-31", "末締め翌月30日払い").scheduledDate, "2027-02-28");
  assert.equal(pay("2027-01-31", "末締め翌月30日払い").paymentDate.date, "2027-02-26");
  // 1/10(日)→ 1/11 成人の日 → 1/12
  assert.equal(pay("2026-12-10", "末締め翌月10日払い 休日は翌営業日").paymentDate.date, "2027-01-12");
  // 年をまたぐ翌々月
  assert.equal(pay("2026-11-20", "末締め翌々月末払い").scheduledDate, "2027-01-31");
});

test("支払日: 項目で指定・独自の休業日", () => {
  const r = paymentDate({
    date: "2026-09-10",
    closingDay: 20,
    paymentMonthOffset: 2,
    paymentDay: "end",
    holidayRule: "none",
  });
  assert.equal(r.closingDate, "2026-09-20");
  assert.equal(r.paymentDate.date, "2026-11-30");
  // 11/30 を休業日にすると前営業日の 11/27(金)
  assert.equal(
    pay("2026-09-25", "20日締め翌月末払い", { closedDates: ["2026-11-30"] }).paymentDate.date,
    "2026-11-27",
  );
  // 締め日の既定は月末
  assert.equal(paymentDate({ date: "2026-09-15", paymentDay: 10 }).scheduledDate, "2026-10-10");
});

test("支払日: 入力の誤り", () => {
  fails(() => pay("2026-09-15", "よろしくお願いします"), "terms");
  fails(() => paymentDate({ date: "2026-09-15" }), "paymentDay");
  fails(() => paymentDate({ date: "2026-09-15", paymentDay: 32 }), "paymentDay");
  fails(() => paymentDate({ date: "2026-09-15", paymentDay: 10, closingDay: 0 }), "closingDay");
  fails(() => pay("2026-09-15", "末締め翌月25日払い", { holidayRule: "later" }), "holidayRule");
  fails(() => pay("2026-09-15", "末締め翌月25日払い", { paymentMonthOffset: 13 }), "paymentMonthOffset");
  fails(() => pay("2026-02-30", "末締め翌月25日払い"), "date");
  fails(() => pay("2026-09-15", "x".repeat(101)), "terms");
});

test("源泉徴収: 100万円以下は10.21%、超える部分は20.42%(1円未満切り捨て)", () => {
  assert.equal(withholdingTax(100_000), 10_210);
  assert.equal(withholdingTax(12_345), 1_260);
  assert.equal(withholdingTax(1_000_000), 102_100);
  assert.equal(withholdingTax(1_000_001), 102_100);
  assert.equal(withholdingTax(1_500_000), 204_200);
  assert.equal(withholdingTax(0), 0);
});

test("源泉徴収: 請求書の合計・差引の支払額", () => {
  const r = withholding({ amount: 100_000 });
  assert.equal(r.consumptionTax, 10_000);
  assert.equal(r.invoiceTotal, 110_000);
  assert.equal(r.withholdingTax, 10_210);
  assert.equal(r.netPayment, 99_790);
  assert.deepEqual(r.assumptions.map((a) => a.code), ["general_fees"]);
  const big = withholding({ amount: 1_500_000 });
  assert.equal(big.netPayment, 1_650_000 - 204_200);
  assert.equal(withholding({ amount: 100_000, taxRate: 0.08 }).consumptionTax, 8_000);
  // 消費税を区分しない(税込の額)→ 税込の額に源泉徴収
  const inc = withholding({ amount: 110_000, amountIncludesTax: true });
  assert.equal(inc.consumptionTax, null);
  assert.equal(inc.withholdingTax, 11_231);
  assert.equal(inc.netPayment, 98_769);
  assert.deepEqual(inc.assumptions.map((a) => a.code), ["general_fees", "tax_not_separated"]);
});

test("源泉徴収: 入力の誤り", () => {
  fails(() => withholding({}), "amount");
  fails(() => withholding({ amount: -1 }), "amount");
  fails(() => withholding({ amount: 1.5 }), "amount");
  fails(() => withholding({ amount: "10万円" }), "amount");
  fails(() => withholding({ amount: 1000, taxRate: 0.05 }), "taxRate");
  fails(() => withholding({ amount: 1000, amountIncludesTax: "yes" }), "amountIncludesTax");
});

test("休日の扱いの書き方(シート・Excel の引数)", () => {
  assert.equal(holidayRuleOf("前営業日"), "previous");
  assert.equal(holidayRuleOf("翌"), "next");
  assert.equal(holidayRuleOf("NEXT"), "next");
  assert.equal(holidayRuleOf("なし"), "none");
  assert.equal(holidayRuleOf(""), undefined);
  fails(() => holidayRuleOf("適当"), "holidayRule");
});
