// dist/ のファイルを Apps Script と同じように1つのグローバル空間に読み込み、
// スプレッドシートから呼ばれる時と同じ形の値(日付・範囲の2次元配列・空のセル)で関数を試す。
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const DIST = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "dist");
const TZ = "Asia/Tokyo";

// Apps Script の Utilities / SpreadsheetApp の代わり(タイムゾーンつきの日付の変換だけ)
function offsetMinutes(tz, date) {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat("en-US", {
      timeZone: tz,
      hourCycle: "h23",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    })
      .formatToParts(date)
      .map((p) => [p.type, p.value]),
  );
  const asUtc = Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute);
  return (asUtc - date.getTime()) / 60000;
}
const Utilities = {
  formatDate(date, tz, fmt) {
    assert.equal(fmt, "yyyy-MM-dd");
    return new Intl.DateTimeFormat("en-CA", { timeZone: tz }).format(date);
  },
  parseDate(s, tz, fmt) {
    assert.equal(fmt, "yyyy-MM-dd");
    const utc = Date.parse(`${s}T00:00:00Z`);
    return new Date(utc - offsetMinutes(tz, new Date(utc)) * 60000);
  },
};
const menu = [];
const ctx = vm.createContext({
  Utilities,
  Session: { getScriptTimeZone: () => TZ },
  SpreadsheetApp: {
    getActiveSpreadsheet: () => ({ getSpreadsheetTimeZone: () => TZ }),
    getUi: () => ({
      createAddonMenu: () => ({
        addItem(label, fn) {
          menu.push([label, fn]);
          return this;
        },
        addToUi() {},
      }),
    }),
  },
});
for (const f of ["lib.js", "functions.js", "Code.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DIST, f), "utf8"), ctx, { filename: f });
}
const g = ctx;
// シートの日付セル(東京の0時)
const cellDate = (iso) => Utilities.parseDate(iso, TZ, "yyyy-MM-dd");
const iso = (d) => Utilities.formatDate(d, TZ, "yyyy-MM-dd");
// vm の中で作られた配列は別の Array なので、比べる前にこちら側の配列に直す
const plain = (v) => JSON.parse(JSON.stringify(v));

test("手取り: 計算API と同じ結果、範囲・空のセル・文字の金額", () => {
  assert.equal(g.JP_TAKEHOME(300000), 2876160);
  assert.equal(g.JP_TAKEHOME("30万円"), 2876160);
  assert.deepEqual(plain(g.JP_TAKEHOME([[300000], [""], [150000]])), [
    [2876160],
    [""],
    [g.JP_TAKEHOME(150000)],
  ]);
  assert.ok(g.JP_TAKEHOME(400000, 1000000, 45, "大阪府") > 0);
  const detail = plain(g.JP_TAKEHOME_DETAIL(300000));
  assert.deepEqual(detail[0], ["額面(年)", 3600000]);
  assert.deepEqual(detail.at(-2), ["手取り(年)", 2876160]);
  assert.throws(() => g.JP_TAKEHOME(300000, "", "", "アトランティス"), /prefecture/);
});

test("求人の給与: 年収の目安・時給換算・固定残業代", () => {
  const text = "月給25万円～＋賞与年2回（計4.5ヵ月分）";
  assert.equal(g.JP_ANNUAL_INCOME(text), 250000 * 16.5);
  assert.equal(g.JP_ANNUAL_INCOME("月給25万円～30万円", "", "max"), 3600000);
  assert.equal(g.JP_ANNUAL_INCOME("当社規定により優遇"), "");
  assert.ok(g.JP_HOURLY_EQUIVALENT("月給30万円", "実働8時間 年間休日125日") > 1500);
  assert.equal(g.JP_HOURLY_EQUIVALENT("時給1,500円"), "");
  assert.equal(g.JP_FIXED_OVERTIME("月給30万円（固定残業代40時間分・5万円を含む）"), 50000);
  assert.equal(g.JP_FIXED_OVERTIME("月給30万円"), "");
  assert.deepEqual(plain(g.JP_ANNUAL_INCOME([["月給20万円"], ["月給30万円"]])), [
    [2400000],
    [3600000],
  ]);
});

test("金額・面積・坪単価・ローン", () => {
  assert.equal(g.JP_YEN("1億2000万円"), 120000000);
  assert.equal(g.JP_YEN("12.5万円"), 125000);
  assert.equal(g.JP_YEN(5000), 5000);
  assert.throws(() => g.JP_YEN("未定"), /金額として読めません/);
  assert.equal(g.JP_AREA_M2("10坪"), 33.06);
  assert.equal(g.JP_AREA_M2("25.3m²"), 25.3);
  assert.equal(g.JP_TSUBO_PRICE("4,980万円", "70.12㎡"), Math.round(49800000 / (70.12 * 0.3025)));
  assert.equal(g.JP_TSUBO_PRICE(100000, 33.0578), Math.round(100000 / (33.0578 * 0.3025)));
  const loan = g.JP_LOAN_PAYMENT("3000万円");
  assert.ok(loan > 84000 && loan < 85000, `35年・1%で約8.47万円: ${loan}`);
  assert.ok(g.JP_LOAN_PAYMENT(30000000, 2, 25) > loan);
});

test("和暦: 日付のセル・シリアル値・文字列、和暦から日付", () => {
  assert.equal(g.JP_WAREKI(cellDate("2026-09-24")), "令和8年9月24日");
  assert.equal(g.JP_WAREKI(cellDate("2019-05-01"), "short"), "R1.5.1");
  assert.equal(g.JP_WAREKI(46289), "令和8年9月24日"); // シリアル値(2026/9/24)
  assert.equal(g.JP_WAREKI("2026/9/24"), "令和8年9月24日");
  assert.equal(iso(g.JP_FROM_WAREKI("R6.4.1")), "2024-04-01");
  assert.equal(iso(g.JP_FROM_WAREKI("平成元年1月8日")), "1989-01-08");
  assert.throws(() => g.JP_FROM_WAREKI("そのうち"), /和暦として読めません/);
});

test("祝日・営業日: WORKDAY・NETWORKDAYS の日本版", () => {
  assert.equal(g.JP_IS_HOLIDAY(cellDate("2026-09-22")), true);
  assert.equal(g.JP_HOLIDAY_NAME(cellDate("2026-09-21")), "敬老の日");
  assert.equal(g.JP_HOLIDAY_NAME(cellDate("2026-09-24")), "");
  assert.equal(g.JP_IS_BUSINESS_DAY(cellDate("2026-09-26")), false);
  assert.equal(iso(g.JP_WORKDAY(cellDate("2026-09-18"), 1)), "2026-09-24");
  assert.equal(iso(g.JP_WORKDAY(cellDate("2026-12-28"), 1, true)), "2027-01-04");
  // 独自の休業日(範囲)
  const closed = [[cellDate("2026-09-25")], [""]];
  assert.equal(iso(g.JP_WORKDAY(cellDate("2026-09-24"), 1, false, closed)), "2026-09-28");
  assert.equal(g.JP_NETWORKDAYS(cellDate("2026-09-01"), cellDate("2026-09-30")), 19);
  assert.equal(g.JP_NETWORKDAYS("令和8年9月1日", "2026/9/30"), 19);
  const list = g.JP_HOLIDAYS(2026);
  assert.equal(list.length, 18);
  assert.equal(iso(list[0][0]), "2026-01-01");
  assert.equal(list[0][1], "元日");
  // 範囲をまとめて
  assert.deepEqual(
    plain(g.JP_IS_HOLIDAY([[cellDate("2026-09-22")], [cellDate("2026-09-24")], [""]])),
    [[true], [false], [""]],
  );
});

test("メニュー: 使い方の画面を開く項目を追加する", () => {
  g.onOpen();
  assert.deepEqual(menu[0], ["使い方(関数の一覧)", "showHelp"]);
});

test("関数の説明(@customfunction)がすべての JP_ 関数に付いている", () => {
  const src = fs.readFileSync(path.join(DIST, "functions.js"), "utf8");
  const fns = [...src.matchAll(/^function (JP_\w+)\(/gm)].map((m) => m[1]);
  assert.equal(fns.length, 17);
  for (const name of fns) {
    const before = src.slice(0, src.indexOf(`function ${name}(`));
    assert.match(before.slice(before.lastIndexOf("/**")), /@customfunction/, name);
  }
});
