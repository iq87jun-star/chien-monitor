// parser.js の単体テスト。「実例」は en転職の求人詳細ページ(2026-09-23 閲覧)の給与・勤務時間欄の
// 表記をそのまま使っている(金額の書き方の揺れを確かめるため)。それ以外は想定される表記の例。
import { test } from "node:test";
import assert from "node:assert/strict";
import "../src/parser.js";

const P = globalThis.JobParser;

test("金額の表記揺れを円に直す", () => {
  assert.equal(P.parseYen("30万4,240円"), 304240);
  assert.equal(P.parseYen("24万2000円"), 242000);
  assert.equal(P.parseYen("23.85万円"), 238500);
  assert.equal(P.parseYen("300,000円"), 300000);
  assert.equal(P.parseYen("３０万円"), 300000);
  assert.equal(P.parseYen("未定"), null);
});

test("実例: 月給の幅と賞与の月数から年収目安を出す", () => {
  const r = P.analyze(
    "給与：月給24万2000円～46万8700円＋各種手当＋賞与年2回（昨年度実績：6.2ヶ月分） 年収例 550万円／30歳 850万円／40歳",
    "勤務時間：9：00～17：30（実働7時間30分）",
  );
  assert.deepEqual(r.monthly, { min: 242000, max: 468700 });
  assert.equal(r.bonusMonths, 6.2);
  assert.deepEqual(r.annual, {
    min: Math.round(242000 * 18.2),
    max: Math.round(468700 * 18.2),
    open: false,
    bonusIncluded: true,
    from: "月給",
  });
  assert.equal(r.stated.min, 5500000);
  assert.equal(r.stated.open, false, "「年収例 550万円」は単独の金額");
  assert.equal(r.hoursPerDay, 7.5);
  assert.deepEqual(r.assumptions, ["年間休日120日"]);
});

test("実例: 下限だけの月給と「みなし残業なし」", () => {
  const r = P.analyze(
    "給与：月給30万4,240円～＋賞与（4.65ヶ月分） ※みなし残業はありません。残業が発生した際は、全額支給いたします。",
    "勤務時間：9：30～18：15（実働7時間45分）",
  );
  assert.deepEqual(r.monthly, { min: 304240, max: null });
  assert.equal(r.annual.min, Math.round(304240 * 16.65));
  assert.equal(r.annual.max, null);
  assert.equal(r.annual.open, true, "「月給30万4,240円～」は上限なしの幅");
  assert.equal(r.fixedOvertime, null, "「みなし残業はありません」は固定残業代として扱わない");
  assert.equal(r.hoursPerDay, 7.75);
});

test("実例: 会社の平均年収より、この求人の想定年収を優先する", () => {
  const r = P.analyze(
    "給与：平均年収：2178万円（2025年度） 月給29万9000円～33万1000円 ※一律手当含む。 年収例 [初年度想定年収] 1200万円～2000万円",
  );
  assert.equal(r.stated.kind, "想定年収");
  assert.deepEqual([r.stated.min, r.stated.max], [12000000, 20000000]);
  assert.equal(r.stated.companyAverage, false);
});

test("平均年収しか無い時は会社の平均として扱う", () => {
  const r = P.analyze("給与：月給25万円 平均年収：700万円");
  assert.equal(r.stated.companyAverage, true);
});

test("実例: 年収例の語と金額が離れていても読む", () => {
  const r = P.analyze(
    "給与：【関東】 東京／30.05万円 年収例 <入社初年度の年収イメージ> ■首都圏（東京）：478万円 ■その他：340万円～440万円",
  );
  assert.equal(r.stated.min, 4780000);
  assert.equal(r.found, true);
});

test("見出しが「想定年収」で本文が金額だけでも読む", () => {
  const r = P.analyze("想定年収：400万円～600万円");
  assert.deepEqual([r.stated.min, r.stated.max], [4000000, 6000000]);
});

test("固定残業代を検出し、除いた月給と時給を出す", () => {
  const r = P.analyze(
    "給与：月給28万円（固定残業代月30時間分、5万2000円を含む）超過分は別途支給 賞与年2回",
    "休日・休暇：年間休日125日",
  );
  assert.deepEqual(r.fixedOvertime, { hours: 30, amount: 52000 });
  assert.equal(r.baseWithoutOvertime.monthly, 228000);
  assert.equal(r.holidays, 125);
  // 賞与は回数だけで月数が無いので年収目安には含めない
  assert.equal(r.annual.bonusIncluded, false);
  assert.equal(r.annual.min, 280000 * 12);
  const monthlyHours = ((365 - 125) / 12) * 8;
  assert.equal(r.baseWithoutOvertime.hourly, Math.round(228000 / monthlyHours));
});

test("時給の求人は月額・年収に換算する", () => {
  const r = P.analyze(
    "給与：時給1,300円～1,500円 交通費支給",
    "勤務時間：9:00～18:00（実働8時間）",
  );
  assert.equal(r.basis, "時給");
  assert.equal(r.hourlyEquivalent, null, "時給の求人に時給換算は出さない");
  assert.equal(r.annual.min, Math.round(1300 * 20.4 * 8 * 12));
});

test("年俸の求人は年俸をそのまま年収目安にする", () => {
  const r = P.analyze("給与：年俸600万円～900万円（月給50万円～75万円）");
  assert.equal(r.annual.from, "年俸");
  assert.deepEqual([r.annual.min, r.annual.max], [6000000, 9000000]);
});

test("賞与の月数は「ヵ月」「カ月」の表記も読む", () => {
  assert.equal(P.analyze("給与：月給25万円 賞与年2回（計4.5ヵ月分）").bonusMonths, 4.5);
  assert.equal(P.analyze("給与：月給25万円 賞与年2回（計3カ月分）").bonusMonths, 3);
});

test("給与の記載が読めなければ found は false", () => {
  assert.equal(P.analyze("給与：経験・能力を考慮の上、当社規定により優遇").found, false);
  assert.equal(P.analyze("").found, false);
});
