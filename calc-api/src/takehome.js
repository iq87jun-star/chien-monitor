// 手取り計算(会社員・協会けんぽ・独身で扶養なし)。
// 率・控除額は毎年変わるので RATES に年度ごとにまとめ、結果に「どの年度の率で計算したか」を含める。
// 出典(2026年9月確認):
//   健康保険料率(都道府県別)・介護保険料率1.62%・子ども・子育て支援金率0.23% … 協会けんぽ 令和8年度
//   厚生年金 18.3% … 日本年金機構 / 雇用保険(一般の事業・労働者負担)0.5% … 厚生労働省 令和8年度
//   所得税の基礎控除・給与所得控除 … 令和8年度税制改正(財務省 大綱・国税庁 Q&A)
import { InputError } from "./calc.js";

export const RATES = {
  2026: {
    // 健康保険料率(%・労使合計)。令和8年3月分から
    health: {
      北海道: 10.28,
      青森: 9.85,
      岩手: 9.51,
      宮城: 10.1,
      秋田: 10.01,
      山形: 9.75,
      福島: 9.5,
      茨城: 9.52,
      栃木: 9.82,
      群馬: 9.68,
      埼玉: 9.67,
      千葉: 9.73,
      東京: 9.85,
      神奈川: 9.92,
      新潟: 9.21,
      富山: 9.59,
      石川: 9.7,
      福井: 9.71,
      山梨: 9.55,
      長野: 9.63,
      岐阜: 9.8,
      静岡: 9.61,
      愛知: 9.93,
      三重: 9.77,
      滋賀: 9.88,
      京都: 9.89,
      大阪: 10.13,
      兵庫: 10.12,
      奈良: 9.91,
      和歌山: 10.06,
      鳥取: 9.86,
      島根: 9.94,
      岡山: 10.05,
      広島: 9.78,
      山口: 10.15,
      徳島: 10.24,
      香川: 10.02,
      愛媛: 9.98,
      高知: 10.05,
      福岡: 10.11,
      佐賀: 10.55,
      長崎: 10.06,
      熊本: 10.08,
      大分: 10.08,
      宮崎: 9.77,
      鹿児島: 10.13,
      沖縄: 9.44,
    },
    nursingCare: 1.62, // 介護保険(40〜64歳)
    childSupport: 0.23, // 子ども・子育て支援金(令和8年4月分から)
    pension: 18.3, // 厚生年金
    employment: 0.5, // 雇用保険・労働者負担(一般の事業)
    pensionCap: 650000, // 厚生年金の標準報酬月額の上限
    bonusCapPension: 1500000, // 厚生年金の標準賞与額の上限(1回あたり)
    bonusCapHealth: 5730000, // 健康保険の標準賞与額の上限(年度あたり)
    // 所得税の基礎控除(合計所得金額の上限, 控除額)。令和8・9年分の特例加算を含む
    basicDeduction: [
      [4_890_000, 1_040_000],
      [6_550_000, 670_000],
      [23_500_000, 620_000],
      [24_000_000, 480_000],
      [24_500_000, 320_000],
      [25_000_000, 160_000],
    ],
    residentBasicDeduction: 430_000,
    residentPerCapita: 5_000, // 均等割(市町村3,000+道府県1,000+森林環境税1,000)
  },
};
export const DEFAULT_YEAR = 2026;

const ROMAJI = {
  hokkaido: "北海道",
  aomori: "青森",
  iwate: "岩手",
  miyagi: "宮城",
  akita: "秋田",
  yamagata: "山形",
  fukushima: "福島",
  ibaraki: "茨城",
  tochigi: "栃木",
  gunma: "群馬",
  saitama: "埼玉",
  chiba: "千葉",
  tokyo: "東京",
  kanagawa: "神奈川",
  niigata: "新潟",
  toyama: "富山",
  ishikawa: "石川",
  fukui: "福井",
  yamanashi: "山梨",
  nagano: "長野",
  gifu: "岐阜",
  shizuoka: "静岡",
  aichi: "愛知",
  mie: "三重",
  shiga: "滋賀",
  kyoto: "京都",
  osaka: "大阪",
  hyogo: "兵庫",
  nara: "奈良",
  wakayama: "和歌山",
  tottori: "鳥取",
  shimane: "島根",
  okayama: "岡山",
  hiroshima: "広島",
  yamaguchi: "山口",
  tokushima: "徳島",
  kagawa: "香川",
  ehime: "愛媛",
  kochi: "高知",
  fukuoka: "福岡",
  saga: "佐賀",
  nagasaki: "長崎",
  kumamoto: "熊本",
  oita: "大分",
  miyazaki: "宮崎",
  kagoshima: "鹿児島",
  okinawa: "沖縄",
};

// 「東京都」「東京」「Tokyo」「tokyo-to」→「東京」
export function prefectureKey(input) {
  const s = String(input ?? "")
    .normalize("NFKC")
    .trim();
  if (!s) return null;
  const ja = s === "北海道" ? s : s.replace(/[都府県]$/, "");
  if (RATES[DEFAULT_YEAR].health[ja] != null) return ja;
  // 「Tokyo」「Kyoto」はそのまま、「Tokyo-to」「Osaka fu」「Aichi Prefecture」は区切りの後ろを外す
  const lower = s.toLowerCase().replace(/\s+/g, " ");
  const en = lower
    .replace(/[-\s](to|fu|ken)$/, "")
    .replace(/\s*prefecture$/, "")
    .replace(/\s+/g, "");
  return ROMAJI[lower.replace(/\s+/g, "")] ?? ROMAJI[en] ?? null;
}

// 標準報酬月額の等級(健康保険は第1級58,000円〜第50級1,390,000円)。[この額未満なら, 標準報酬月額]
const GRADES = [
  [63000, 58000],
  [73000, 68000],
  [83000, 78000],
  [93000, 88000],
  [101000, 98000],
  [107000, 104000],
  [114000, 110000],
  [122000, 118000],
  [130000, 126000],
  [138000, 134000],
  [146000, 142000],
  [155000, 150000],
  [165000, 160000],
  [175000, 170000],
  [185000, 180000],
  [195000, 190000],
  [210000, 200000],
  [230000, 220000],
  [250000, 240000],
  [270000, 260000],
  [290000, 280000],
  [310000, 300000],
  [330000, 320000],
  [350000, 340000],
  [370000, 360000],
  [395000, 380000],
  [425000, 410000],
  [455000, 440000],
  [485000, 470000],
  [515000, 500000],
  [545000, 530000],
  [575000, 560000],
  [605000, 590000],
  [635000, 620000],
  [665000, 650000],
  [695000, 680000],
  [730000, 710000],
  [770000, 750000],
  [810000, 790000],
  [855000, 830000],
  [905000, 880000],
  [955000, 930000],
  [1005000, 980000],
  [1055000, 1030000],
  [1115000, 1090000],
  [1175000, 1150000],
  [1235000, 1210000],
  [1295000, 1270000],
  [1355000, 1330000],
  [Infinity, 1390000],
];
export function standardMonthly(pay) {
  return GRADES.find(([limit]) => pay < limit)[1];
}
// 厚生年金は第1級88,000円〜第32級650,000円
export const standardMonthlyPension = (pay, cap) =>
  Math.min(Math.max(standardMonthly(pay), 88000), cap);

// 給与から差し引く保険料の端数: 50銭以下は切り捨て、50銭を超えたら切り上げ
const employeeShare = (amount) => {
  const floor = Math.floor(amount);
  return amount - floor > 0.5 ? floor + 1 : floor;
};

// 給与所得(令和8年分の所得税)。令和8・9年分の特例で、収入220万円未満は「収入−74万円」
export function salaryIncomeForIncomeTax2026(gross) {
  if (gross < 691_000) return 0;
  if (gross < 2_191_000) return gross - 740_000;
  if (gross < 2_193_000) return 1_451_000;
  if (gross < 2_196_000) return 1_453_000;
  if (gross < 2_200_000) return 1_456_000;
  return salaryIncomeStandard(gross);
}

// 給与所得(本則。660万円未満は収入を4千円単位に切り捨てて計算する「年末調整等のための表」と同じ)
export function salaryIncomeStandard(gross, minimumDeduction = 690_000) {
  if (gross >= 8_500_000) return gross - 1_950_000;
  if (gross >= 6_600_000) return Math.floor(gross * 0.9 - 1_100_000);
  const a = Math.floor(gross / 4000) * 4000;
  const byFormula =
    gross >= 3_600_000 ? a * 0.8 - 440_000 : gross >= 1_628_000 ? a * 0.7 - 80_000 : null;
  const byMinimum = Math.max(gross - minimumDeduction, 0);
  return byFormula == null ? byMinimum : Math.min(Math.floor(byFormula), byMinimum);
}

const INCOME_TAX = [
  [1_950_000, 0.05, 0],
  [3_300_000, 0.1, 97_500],
  [6_950_000, 0.2, 427_500],
  [9_000_000, 0.23, 636_000],
  [18_000_000, 0.33, 1_536_000],
  [40_000_000, 0.4, 2_796_000],
  [Infinity, 0.45, 4_796_000],
];
export function incomeTax(taxable) {
  const t = Math.floor(Math.max(taxable, 0) / 1000) * 1000;
  const [, rate, minus] = INCOME_TAX.find(([limit]) => t <= limit);
  const base = Math.max(t * rate - minus, 0);
  return Math.floor((base * 1.021) / 100) * 100; // 復興特別所得税(2.1%)込み・100円未満切り捨て
}

function residentTax(totalIncome, socialInsurance, r) {
  if (totalIncome <= 450_000) return 0; // 非課税(単身・1級地の基準)
  const taxable =
    Math.floor(Math.max(totalIncome - socialInsurance - r.residentBasicDeduction, 0) / 1000) * 1000;
  // 調整控除(基礎控除の人的控除額の差5万円のみ)
  const adjust =
    taxable <= 2_000_000
      ? Math.min(50_000, taxable) * 0.05
      : Math.max((50_000 - (taxable - 2_000_000)) * 0.05, 2_500);
  const incomeLevy = Math.floor(Math.max(taxable * 0.1 - adjust, 0) / 100) * 100;
  return incomeLevy + r.residentPerCapita;
}

const assumption = (code, ja, en) => ({ code, ja, en });

function num(body, key, { required = false, min = 0, max, def, integer = false } = {}) {
  const v = body?.[key];
  if (v == null) {
    if (required) throw new InputError(`"${key}" is required`, key);
    return def;
  }
  if (
    typeof v !== "number" ||
    !Number.isFinite(v) ||
    v < min ||
    (max != null && v > max) ||
    (integer && !Number.isInteger(v))
  ) {
    throw new InputError(
      `"${key}" must be ${integer ? "an integer" : "a number"} between ${min} and ${max}`,
      key,
    );
  }
  return v;
}

// POST /v1/takehome/calculate
export function calculateTakeHome(body) {
  const monthly = Math.round(
    num(body, "monthlySalary", { required: true, min: 1, max: 20_000_000 }),
  );
  const bonus = Math.round(num(body, "annualBonus", { max: 200_000_000, def: 0 }));
  const bonusTimes = num(body, "bonusTimes", {
    min: bonus > 0 ? 1 : 0,
    max: 12,
    def: bonus > 0 ? 2 : 0,
    integer: true,
  });
  const age = num(body, "age", { min: 15, max: 99, def: 30, integer: true });
  const year = num(body, "year", {
    min: DEFAULT_YEAR,
    max: DEFAULT_YEAR,
    def: DEFAULT_YEAR,
    integer: true,
  });
  const pref = prefectureKey(body?.prefecture ?? "東京");
  if (!pref)
    throw new InputError(
      '"prefecture" must be a Japanese prefecture (e.g. "東京都" or "Tokyo")',
      "prefecture",
    );
  const r = RATES[year];
  const care = age >= 40 && age < 65;
  const healthRate = r.health[pref] + (care ? r.nursingCare : 0);

  // 毎月の保険料(従業員負担)
  const stdHealth = standardMonthly(monthly);
  const stdPension = standardMonthlyPension(monthly, r.pensionCap);
  const m = {
    health: employeeShare((stdHealth * r.health[pref]) / 200),
    nursingCare: care ? employeeShare((stdHealth * r.nursingCare) / 200) : 0,
    childSupport: employeeShare((stdHealth * r.childSupport) / 200),
    pension: employeeShare((stdPension * r.pension) / 200),
    employment: employeeShare((monthly * r.employment) / 100),
  };
  // 賞与の保険料(標準賞与額は千円未満切り捨て。健康保険は年間573万円、厚生年金は1回150万円が上限)
  const b = { health: 0, nursingCare: 0, childSupport: 0, pension: 0, employment: 0 };
  let healthBonusLeft = r.bonusCapHealth;
  for (let i = 0; i < bonusTimes; i++) {
    const pay = Math.floor(bonus / bonusTimes);
    const std = Math.floor(pay / 1000) * 1000;
    const stdH = Math.min(std, healthBonusLeft);
    healthBonusLeft -= stdH;
    b.health += employeeShare((stdH * r.health[pref]) / 200);
    b.nursingCare += care ? employeeShare((stdH * r.nursingCare) / 200) : 0;
    b.childSupport += employeeShare((stdH * r.childSupport) / 200);
    b.pension += employeeShare((Math.min(std, r.bonusCapPension) * r.pension) / 200);
    b.employment += employeeShare((pay * r.employment) / 100);
  }
  const si = Object.fromEntries(Object.keys(m).map((k) => [k, m[k] * 12 + b[k]]));
  const siTotal = Object.values(si).reduce((a, x) => a + x, 0);

  const gross = monthly * 12 + bonus;
  // 所得税(令和8年分)
  const salaryIncome = salaryIncomeForIncomeTax2026(gross);
  const basic = (r.basicDeduction.find(([limit]) => salaryIncome <= limit) ?? [0, 0])[1];
  const itax = incomeTax(salaryIncome - siTotal - basic);
  // 住民税(同じ年の所得に対する翌年度分を概算。給与所得控除は本則の最低69万円)
  const rtax = residentTax(salaryIncomeStandard(gross), siTotal, r);
  const takeHome = gross - siTotal - itax - rtax;

  return {
    year,
    prefecture: pref,
    grossAnnual: gross,
    socialInsurance: {
      healthInsurance: si.health,
      nursingCareInsurance: si.nursingCare,
      childSupportLevy: si.childSupport,
      pension: si.pension,
      employmentInsurance: si.employment,
      total: siTotal,
      standardMonthlyRemuneration: { health: stdHealth, pension: stdPension },
    },
    incomeTax: itax,
    residentTax: rtax,
    totalDeductions: siTotal + itax + rtax,
    takeHomeAnnual: takeHome,
    takeHomeMonthlyAverage: Math.round(takeHome / 12),
    takeHomeRatioPercent: Math.round((takeHome / gross) * 1000) / 10,
    rates: {
      healthInsurancePercent: r.health[pref],
      nursingCarePercent: care ? r.nursingCare : 0,
      childSupportPercent: r.childSupport,
      pensionPercent: r.pension,
      employmentInsuranceEmployeePercent: r.employment,
      totalEmployeeSharePercent:
        Math.round(((healthRate + r.childSupport + r.pension) / 2 + r.employment) * 1000) / 1000,
    },
    assumptions: [
      assumption(
        "employee_kyokai_kenpo",
        "会社員(協会けんぽ・厚生年金・雇用保険の一般の事業)で、独身・扶養なしとして計算",
        "Company employee in Kyokai Kenpo health insurance, single with no dependents",
      ),
      assumption(
        "full_year_rates",
        `${year}年度の保険料率を1年分に当てはめて計算(子ども・子育て支援金は実際には4月分から)`,
        `FY${year} insurance rates applied to the whole year (the child support levy actually starts in April)`,
      ),
      assumption(
        "resident_tax_estimate",
        "住民税は同じ年の所得にかかる翌年度分を概算(基礎控除43万円・均等割5,000円、調整控除は基礎控除分のみ)",
        "Resident tax is estimated on the same year's income (it is actually levied the following fiscal year)",
      ),
      ...(bonus > 0
        ? [
            assumption(
              "bonus_split",
              `賞与は年${bonusTimes}回に均等に分けて計算`,
              `Bonus is split evenly into ${bonusTimes} payments`,
            ),
          ]
        : []),
    ],
    currency: "JPY",
  };
}
