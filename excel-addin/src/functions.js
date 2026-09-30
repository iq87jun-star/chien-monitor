// Excel の関数(カスタム関数)。計算は計算API(calc-api)とスプレッドシートのアドオン(sheets-addon)と同じコード。
// 関数の説明(Excel に出る説明・引数)もここに書き、scripts/build.mjs が functions.json と使い方の画面を作る。
//
// Excel からの値の受け取り方:
//   - 「範囲も可」の引数(range: true)は、1セルでも範囲でも2次元配列で届く。結果も同じ形で返す
//   - 日付はシリアル値(1900年日付システム。2026/9/24 = 46289)。日付を返す関数もシリアル値を返す
//     (セルの表示形式を「日付」にすると日付で見える。Excel 標準の WORKDAY と同じ)
//   - 空のセル・省略した引数は "" / null / undefined のどれかで届くので、まとめて「無し」として扱う
import { analyzeSalary } from "../../calc-api/src/calc.js";
import { calculateTakeHome } from "../../calc-api/src/takehome.js";
import { holidayRuleOf, paymentDate, withholding } from "../../calc-api/src/invoice.js";
import {
  HOLIDAYS,
  addBusinessDays,
  calendarDay,
  calendarHolidays,
  countBusinessDays,
  fromWareki,
  parseDate,
  toWareki,
} from "../../calc-api/src/calendar.js";

// 拡張の parser.js は calc.js の import の時点で globalThis に公開されている
const Realty = globalThis.RealtyParser;

const DAY = 86_400_000;
const EPOCH = Date.UTC(1899, 11, 30); // Excel のシリアル値 0(1900/3/1 以降はこれで正しい)

// ---- 共通の下請け ----

export const isBlank = (v) => v === "" || v == null;

function mapCells(matrix, fn) {
  const rows = Array.isArray(matrix) ? matrix : [[matrix]];
  return rows.map((row) =>
    (Array.isArray(row) ? row : [row]).map((c) => (isBlank(c) ? "" : fn(c))),
  );
}

// 2つ目の引数が1セルなら全部の行に同じ値を、同じ形の範囲なら同じ位置の値を使う
function mapCells2(matrix, other, fn) {
  const single = !Array.isArray(other) || (other.length === 1 && other[0].length === 1);
  const one = Array.isArray(other) ? other[0]?.[0] : other;
  return mapCells(matrix, (c) => c).map((row, i) =>
    row.map((c, j) => (c === "" ? "" : fn(c, single ? one : other[i]?.[j]))),
  );
}

export const serialToIso = (n) => new Date(EPOCH + Math.round(n) * DAY).toISOString().slice(0, 10);
export const isoToSerial = (s) => (Date.parse(`${s}T00:00:00Z`) - EPOCH) / DAY;

// セルの値(シリアル値・「2026/9/24」・和暦の文字列)→ "YYYY-MM-DD"
function toIso(v) {
  if (typeof v === "number") return serialToIso(v);
  const s = String(v).trim();
  const iso = parseDate(s);
  if (iso) return iso;
  const w = fromWareki(s);
  if (w) return w.date;
  throw new Error(`日付として読めません: ${s}`);
}

function num(v, name) {
  if (typeof v === "number") return v;
  const n = Realty.parseYen(String(v));
  if (n == null) throw new Error(`${name}を数値として読めません: ${v}`);
  return n;
}

// 休業日の範囲(任意)→ ["YYYY-MM-DD", ...]
function closedDates(range) {
  if (isBlank(range)) return [];
  const list = Array.isArray(range) ? range.flat() : [range];
  return list.filter((c) => !isBlank(c)).map(toIso);
}

const yes = (v) => v === true || String(v).toUpperCase() === "TRUE";

// ---- 手取り ----

function takeHome(monthly, bonus, age, prefecture) {
  const body = { monthlySalary: num(monthly, "月給") };
  if (!isBlank(bonus)) body.annualBonus = num(bonus, "賞与");
  if (!isBlank(age)) body.age = Math.floor(Number(age));
  if (!isBlank(prefecture)) body.prefecture = String(prefecture);
  return calculateTakeHome(body);
}

const TAKEHOME_PARAMS = [
  { name: "bonus", description: "年間の賞与の合計(省略時は0)" },
  { name: "age", description: "年齢(40〜64歳は介護保険がかかる。省略時は30)" },
  { name: "prefecture", description: "勤務先の協会けんぽの都道府県(省略時は東京都)" },
];

function salaryOf(text, work) {
  return analyzeSalary({ salary: String(text), workConditions: isBlank(work) ? "" : String(work) });
}

// ---- 関数の一覧 ----
// name: Excel での名前(=JP.name)。params[].range: 範囲を受け取る引数。result: "scalar" | "matrix"

export const CATEGORIES = [
  { key: "takehome", title: "手取り(2026年度の率)" },
  { key: "salary", title: "求人の給与" },
  { key: "money", title: "金額・物件" },
  { key: "calendar", title: "和暦・祝日・営業日" },
  { key: "invoice", title: "請求・支払" },
];

export const FUNCTIONS = [
  {
    name: "TAKEHOME",
    category: "takehome",
    description: "月給・賞与から1年間の手取り額を計算します(2026年度の率・会社員・独身で扶養なし)。",
    example: "=JP.TAKEHOME(300000) → 2,876,160",
    params: [
      { name: "monthlySalary", description: "月給(額面・各種手当込み)。範囲も可", range: true },
      ...TAKEHOME_PARAMS.map((p) => ({ ...p, optional: true })),
    ],
    result: "matrix",
    fn: (monthly, bonus, age, prefecture) =>
      mapCells(monthly, (m) => takeHome(m, bonus, age, prefecture).takeHomeAnnual),
  },
  {
    name: "TAKEHOME_DETAIL",
    category: "takehome",
    description: "手取りの内訳(社会保険料・所得税・住民税)を2列の表で返します(2026年度の率)。",
    example: "=JP.TAKEHOME_DETAIL(300000)",
    params: [
      { name: "monthlySalary", description: "月給(額面・各種手当込み)" },
      ...TAKEHOME_PARAMS.map((p) => ({ ...p, optional: true })),
    ],
    result: "matrix",
    fn: (monthly, bonus, age, prefecture) => {
      const r = takeHome(monthly, bonus, age, prefecture);
      const s = r.socialInsurance;
      return [
        ["額面(年)", r.grossAnnual],
        ["健康保険", s.healthInsurance],
        ["介護保険", s.nursingCareInsurance],
        ["子ども・子育て支援金", s.childSupportLevy],
        ["厚生年金", s.pension],
        ["雇用保険", s.employmentInsurance],
        ["社会保険料 計", s.total],
        ["所得税", r.incomeTax],
        ["住民税(概算)", r.residentTax],
        ["手取り(年)", r.takeHomeAnnual],
        ["手取り(月平均)", r.takeHomeMonthlyAverage],
      ];
    },
  },
  {
    name: "ANNUAL_INCOME",
    category: "salary",
    description: "求人の給与欄の文章から年収の目安を計算します(月給×(12+賞与の月数)、年俸があれば年俸)。",
    example: '=JP.ANNUAL_INCOME("月給25万円～＋賞与年2回（4.5ヶ月分）") → 4,125,000',
    params: [
      { name: "salaryText", description: "給与欄の文章。範囲も可", range: true },
      { name: "workText", description: "勤務時間・休日の文章(省略可)", optional: true },
      { name: "which", description: '"min"(下限・省略時)または "max"(上限)', optional: true },
    ],
    result: "matrix",
    fn: (text, work, which) =>
      mapCells(text, (t) => {
        const r = salaryOf(t, work);
        if (!r.annual) return "";
        return (which === "max" ? r.annual.max : r.annual.min) ?? "";
      }),
  },
  {
    name: "HOURLY_EQUIVALENT",
    category: "salary",
    description: "求人の給与欄の文章から、時給に換算した額(下限)を計算します。時給の求人や読めない時は空。",
    example: '=JP.HOURLY_EQUIVALENT("月給30万円", "実働8時間 年間休日125日")',
    params: [
      { name: "salaryText", description: "給与欄の文章。範囲も可", range: true },
      {
        name: "workText",
        description: "勤務時間・休日の文章(無ければ1日8時間・年間休日120日と仮定)",
        optional: true,
      },
    ],
    result: "matrix",
    fn: (text, work) =>
      mapCells(text, (t) => salaryOf(t, work).hourlyEquivalent?.min ?? ""),
  },
  {
    name: "FIXED_OVERTIME",
    category: "salary",
    description: "求人の給与欄から固定残業代(みなし残業代)の金額を取り出します。書かれていなければ空。",
    example: '=JP.FIXED_OVERTIME("月給30万円（固定残業代40時間分・5万円を含む）") → 50,000',
    params: [{ name: "salaryText", description: "給与欄の文章。範囲も可", range: true }],
    result: "matrix",
    fn: (text) => mapCells(text, (t) => salaryOf(t).fixedOvertime?.amount ?? ""),
  },
  {
    name: "YEN",
    category: "money",
    description: "日本語の金額の書き方を数値にします(例: 1億2000万円 → 120000000)。",
    example: '=JP.YEN("1億2000万円") → 120,000,000',
    params: [{ name: "text", description: "金額の文字列。範囲も可", range: true }],
    result: "matrix",
    fn: (text) =>
      mapCells(text, (t) => {
        if (typeof t === "number") return t;
        const n = Realty.parseYen(String(t));
        if (n == null) throw new Error(`金額として読めません: ${t}`);
        return n;
      }),
  },
  {
    name: "AREA_M2",
    category: "money",
    description: "面積の書き方を㎡にします(例: 10坪 → 33.06)。数値はそのまま㎡とみなします。",
    example: '=JP.AREA_M2("10坪") → 33.06',
    params: [{ name: "text", description: "面積の文字列。範囲も可", range: true }],
    result: "matrix",
    fn: (text) =>
      mapCells(text, (t) => {
        if (typeof t === "number") return t;
        const n = Realty.parseArea(String(t));
        if (n == null) throw new Error(`面積として読めません: ${t}`);
        return Math.round(n * 100) / 100;
      }),
  },
  {
    name: "TSUBO_PRICE",
    category: "money",
    description: "坪単価(価格または賃料 ÷ 坪数)を計算します。「4,980万円」「70.12㎡」のような書き方も可。",
    example: '=JP.TSUBO_PRICE("4,980万円", "70.12㎡")',
    params: [
      { name: "price", description: "価格または賃料。範囲も可", range: true },
      { name: "area", description: "面積(数値は㎡)" },
    ],
    result: "matrix",
    fn: (price, area) => {
      const a = typeof area === "number" ? area : Realty.parseArea(String(area ?? ""));
      if (!a) throw new Error(`面積として読めません: ${area}`);
      return mapCells(price, (p) => Math.round(num(p, "価格") / (a * 0.3025)));
    },
  },
  {
    name: "LOAN_PAYMENT",
    category: "money",
    description: "住宅ローンの毎月の返済額(元利均等)を計算します。",
    example: '=JP.LOAN_PAYMENT("3000万円", 1, 35)',
    params: [
      { name: "principal", description: "借入額(「3,000万円」のような書き方も可)。範囲も可", range: true },
      { name: "ratePercent", description: "年利(%・省略時は1)", optional: true },
      { name: "years", description: "返済期間(年・省略時は35)", optional: true },
    ],
    result: "matrix",
    fn: (principal, ratePercent, years) => {
      const rate = isBlank(ratePercent) ? 1 : Number(ratePercent);
      const y = isBlank(years) ? 35 : Number(years);
      return mapCells(principal, (p) =>
        Math.round(Realty.monthlyPayment(num(p, "借入額"), rate / 100, y)),
      );
    },
  },
  {
    name: "WAREKI",
    category: "calendar",
    description: "日付を和暦にします(例: 2026/9/24 → 令和8年9月24日)。",
    example: "=JP.WAREKI(A2) → 令和8年9月24日",
    params: [
      { name: "date", description: "日付。範囲も可", range: true },
      { name: "format", description: '"long"(令和8年9月24日・省略時)または "short"(R8.9.24)', optional: true },
    ],
    result: "matrix",
    fn: (date, format) =>
      mapCells(date, (d) => {
        const w = toWareki(toIso(d));
        if (!w) throw new Error("1873年より前の日付は和暦にできません");
        return format === "short" ? w.short : w.text;
      }),
  },
  {
    name: "FROM_WAREKI",
    category: "calendar",
    description: "和暦の文字列を日付(シリアル値)にします(例: 令和6年4月1日、R6.4.1、平成元年1月8日)。",
    example: '=JP.FROM_WAREKI("R6.4.1") → 2024/4/1(表示形式を日付に)',
    params: [{ name: "text", description: "和暦の文字列。範囲も可", range: true }],
    result: "matrix",
    fn: (text) =>
      mapCells(text, (t) => {
        const r = fromWareki(String(t));
        if (!r) throw new Error(`和暦として読めません: ${t}`);
        return isoToSerial(r.date);
      }),
  },
  {
    name: "IS_HOLIDAY",
    category: "calendar",
    description: "日本の祝日(振替休日・国民の休日を含む)かどうかを返します。",
    example: "=JP.IS_HOLIDAY(A2)",
    params: [{ name: "date", description: "日付。範囲も可", range: true }],
    result: "matrix",
    fn: (date) => mapCells(date, (d) => Boolean(HOLIDAYS[toIso(d)])),
  },
  {
    name: "HOLIDAY_NAME",
    category: "calendar",
    description: "祝日の名前を返します(祝日でなければ空)。",
    example: "=JP.HOLIDAY_NAME(A2) → 敬老の日",
    params: [{ name: "date", description: "日付。範囲も可", range: true }],
    result: "matrix",
    fn: (date) => mapCells(date, (d) => HOLIDAYS[toIso(d)] ?? ""),
  },
  {
    name: "IS_BUSINESS_DAY",
    category: "calendar",
    description: "営業日(土日・祝日・指定した休業日以外)かどうかを返します。",
    example: "=JP.IS_BUSINESS_DAY(A2, TRUE)",
    params: [
      { name: "date", description: "日付。範囲も可", range: true },
      { name: "yearEndClosure", description: "TRUE なら12月29日〜1月3日を休みとして扱う", optional: true },
      { name: "closedDates", description: "独自の休業日の範囲(省略可)", optional: true, range: true },
    ],
    result: "matrix",
    fn: (date, yearEnd, closed) => {
      const c = closedDates(closed);
      return mapCells(date, (d) =>
        calendarDay({ date: toIso(d), yearEndClosure: yes(yearEnd), closedDates: c }).isBusinessDay,
      );
    },
  },
  {
    name: "WORKDAY",
    category: "calendar",
    description: "○営業日後(マイナスなら前)の日付を返します。日本の祝日に対応した WORKDAY です。",
    example: "=JP.WORKDAY(A2, 5) → 5営業日後(表示形式を日付に)",
    params: [
      { name: "date", description: "開始日(この日は数えない)。範囲も可", range: true },
      { name: "days", description: "営業日数(マイナスで前へ)" },
      { name: "yearEndClosure", description: "TRUE なら12月29日〜1月3日を休みとして扱う", optional: true },
      { name: "closedDates", description: "独自の休業日の範囲(省略可)", optional: true, range: true },
    ],
    result: "matrix",
    fn: (date, days, yearEnd, closed) => {
      const c = closedDates(closed);
      return mapCells(date, (d) => {
        const r = addBusinessDays({
          date: toIso(d),
          days: Math.trunc(Number(days)),
          yearEndClosure: yes(yearEnd),
          closedDates: c,
        });
        return isoToSerial(r.result.date);
      });
    },
  },
  {
    name: "NETWORKDAYS",
    category: "calendar",
    description: "期間の営業日数を返します(開始日・終了日を含む)。日本の祝日に対応した NETWORKDAYS です。",
    example: "=JP.NETWORKDAYS(A2, B2)",
    params: [
      { name: "startDate", description: "開始日" },
      { name: "endDate", description: "終了日" },
      { name: "yearEndClosure", description: "TRUE なら12月29日〜1月3日を休みとして扱う", optional: true },
      { name: "closedDates", description: "独自の休業日の範囲(省略可)", optional: true, range: true },
    ],
    result: "scalar",
    fn: (start, end, yearEnd, closed) =>
      countBusinessDays({
        from: toIso(start),
        to: toIso(end),
        yearEndClosure: yes(yearEnd),
        closedDates: closedDates(closed),
      }).businessDays,
  },
  {
    name: "HOLIDAYS",
    category: "calendar",
    description: "その年の祝日の一覧(日付のシリアル値と祝日名の2列)を返します(内閣府の公式データ)。",
    example: "=JP.HOLIDAYS(2026)",
    params: [{ name: "year", description: "年(例: 2026)" }],
    result: "matrix",
    fn: (year) =>
      calendarHolidays({ year: Math.floor(Number(year)) }).holidays.map((h) => [
        isoToSerial(h.date),
        h.name,
      ]),
  },
  {
    name: "PAYMENT_DATE",
    category: "invoice",
    description: "支払条件(例: 末締め翌月25日払い)から支払日(シリアル値)を返します。土日・祝日なら前営業日にします。",
    example: '=JP.PAYMENT_DATE(A2, "末締め翌月25日払い") → 25日が休日なら前営業日(表示形式を日付に)',
    params: [
      { name: "date", description: "取引日・請求日。範囲も可", range: true },
      {
        name: "terms",
        description: "支払条件の文章(例: 末締め翌月25日払い、20日締め翌々月末日支払)。行ごとに違う条件なら範囲も可",
        range: true,
      },
      {
        name: "holidayRule",
        description: '休日の時: "前"(前営業日・省略時)、"翌"(翌営業日)、"なし"。文章に「翌営業日」とあればそれに従う',
        optional: true,
      },
      { name: "closedDates", description: "独自の休業日の範囲(省略可)", optional: true, range: true },
    ],
    result: "matrix",
    fn: (date, terms, holidayRule, closed) => {
      const rule = holidayRuleOf(holidayRule);
      const c = closedDates(closed);
      return mapCells2(date, terms, (d, t) => {
        if (isBlank(t)) throw new Error("支払条件がありません");
        const body = { date: toIso(d), terms: String(t), closedDates: c };
        if (rule) body.holidayRule = rule;
        return isoToSerial(paymentDate(body).paymentDate.date);
      });
    },
  },
  {
    name: "WITHHOLDING",
    category: "invoice",
    description: "報酬・料金の源泉徴収税額を返します(100万円までは10.21%、超える部分は20.42%。1円未満切り捨て)。",
    example: "=JP.WITHHOLDING(100000) → 10,210",
    params: [
      { name: "amount", description: "報酬の額(税抜。「10万円」のような書き方も可)。範囲も可", range: true },
      { name: "includesTax", description: "TRUE なら、消費税を区分していない税込の額として扱う", optional: true },
    ],
    result: "matrix",
    fn: (amount, includesTax) =>
      mapCells(amount, (a) =>
        withholding({ amount: Math.round(num(a, "報酬の額")), amountIncludesTax: yes(includesTax) })
          .withholdingTax,
      ),
  },
];
