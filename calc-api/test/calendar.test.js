import { test } from "node:test";
import assert from "node:assert/strict";
import {
  RANGE,
  addBusinessDays,
  calendarDay,
  calendarHolidays,
  convertWareki,
  countBusinessDays,
  parseDate,
} from "../src/calendar.js";

const fails = (fn, field) => assert.throws(fn, (e) => e.field === field);

test("祝日データ(内閣府)の範囲と2026年の祝日", () => {
  assert.equal(RANGE.from, "1955-01-01");
  assert.ok(RANGE.to >= "2027-12-31");
  const y = calendarHolidays({ year: 2026 });
  assert.equal(y.count, 18);
  assert.deepEqual(
    y.holidays.filter((h) => h.date.startsWith("2026-09")).map((h) => h.name),
    ["敬老の日", "休日", "秋分の日"],
  );
  fails(() => calendarHolidays({ year: 1900 }), "year");
});

test("日付の判定: 祝日・国民の休日・土日・和暦", () => {
  const d = calendarDay({ date: "2026-09-22" });
  assert.equal(d.isHoliday, true);
  assert.equal(d.holidayName, "休日");
  assert.equal(d.isBusinessDay, false);
  assert.equal(d.weekdayJa, "火");
  assert.equal(d.wareki.text, "令和8年9月22日");
  assert.equal(calendarDay({ date: "2026/9/24" }).isBusinessDay, true);
  assert.equal(calendarDay({ date: "2026-09-26" }).isBusinessDay, false); // 土曜
  assert.equal(calendarDay({ date: "2019-05-01" }).holidayName, "休日（祝日扱い）");
  fails(() => calendarDay({ date: "2026-02-30" }), "date");
  fails(() => calendarDay({ date: "1900-01-01" }), "date");
  assert.equal(parseDate("2026-2-3"), "2026-02-03");
});

test("営業日の加算: 連休をまたぐ・年末年始・前へ戻る・独自の休業日", () => {
  assert.equal(addBusinessDays({ date: "2026-09-18", days: 1 }).result.date, "2026-09-24");
  assert.equal(addBusinessDays({ date: "2026-09-24", days: -3 }).result.date, "2026-09-16");
  assert.equal(addBusinessDays({ date: "2026-12-28", days: 1 }).result.date, "2026-12-29");
  assert.equal(
    addBusinessDays({ date: "2026-12-28", days: 1, yearEndClosure: true }).result.date,
    "2027-01-04",
  );
  assert.equal(
    addBusinessDays({ date: "2026-09-24", days: 1, closedDates: ["2026-09-25"] }).result.date,
    "2026-09-28",
  );
  assert.equal(
    addBusinessDays({ date: "2026-09-25", days: 1, weekendDays: ["sun"] }).result.date,
    "2026-09-26",
  );
  fails(() => addBusinessDays({ date: "2026-09-18", days: 1.5 }), "days");
  fails(() => addBusinessDays({ date: "2027-12-30", days: 5 }), "days"); // データの範囲外
  fails(() => addBusinessDays({ date: "2026-09-18", days: 1, closedDates: ["x"] }), "closedDates");
});

test("営業日の数: 2026年9月は19日(土日8日・祝日3日)", () => {
  const r = countBusinessDays({ from: "2026-09-01", to: "2026-09-30" });
  assert.equal(r.calendarDays, 30);
  assert.equal(r.businessDays, 19);
  assert.equal(r.holidays.length, 3);
  assert.equal(countBusinessDays({ from: "2026-09-24", to: "2026-09-24" }).businessDays, 1);
  fails(() => countBusinessDays({ from: "2026-09-30", to: "2026-09-01" }), "to");
  fails(() => countBusinessDays({ from: "1960-01-01", to: "2026-01-01" }), "to");
});

test("和暦 → 西暦: 漢字・略号・元年・全角・元号の期間外", () => {
  const to = (w) => convertWareki({ wareki: w }).date;
  assert.equal(to("令和6年4月1日"), "2024-04-01");
  assert.equal(to("R6.4.1"), "2024-04-01");
  assert.equal(to("r6/4/1"), "2024-04-01");
  assert.equal(to("令和６年４月１日"), "2024-04-01");
  assert.equal(to("平成元年1月8日"), "1989-01-08");
  assert.equal(to("昭和64年1月7日"), "1989-01-07");
  assert.equal(to("H31/4/30"), "2019-04-30");
  const late = convertWareki({ wareki: "平成31年5月1日" });
  assert.equal(late.date, "2019-05-01");
  assert.equal(late.input.outOfEraRange, true);
  assert.equal(late.wareki.text, "令和元年5月1日");
  fails(() => convertWareki({ wareki: "R7.2.30" }), "wareki");
  fails(() => convertWareki({ wareki: "そのうち" }), "wareki");
  fails(() => convertWareki({}), "date");
});

test("西暦 → 和暦: 改元日の前後", () => {
  assert.equal(convertWareki({ date: "2019-04-30" }).wareki.text, "平成31年4月30日");
  assert.equal(convertWareki({ date: "2019-05-01" }).wareki.text, "令和元年5月1日");
  assert.equal(convertWareki({ date: "1989-01-08" }).wareki.short, "H1.1.8");
  assert.equal(convertWareki({ date: "1926-12-25" }).wareki.era, "昭和");
  fails(() => convertWareki({ date: "1850-01-01" }), "date");
});
