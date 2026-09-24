// 計算の本体。ブラウザ拡張(求人 年収チェッカー・物件 単価・月額チェッカー)の parser.js をそのまま使い、
// API 向けに入力の受け取り方と出力の形(英語のキー・コード+日本語の表記)を整える。
// parser.js は拡張の content script(クラシックスクリプト)なので globalThis に公開される。
import "../../job-extension/src/parser.js";
import "../../realty-extension/src/parser.js";

const Job = globalThis.JobParser;
const Realty = globalThis.RealtyParser;

export const MAX_TEXT = 2000;

export class InputError extends Error {
  constructor(message, field) {
    super(message);
    this.field = field;
  }
}

// 給与の算出元(記載の語)→ コード
const BASIS = {
  月給: "monthly_salary",
  月収: "monthly_income",
  基本給: "base_salary",
  月額: "monthly_amount",
  日給: "daily_wage",
  時給: "hourly_wage",
  年俸: "annual_salary",
};
// 記載されている年収の種類 → コード
const STATED = {
  想定年収: "expected",
  年収例: "example",
  年収: "stated",
  平均年収: "company_average",
};

const assumption = (code, ja, en) => ({ code, ja, en });
const JOB_ASSUMPTIONS = {
  年間休日120日: assumption(
    "holidays_default_120",
    "年間休日120日",
    "Assumed 120 annual holidays (not stated)",
  ),
  "1日8時間": assumption(
    "hours_default_8",
    "1日8時間",
    "Assumed 8 working hours per day (not stated)",
  ),
};

function text(body, field, { required = false } = {}) {
  const v = body?.[field];
  if (v == null || v === "") {
    if (required) throw new InputError(`"${field}" is required`, field);
    return "";
  }
  if (typeof v !== "string") throw new InputError(`"${field}" must be a string`, field);
  if (v.length > MAX_TEXT) throw new InputError(`"${field}" is too long (max ${MAX_TEXT})`, field);
  return v;
}

const range = (r) => (r ? { min: r.min, max: r.max ?? null } : null);

// POST /v1/salary/analyze { salary, workConditions? }
export function analyzeSalary(body) {
  const salary = text(body, "salary", { required: true });
  const work = text(body, "workConditions");
  const r = Job.analyze(salary, work);
  return {
    found: r.found,
    basis: r.basis ? { code: BASIS[r.basis] ?? "other", ja: r.basis } : null,
    monthly: range(r.monthly),
    bonusMonths: r.bonusMonths,
    annual: r.annual && {
      min: r.annual.min,
      max: r.annual.max ?? null,
      openEnded: r.annual.open,
      bonusIncluded: r.annual.bonusIncluded,
    },
    statedAnnual: r.stated && {
      type: STATED[r.stated.kind] ?? "stated",
      ja: r.stated.kind,
      min: r.stated.min,
      max: r.stated.max ?? null,
      openEnded: r.stated.open,
      companyAverage: r.stated.companyAverage,
    },
    hourlyEquivalent: range(r.hourlyEquivalent),
    fixedOvertime: r.fixedOvertime && {
      hours: r.fixedOvertime.hours,
      amount: r.fixedOvertime.amount,
    },
    withoutFixedOvertime: r.baseWithoutOvertime && {
      monthly: r.baseWithoutOvertime.monthly,
      hourly: r.baseWithoutOvertime.hourly,
    },
    hoursPerDay: r.hoursPerDay,
    annualHolidays: r.holidays,
    assumptions: r.assumptions.map((a) => JOB_ASSUMPTIONS[a] ?? assumption("other", a, a)),
    currency: "JPY",
  };
}

// 物件の入力: API のキー → parser.js の項目名と、数値で渡された時の単位
const REALTY_FIELDS = [
  ["rent", "rent", "円"],
  ["managementFee", "fee", "円"],
  ["depositAndKeyMoney", "depositKey", null],
  ["deposit", "deposit", "円"],
  ["keyMoney", "keyMoney", "円"],
  ["price", "price", "円"],
  ["repairReserve", "repair", "円"],
  ["managementFeeAndRepairReserve", "feeRepair", null],
  ["grossYield", "yield", "%"],
  ["annualIncome", "income", "円"],
  ["area", "area", "㎡"],
];

// 数値はそれぞれの単位(円・㎡・%)とみなす。文字列は物件ページの表記のまま解釈する(「8.5万円」「25.3m²」「1ヶ月」)
function realtyFields(body) {
  const fields = {};
  for (const [key, name, unit] of REALTY_FIELDS) {
    const v = body?.[key];
    if (v == null || v === "") continue;
    if (typeof v === "number") {
      if (!unit) throw new InputError(`"${key}" must be a string`, key);
      if (!Number.isFinite(v) || v < 0) throw new InputError(`"${key}" must be >= 0`, key);
      fields[name] = `${v}${unit}`;
    } else if (typeof v === "string") {
      if (v.length > MAX_TEXT) throw new InputError(`"${key}" is too long`, key);
      fields[name] = v;
    } else {
      throw new InputError(`"${key}" must be a string or number`, key);
    }
  }
  return fields;
}

function loanOptions(body) {
  const rate = body?.loanRatePercent ?? 1;
  const years = body?.loanYears ?? 35;
  if (typeof rate !== "number" || !(rate >= 0 && rate <= 20)) {
    throw new InputError('"loanRatePercent" must be a number between 0 and 20', "loanRatePercent");
  }
  if (!Number.isInteger(years) || years < 1 || years > 50) {
    throw new InputError('"loanYears" must be an integer between 1 and 50', "loanYears");
  }
  return { loanRate: rate / 100, loanYears: years };
}

const round2 = (v) => (v == null ? null : Math.round(v * 10000) / 100);

// POST /v1/realty/analyze
export function analyzeRealty(body) {
  const fields = realtyFields(body);
  const options = loanOptions(body);
  const r = Realty.analyze(fields, options);
  if (!r) return { found: false, type: null, currency: "JPY" };
  const common = {
    found: true,
    type: r.kind,
    area: r.area,
    pricePerSquareMeter: r.perM2,
    pricePerTsubo: r.perTsubo,
    currency: "JPY",
  };
  if (r.kind === "rent") {
    return {
      ...common,
      rent: r.rent,
      managementFee: r.fee,
      monthlyTotal: r.monthly,
      deposit: r.deposit,
      keyMoney: r.keyMoney,
      initialCostEstimate: r.initialCost,
      assumptions:
        r.initialCost != null
          ? [
              assumption(
                "initial_cost_basis",
                "仲介手数料は賃料1ヶ月分+税、前家賃1ヶ月分で計算",
                "Initial cost = deposit + key money + brokerage fee (1 month's rent + 10% tax) + 1 month's advance rent. Guarantor, insurance and lock change fees are not included",
              ),
            ]
          : [],
    };
  }
  return {
    ...common,
    price: r.price,
    managementFee: r.fee,
    repairReserve: r.repair,
    loan: {
      ratePercent: options.loanRate * 100,
      years: options.loanYears,
      monthlyPayment: r.loanPayment,
    },
    monthlyTotal: r.monthlyTotal,
    grossYieldPercent: round2(r.grossYield),
    annualIncome: r.annualIncome,
    netYieldPercent: round2(r.netYield),
    assumptions: [
      assumption(
        "loan_full_amount",
        `全額を金利${options.loanRate * 100}%・${options.loanYears}年の元利均等で借りた場合`,
        `Loan payment assumes borrowing the full price at ${options.loanRate * 100}% for ${options.loanYears} years (equal monthly installments)`,
      ),
      ...(r.netYield != null
        ? [
            assumption(
              "net_yield_simple",
              "簡易の実質利回りは管理費・修繕積立金だけを差し引き(税・空室等は含まず)",
              "Net yield only subtracts management fee and repair reserve (taxes, vacancy etc. not included)",
            ),
          ]
        : []),
    ],
  };
}
