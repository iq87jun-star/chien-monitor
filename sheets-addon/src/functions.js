// スプレッドシートの関数(カスタム関数)。計算は JPCalc(dist/lib.js。計算API と同じコード)で行う。
// どの関数も、1つ目の引数に範囲(A2:A100 など)を渡すと、行ごとに計算した結果をまとめて返す。
// 空のセルには空を返す。読めない値にはエラー(#ERROR!)と理由を返す。

/* global JPCalc, SpreadsheetApp, Session, Utilities */

// ---- 共通の下請け ----

function mapCells_(value, fn) {
  if (Array.isArray(value)) {
    return value.map(function (row) {
      return Array.isArray(row)
        ? row.map(function (c) {
            return cell_(c, fn);
          })
        : cell_(row, fn);
    });
  }
  return cell_(value, fn);
}

function cell_(v, fn) {
  if (v === "" || v == null) return "";
  return fn(v);
}

function tz_() {
  try {
    return SpreadsheetApp.getActiveSpreadsheet().getSpreadsheetTimeZone();
  } catch (e) {
    return Session.getScriptTimeZone();
  }
}

// セルの値(日付・シリアル値・「2026/9/24」・和暦の文字列)→ "YYYY-MM-DD"
function toIso_(v) {
  // instanceof ではなく型の名前で見る(別の実行環境で作られた日付でも正しく判定する)
  if (Object.prototype.toString.call(v) === "[object Date]") {
    return Utilities.formatDate(v, tz_(), "yyyy-MM-dd");
  }
  if (typeof v === "number") {
    return new Date(Date.UTC(1899, 11, 30) + Math.round(v) * 86400000).toISOString().slice(0, 10);
  }
  var s = String(v).trim();
  var iso = JPCalc.parseDate(s);
  if (iso) return iso;
  var w = JPCalc.fromWareki(s);
  if (w) return w.date;
  throw new Error("日付として読めません: " + s);
}

function toDate_(iso) {
  return Utilities.parseDate(iso, tz_(), "yyyy-MM-dd");
}

function num_(v, name) {
  if (typeof v === "number") return v;
  var n = JPCalc.RealtyParser.parseYen(String(v));
  if (n == null) throw new Error(name + "を数値として読めません: " + v);
  return n;
}

// 休業日の範囲(任意)→ ["YYYY-MM-DD", ...]
function closedDates_(range) {
  if (range === "" || range == null) return [];
  var list = Array.isArray(range) ? [].concat.apply([], range) : [range];
  return list
    .filter(function (c) {
      return c !== "" && c != null;
    })
    .map(toIso_);
}

function wrap_(fn) {
  try {
    return fn();
  } catch (e) {
    throw new Error(e && e.message ? e.message : String(e));
  }
}

// ---- 手取り ----

/**
 * 月給・賞与から、1年間の手取り額を計算します(2026年度の率・会社員・独身で扶養なし)。
 *
 * @param {number} monthlySalary 月給(額面・各種手当込み)。範囲も可
 * @param {number} [annualBonus] 年間の賞与の合計(省略時は0)
 * @param {number} [age] 年齢(40〜64歳は介護保険がかかる。省略時は30)
 * @param {string} [prefecture] 勤務先の協会けんぽの都道府県(省略時は東京都)
 * @return 1年間の手取り額(円)
 * @customfunction
 */
function JP_TAKEHOME(monthlySalary, annualBonus, age, prefecture) {
  return mapCells_(monthlySalary, function (m) {
    return wrap_(function () {
      return takeHome_(m, annualBonus, age, prefecture).takeHomeAnnual;
    });
  });
}

/**
 * 手取りの内訳(社会保険料・所得税・住民税)を表で返します(2026年度の率)。
 *
 * @param {number} monthlySalary 月給(額面・各種手当込み)
 * @param {number} [annualBonus] 年間の賞与の合計
 * @param {number} [age] 年齢
 * @param {string} [prefecture] 都道府県
 * @return 項目と金額の表(2列)
 * @customfunction
 */
function JP_TAKEHOME_DETAIL(monthlySalary, annualBonus, age, prefecture) {
  return wrap_(function () {
    var r = takeHome_(monthlySalary, annualBonus, age, prefecture);
    var s = r.socialInsurance;
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
  });
}

function takeHome_(monthly, bonus, age, prefecture) {
  var body = { monthlySalary: num_(monthly, "月給") };
  if (bonus !== "" && bonus != null) body.annualBonus = num_(bonus, "賞与");
  if (age !== "" && age != null) body.age = Math.floor(Number(age));
  if (prefecture !== "" && prefecture != null) body.prefecture = String(prefecture);
  return JPCalc.calculateTakeHome(body);
}

// ---- 求人の給与 ----

/**
 * 求人の給与欄の文章から、年収の目安を計算します(月給×(12+賞与の月数)、年俸があれば年俸)。
 *
 * @param {string} salaryText 給与欄の文章(例: 月給25万円～＋賞与年2回（4.5ヶ月分）)。範囲も可
 * @param {string} [workText] 勤務時間・休日の文章(省略可)
 * @param {string} [which] "min"(下限・省略時)または "max"(上限)
 * @return 年収の目安(円)。読めなければ空
 * @customfunction
 */
function JP_ANNUAL_INCOME(salaryText, workText, which) {
  return mapCells_(salaryText, function (t) {
    return wrap_(function () {
      var r = JPCalc.analyzeSalary({
        salary: String(t),
        workConditions: workText ? String(workText) : "",
      });
      if (!r.annual) return "";
      var v = which === "max" ? r.annual.max : r.annual.min;
      return v == null ? "" : v;
    });
  });
}

/**
 * 求人の給与欄の文章から、時給に換算した額を計算します(月給÷月の労働時間)。
 *
 * @param {string} salaryText 給与欄の文章。範囲も可
 * @param {string} [workText] 勤務時間・休日の文章(無ければ1日8時間・年間休日120日と仮定)
 * @return 時給換算(円・下限)。時給の求人や読めない時は空
 * @customfunction
 */
function JP_HOURLY_EQUIVALENT(salaryText, workText) {
  return mapCells_(salaryText, function (t) {
    return wrap_(function () {
      var r = JPCalc.analyzeSalary({
        salary: String(t),
        workConditions: workText ? String(workText) : "",
      });
      return r.hourlyEquivalent ? r.hourlyEquivalent.min : "";
    });
  });
}

/**
 * 求人の給与欄から、固定残業代(みなし残業代)の金額を取り出します。
 *
 * @param {string} salaryText 給与欄の文章。範囲も可
 * @return 固定残業代(円)。書かれていなければ空
 * @customfunction
 */
function JP_FIXED_OVERTIME(salaryText) {
  return mapCells_(salaryText, function (t) {
    var r = JPCalc.analyzeSalary({ salary: String(t) });
    return r.fixedOvertime && r.fixedOvertime.amount != null ? r.fixedOvertime.amount : "";
  });
}

// ---- 金額・物件 ----

/**
 * 日本語の金額の書き方を数値にします(例: 1億2000万円 → 120000000、12.5万円 → 125000)。
 *
 * @param {string} text 金額の文字列。範囲も可
 * @return 金額(円)
 * @customfunction
 */
function JP_YEN(text) {
  return mapCells_(text, function (t) {
    if (typeof t === "number") return t;
    var n = JPCalc.RealtyParser.parseYen(String(t));
    if (n == null) throw new Error("金額として読めません: " + t);
    return n;
  });
}

/**
 * 面積の書き方を㎡にします(例: 25.3m² → 25.3、10坪 → 33.06)。数値はそのまま㎡とみなします。
 *
 * @param {string} text 面積の文字列。範囲も可
 * @return 面積(㎡)
 * @customfunction
 */
function JP_AREA_M2(text) {
  return mapCells_(text, function (t) {
    if (typeof t === "number") return t;
    var n = JPCalc.RealtyParser.parseArea(String(t));
    if (n == null) throw new Error("面積として読めません: " + t);
    return Math.round(n * 100) / 100;
  });
}

/**
 * 坪単価を計算します(価格または賃料 ÷ 坪数)。価格・面積は「4,980万円」「70.12㎡」のような書き方でも可。
 *
 * @param {number} price 価格または賃料(範囲も可)
 * @param {number} area 面積(数値は㎡)
 * @return 1坪あたりの金額(円)
 * @customfunction
 */
function JP_TSUBO_PRICE(price, area) {
  return mapCells_(price, function (p) {
    var a = typeof area === "number" ? area : JPCalc.RealtyParser.parseArea(String(area));
    if (!a) throw new Error("面積として読めません: " + area);
    return Math.round(num_(p, "価格") / (a * 0.3025));
  });
}

/**
 * 住宅ローンの毎月の返済額(元利均等)を計算します。
 *
 * @param {number} principal 借入額(「3,000万円」のような書き方も可)。範囲も可
 * @param {number} [ratePercent] 年利(%・省略時は1)
 * @param {number} [years] 返済期間(年・省略時は35)
 * @return 毎月の返済額(円)
 * @customfunction
 */
function JP_LOAN_PAYMENT(principal, ratePercent, years) {
  var rate = ratePercent === "" || ratePercent == null ? 1 : Number(ratePercent);
  var y = years === "" || years == null ? 35 : Number(years);
  return mapCells_(principal, function (p) {
    return Math.round(JPCalc.RealtyParser.monthlyPayment(num_(p, "借入額"), rate / 100, y));
  });
}

// ---- 和暦・祝日・営業日 ----

/**
 * 日付を和暦にします(例: 2026/9/24 → 令和8年9月24日)。
 *
 * @param {Date} date 日付。範囲も可
 * @param {string} [format] "long"(令和8年9月24日・省略時)または "short"(R8.9.24)
 * @return 和暦の文字列
 * @customfunction
 */
function JP_WAREKI(date, format) {
  return mapCells_(date, function (d) {
    var w = JPCalc.toWareki(toIso_(d));
    if (!w) throw new Error("1873年より前の日付は和暦にできません");
    return format === "short" ? w.short : w.text;
  });
}

/**
 * 和暦の文字列を日付にします(例: 令和6年4月1日、R6.4.1、平成元年1月8日)。
 *
 * @param {string} text 和暦の文字列。範囲も可
 * @return 日付
 * @customfunction
 */
function JP_FROM_WAREKI(text) {
  return mapCells_(text, function (t) {
    var r = JPCalc.fromWareki(String(t));
    if (!r) throw new Error("和暦として読めません: " + t);
    return toDate_(r.date);
  });
}

/**
 * 日本の祝日(振替休日・国民の休日を含む)かどうかを返します。
 *
 * @param {Date} date 日付。範囲も可
 * @return TRUE / FALSE
 * @customfunction
 */
function JP_IS_HOLIDAY(date) {
  return mapCells_(date, function (d) {
    return Boolean(JPCalc.HOLIDAYS[toIso_(d)]);
  });
}

/**
 * 祝日の名前を返します(祝日でなければ空)。
 *
 * @param {Date} date 日付。範囲も可
 * @return 祝日の名前
 * @customfunction
 */
function JP_HOLIDAY_NAME(date) {
  return mapCells_(date, function (d) {
    return JPCalc.HOLIDAYS[toIso_(d)] || "";
  });
}

/**
 * 営業日(土日・祝日・指定した休業日以外)かどうかを返します。
 *
 * @param {Date} date 日付。範囲も可
 * @param {boolean} [yearEndClosure] TRUE なら12月29日〜1月3日を休みとして扱う
 * @param {Date} [closedDates] 独自の休業日の範囲(省略可)
 * @return TRUE / FALSE
 * @customfunction
 */
function JP_IS_BUSINESS_DAY(date, yearEndClosure, closedDates) {
  var closed = closedDates_(closedDates);
  return mapCells_(date, function (d) {
    return wrap_(function () {
      return JPCalc.calendarDay({
        date: toIso_(d),
        yearEndClosure: yearEndClosure === true,
        closedDates: closed,
      }).isBusinessDay;
    });
  });
}

/**
 * ○営業日後(マイナスなら前)の日付を返します。日本の祝日に対応した WORKDAY 関数です。
 *
 * @param {Date} date 開始日(この日は数えない)。範囲も可
 * @param {number} days 営業日数(マイナスで前へ)
 * @param {boolean} [yearEndClosure] TRUE なら12月29日〜1月3日を休みとして扱う
 * @param {Date} [closedDates] 独自の休業日の範囲(省略可)
 * @return 日付
 * @customfunction
 */
function JP_WORKDAY(date, days, yearEndClosure, closedDates) {
  var closed = closedDates_(closedDates);
  return mapCells_(date, function (d) {
    return wrap_(function () {
      var r = JPCalc.addBusinessDays({
        date: toIso_(d),
        days: Math.trunc(Number(days)),
        yearEndClosure: yearEndClosure === true,
        closedDates: closed,
      });
      return toDate_(r.result.date);
    });
  });
}

/**
 * 期間の営業日数を返します(開始日・終了日を含む)。日本の祝日に対応した NETWORKDAYS 関数です。
 *
 * @param {Date} startDate 開始日
 * @param {Date} endDate 終了日
 * @param {boolean} [yearEndClosure] TRUE なら12月29日〜1月3日を休みとして扱う
 * @param {Date} [closedDates] 独自の休業日の範囲(省略可)
 * @return 営業日数
 * @customfunction
 */
function JP_NETWORKDAYS(startDate, endDate, yearEndClosure, closedDates) {
  return wrap_(function () {
    return JPCalc.countBusinessDays({
      from: toIso_(startDate),
      to: toIso_(endDate),
      yearEndClosure: yearEndClosure === true,
      closedDates: closedDates_(closedDates),
    }).businessDays;
  });
}

/**
 * その年の祝日の一覧を返します(内閣府の公式データ)。
 *
 * @param {number} year 年(例: 2026)
 * @return 日付と祝日名の表(2列)
 * @customfunction
 */
function JP_HOLIDAYS(year) {
  return wrap_(function () {
    return JPCalc.calendarHolidays({ year: Math.floor(Number(year)) }).holidays.map(function (h) {
      return [toDate_(h.date), h.name];
    });
  });
}
