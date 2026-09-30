// 請求・支払の計算(経理の部品): 支払条件からの支払日と、報酬・料金の源泉徴収税額。
// 支払日は calendar.js の営業日(内閣府の祝日)をそのまま使う。
import { InputError } from "./calc.js";
import { RANGE, dateField, describe, inRange, isBusinessDay, options } from "./calendar.js";

const DAY = 86_400_000;
const MAX_TERMS = 100;
const HOLIDAY_RULES = ["previous", "next", "none"];

const toTime = (s) => Date.parse(`${s}T00:00:00Z`);
const lastDay = (y, m) => new Date(Date.UTC(y, m, 0)).getUTCDate(); // m は 1〜12
const ymd = (y, m, d) =>
  `${y}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
const dayIn = (y, m, day) => (day === "end" ? lastDay(y, m) : Math.min(day, lastDay(y, m)));

// 「末締め翌月25日払い」「20日締め翌々月末日支払・休日の場合は翌営業日」→ 条件。読めない部分は null
export function parseTerms(text) {
  const s = String(text ?? "")
    .normalize("NFKC")
    .replace(/\s+/g, "");
  const close = /(?:(\d{1,2})日|(月末|末日|末))締/.exec(s);
  const pay =
    /(当月|翌月|翌々月|(\d{1,2})[かヵヶカケ]?月後)の?(?:(\d{1,2})日|(末日|末))/.exec(s);
  const offset = !pay
    ? null
    : pay[1] === "当月"
      ? 0
      : pay[1] === "翌月"
        ? 1
        : pay[1] === "翌々月"
          ? 2
          : Number(pay[2]);
  return {
    closingDay: close ? (close[1] ? Number(close[1]) : "end") : null,
    paymentMonthOffset: offset,
    paymentDay: pay ? (pay[3] ? Number(pay[3]) : "end") : null,
    holidayRule: /前営業日/.test(s) ? "previous" : /(翌|後)営業日/.test(s) ? "next" : null,
  };
}

// 休日の扱いの書き方(シート・Excel の引数)→ "previous" | "next" | "none"。空なら undefined
export function holidayRuleOf(v) {
  if (v === "" || v == null) return undefined;
  const s = String(v).normalize("NFKC").trim().toLowerCase();
  if (HOLIDAY_RULES.includes(s)) return s;
  if (/^前(営業日|日)?$/.test(s)) return "previous";
  if (/^(翌|後)(営業日|日)?$/.test(s)) return "next";
  if (/^(なし|そのまま|ずらさない)$/.test(s)) return "none";
  throw new InputError(`休日の扱いは「前」「翌」「なし」のどれか: ${v}`, "holidayRule");
}

function dayField(v, key) {
  if (v === "end") return v;
  if (!Number.isInteger(v) || v < 1 || v > 31) {
    throw new InputError(`"${key}" must be an integer 1-31 or "end"`, key);
  }
  return v;
}

// POST /v1/invoice/payment-date { date, terms } または { date, closingDay, paymentMonthOffset, paymentDay }
// 取引日(請求日)を含む締め日 → その締め日の月から paymentMonthOffset か月後の支払日 → 休日なら前(後)の営業日
export function paymentDate(body) {
  const d = dateField(body, "date");
  inRange(d, "date");
  let parsed = {};
  if (body?.terms != null) {
    if (typeof body.terms !== "string" || body.terms.length > MAX_TERMS) {
      throw new InputError(`"terms" must be a string up to ${MAX_TERMS} characters`, "terms");
    }
    parsed = parseTerms(body.terms);
  }
  const pick = (key, fallback) => body?.[key] ?? parsed[key] ?? fallback;
  const closingDay = dayField(pick("closingDay", "end"), "closingDay");
  const paymentDay = pick("paymentDay", null);
  if (paymentDay == null) {
    throw new InputError(
      body?.terms != null
        ? '"terms" must include the payment day (e.g. "末締め翌月25日払い")'
        : '"paymentDay" is required (1-31 or "end"), or give "terms"',
      body?.terms != null ? "terms" : "paymentDay",
    );
  }
  dayField(paymentDay, "paymentDay");
  const offset = pick("paymentMonthOffset", 1);
  if (!Number.isInteger(offset) || offset < 0 || offset > 12) {
    throw new InputError('"paymentMonthOffset" must be an integer 0-12', "paymentMonthOffset");
  }
  const holidayRule = pick("holidayRule", "previous");
  if (!HOLIDAY_RULES.includes(holidayRule)) {
    throw new InputError(`"holidayRule" must be one of ${HOLIDAY_RULES.join(", ")}`, "holidayRule");
  }
  const o = options(body);

  let [y, m] = d.split("-").map(Number);
  if (Number(d.slice(8)) > dayIn(y, m, closingDay)) [y, m] = m === 12 ? [y + 1, 1] : [y, m + 1];
  const closingDate = ymd(y, m, dayIn(y, m, closingDay));
  const pm = m - 1 + offset;
  const [py, pmm] = [y + Math.floor(pm / 12), (pm % 12) + 1];
  const scheduled = ymd(py, pmm, dayIn(py, pmm, paymentDay));

  let t = toTime(scheduled);
  const step = holidayRule === "next" ? 1 : -1;
  for (let i = 0; holidayRule !== "none" && !isBusinessDay(new Date(t).toISOString().slice(0, 10), o); i++) {
    if (i > 60) throw new InputError("No business day found near the payment date", "closedDates");
    t += step * DAY;
  }
  const pay = new Date(t).toISOString().slice(0, 10);
  if (pay < RANGE.from || pay > RANGE.to) {
    throw new InputError(
      `Payment date is outside the holiday data range (${RANGE.from} to ${RANGE.to})`,
      "date",
    );
  }
  return {
    date: d,
    terms: { closingDay, paymentMonthOffset: offset, paymentDay, holidayRule },
    closingDate,
    scheduledDate: scheduled,
    paymentDate: describe(pay, o),
    adjusted: pay !== scheduled,
    daysUntilPayment: (t - toTime(d)) / DAY,
  };
}

// 報酬・料金の源泉徴収税額(所得税法204条1項1号等。復興特別所得税を含む)。1円未満は切り捨て
//   100万円以下の部分 10.21% / 100万円を超える部分 20.42%
export function withholdingTax(base) {
  return base <= 1_000_000
    ? Math.floor((base * 1021) / 10000)
    : Math.floor(((base - 1_000_000) * 2042) / 10000) + 102_100;
}

const TAX_RATES = [0, 0.08, 0.1];

// POST /v1/invoice/withholding { amount, amountIncludesTax?, taxRate? }
export function withholding(body) {
  const amount = body?.amount;
  if (!Number.isInteger(amount) || amount < 0 || amount > 100_000_000_000) {
    throw new InputError('"amount" must be an integer between 0 and 100000000000 (JPY)', "amount");
  }
  const includes = body?.amountIncludesTax ?? false;
  if (typeof includes !== "boolean") {
    throw new InputError('"amountIncludesTax" must be boolean', "amountIncludesTax");
  }
  const rate = body?.taxRate ?? 0.1;
  if (!TAX_RATES.includes(rate)) {
    throw new InputError('"taxRate" must be 0, 0.08 or 0.1', "taxRate");
  }
  // 消費税が区分されていれば税抜の額に、区分されていなければ税込の額に源泉徴収する
  const consumptionTax = includes ? null : Math.floor((amount * Math.round(rate * 100)) / 100);
  const invoiceTotal = includes ? amount : amount + consumptionTax;
  const tax = withholdingTax(amount);
  return {
    amount,
    amountIncludesTax: includes,
    taxRate: rate,
    consumptionTax,
    invoiceTotal,
    withholdingBase: amount,
    withholdingTax: tax,
    netPayment: invoiceTotal - tax,
    assumptions: [
      {
        code: "general_fees",
        ja: "原稿料・講演料・デザイン料など、個人への一般の報酬・料金として計算(司法書士・外交員・ホステス等の特例は対象外)",
        en: "General fees paid to individuals (writing, lectures, design, etc.). Special rules (judicial scriveners, sales agents, hostesses, etc.) are not covered",
      },
      ...(includes
        ? [
            {
              code: "tax_not_separated",
              ja: "消費税を区分していないため、税込の額に源泉徴収",
              en: "Consumption tax is not stated separately, so withholding applies to the tax-inclusive amount",
            },
          ]
        : []),
    ],
  };
}
