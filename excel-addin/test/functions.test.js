// dist/functions.js を Excel と同じように読み込み(CustomFunctions.associate で登録される)、
// Excel から呼ばれる時と同じ形の値(範囲も1セルも2次元配列・日付はシリアル値・省略は null)で関数を試す。
// 結果はスプレッドシート版(sheets-addon)・計算API と同じになることも確かめる。
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const DIST = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "dist");

class CFError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}
const registered = new Map();
const ctx = vm.createContext({
  CustomFunctions: {
    associate: (id, fn) => registered.set(id, fn),
    Error: CFError,
    ErrorCode: { invalidValue: "#VALUE!" },
  },
});
vm.runInContext(fs.readFileSync(path.join(DIST, "functions.js"), "utf8"), ctx, { filename: "functions.js" });
const metadata = JSON.parse(fs.readFileSync(path.join(DIST, "functions.json"), "utf8"));

// =JP.NAME(...) の呼び出し。Excel は省略した引数を null で渡す
const plain = (v) => JSON.parse(JSON.stringify(v));
function call(name, ...args) {
  const meta = metadata.functions.find((f) => f.name === name);
  assert.ok(meta, `no metadata: ${name}`);
  const full = meta.parameters.map((p, i) => {
    const v = i < args.length ? args[i] : null;
    // 範囲の引数は1セルでも2次元配列で届く
    return p.dimensionality === "matrix" && v != null && !Array.isArray(v) ? [[v]] : v;
  });
  const out = plain(registered.get(meta.id)(...full));
  // 1セルを渡した時の [[x]] は、Excel ではそのセルの値として見える
  return meta.result.dimensionality === "matrix" && out.length === 1 && out[0].length === 1 ? out[0][0] : out;
}
const serial = (iso) => (Date.parse(`${iso}T00:00:00Z`) - Date.UTC(1899, 11, 30)) / 86400000;

test("メタデータ: 17関数がすべて登録され、名前・id が Excel の決まりに合う", () => {
  assert.equal(metadata.functions.length, 17);
  assert.deepEqual([...registered.keys()].sort(), metadata.functions.map((f) => f.id).sort());
  for (const f of metadata.functions) {
    assert.equal(f.id, f.name);
    assert.match(f.name, /^[A-Za-z][A-Za-z0-9._]{2,}$/, f.name);
    assert.ok(f.description.length > 10, f.name);
    // 省略できる引数の後ろに、省略できない引数を置かない
    const firstOptional = f.parameters.findIndex((p) => p.optional);
    if (firstOptional >= 0) assert.ok(f.parameters.slice(firstOptional).every((p) => p.optional), f.name);
    assert.equal(registered.get(f.id).length, 0, "登録する関数は ...args で受ける");
  }
});

test("定義: 配信先の URL がすべて入り、置き換え忘れがない", () => {
  const xml = fs.readFileSync(path.join(DIST, "manifest.xml"), "utf8");
  assert.doesNotMatch(xml, /\{\{/);
  assert.match(xml, /<Version>\d+\.\d+\.\d+\.\d+<\/Version>/);
  for (const f of ["functions.js", "functions.json", "functions.html", "help.html", "assets/icon-32.png", "assets/icon-64.png"]) {
    assert.ok(fs.existsSync(path.join(DIST, f)), f);
    assert.ok(xml.includes(`https://pokeca-kaigai.com/excel-addin/${f}"`), f);
  }
  const help = fs.readFileSync(path.join(DIST, "help.html"), "utf8");
  for (const f of metadata.functions) assert.ok(help.includes(`id="${f.name}"`), f.name);
});

test("手取り: スプレッドシート版と同じ結果、範囲・空のセル・文字の金額", () => {
  assert.equal(call("TAKEHOME", 300000), 2876160);
  assert.equal(call("TAKEHOME", "30万円"), 2876160);
  assert.deepEqual(call("TAKEHOME", [[300000], [""], [150000]]), [
    [2876160],
    [""],
    [call("TAKEHOME", 150000)],
  ]);
  assert.ok(call("TAKEHOME", 400000, 1000000, 45, "大阪府") > 0);
  const detail = call("TAKEHOME_DETAIL", 300000);
  assert.deepEqual(detail[0], ["額面(年)", 3600000]);
  assert.deepEqual(detail.at(-2), ["手取り(年)", 2876160]);
  assert.throws(
    () => call("TAKEHOME", 300000, null, null, "アトランティス"),
    (e) => e.code === "#VALUE!" && /prefecture/.test(e.message),
  );
});

test("求人の給与: 年収の目安・時給換算・固定残業代", () => {
  const text = "月給25万円～＋賞与年2回（計4.5ヵ月分）";
  assert.equal(call("ANNUAL_INCOME", text), 250000 * 16.5);
  assert.equal(call("ANNUAL_INCOME", "月給25万円～30万円", "", "max"), 3600000);
  assert.equal(call("ANNUAL_INCOME", "当社規定により優遇"), "");
  assert.ok(call("HOURLY_EQUIVALENT", "月給30万円", "実働8時間 年間休日125日") > 1500);
  assert.equal(call("HOURLY_EQUIVALENT", "時給1,500円"), "");
  assert.equal(call("FIXED_OVERTIME", "月給30万円（固定残業代40時間分・5万円を含む）"), 50000);
  assert.equal(call("FIXED_OVERTIME", "月給30万円"), "");
  assert.deepEqual(call("ANNUAL_INCOME", [["月給20万円"], ["月給30万円"]]), [[2400000], [3600000]]);
});

test("金額・面積・坪単価・ローン", () => {
  assert.equal(call("YEN", "1億2000万円"), 120000000);
  assert.equal(call("YEN", "12.5万円"), 125000);
  assert.equal(call("YEN", 5000), 5000);
  assert.throws(() => call("YEN", "未定"), /金額として読めません/);
  assert.equal(call("AREA_M2", "10坪"), 33.06);
  assert.equal(call("AREA_M2", "25.3m²"), 25.3);
  assert.equal(call("TSUBO_PRICE", "4,980万円", "70.12㎡"), Math.round(49800000 / (70.12 * 0.3025)));
  assert.equal(call("TSUBO_PRICE", 100000, 33.0578), Math.round(100000 / (33.0578 * 0.3025)));
  assert.throws(() => call("TSUBO_PRICE", 100000, "広い"), /面積として読めません/);
  const loan = call("LOAN_PAYMENT", "3000万円");
  assert.ok(loan > 84000 && loan < 85000, `35年・1%で約8.47万円: ${loan}`);
  assert.ok(call("LOAN_PAYMENT", 30000000, 2, 25) > loan);
});

test("和暦: シリアル値・文字列、和暦からシリアル値", () => {
  assert.equal(serial("2026-09-24"), 46289);
  assert.equal(call("WAREKI", 46289), "令和8年9月24日");
  assert.equal(call("WAREKI", serial("2019-05-01"), "short"), "R1.5.1");
  assert.equal(call("WAREKI", "2026/9/24"), "令和8年9月24日");
  assert.equal(call("FROM_WAREKI", "R6.4.1"), serial("2024-04-01"));
  assert.equal(call("FROM_WAREKI", "平成元年1月8日"), serial("1989-01-08"));
  assert.throws(() => call("FROM_WAREKI", "そのうち"), /和暦として読めません/);
});

test("祝日・営業日: WORKDAY・NETWORKDAYS の日本版", () => {
  assert.equal(call("IS_HOLIDAY", serial("2026-09-22")), true);
  assert.equal(call("HOLIDAY_NAME", serial("2026-09-21")), "敬老の日");
  assert.equal(call("HOLIDAY_NAME", serial("2026-09-24")), "");
  assert.equal(call("IS_BUSINESS_DAY", serial("2026-09-26")), false);
  assert.equal(call("WORKDAY", serial("2026-09-18"), 1), serial("2026-09-24"));
  assert.equal(call("WORKDAY", serial("2026-12-28"), 1, true), serial("2027-01-04"));
  assert.equal(call("WORKDAY", serial("2026-12-28"), 1, false), serial("2026-12-29"));
  // 独自の休業日(範囲・空のセルを含む)
  const closed = [[serial("2026-09-25")], [""]];
  assert.equal(call("WORKDAY", serial("2026-09-24"), 1, false, closed), serial("2026-09-28"));
  assert.equal(call("NETWORKDAYS", serial("2026-09-01"), serial("2026-09-30")), 19);
  assert.equal(call("NETWORKDAYS", "令和8年9月1日", "2026/9/30"), 19);
  const list = call("HOLIDAYS", 2026);
  assert.equal(list.length, 18);
  assert.deepEqual(list[0], [serial("2026-01-01"), "元日"]);
  assert.deepEqual(call("IS_HOLIDAY", [[serial("2026-09-22")], [serial("2026-09-24")], [""]]), [
    [true],
    [false],
    [""],
  ]);
  // 横に並んだ範囲もそのままの形で返す
  assert.deepEqual(call("HOLIDAY_NAME", [[serial("2026-09-21"), serial("2026-09-23")]]), [
    ["敬老の日", "秋分の日"],
  ]);
});
