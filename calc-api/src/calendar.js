// 日本の祝日・営業日・和暦。祝日は内閣府の「国民の祝日」CSV(scripts/update-holidays.mjs で取り込み)。
import { InputError } from "./calc.js";
import data from "./holidays.json" with { type: "json" };

export const HOLIDAYS = data.holidays;
export const RANGE = { from: data.from, to: data.to };
const DAY = 86_400_000;
const WEEKDAYS_JA = ["日", "月", "火", "水", "木", "金", "土"];
const WEEKDAYS_EN = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];
const MAX_SPAN_DAYS = 3700; // 約10年
const MAX_ADD = 1000;

// 元号(開始日)。明治は改暦後の1873年1月1日から扱う
export const ERAS = [
  { name: "令和", en: "Reiwa", abbr: "R", start: "2019-05-01" },
  { name: "平成", en: "Heisei", abbr: "H", start: "1989-01-08" },
  { name: "昭和", en: "Showa", abbr: "S", start: "1926-12-25" },
  { name: "大正", en: "Taisho", abbr: "T", start: "1912-07-30" },
  { name: "明治", en: "Meiji", abbr: "M", start: "1873-01-01", firstYear: 1868 },
];

const iso = (t) => new Date(t).toISOString().slice(0, 10);
const toTime = (s) => Date.parse(`${s}T00:00:00Z`);

// "2026-09-22" / "2026/9/22" → "2026-09-22"(実在しない日付は null)
export function parseDate(input) {
  const m = /^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/.exec(
    String(input ?? "")
      .normalize("NFKC")
      .trim(),
  );
  if (!m) return null;
  const s = `${m[1]}-${m[2].padStart(2, "0")}-${m[3].padStart(2, "0")}`;
  const t = toTime(s);
  return Number.isNaN(t) || iso(t) !== s ? null : s;
}

function dateField(body, key) {
  const v = body?.[key];
  if (v == null || v === "") throw new InputError(`"${key}" is required (YYYY-MM-DD)`, key);
  const d = typeof v === "string" ? parseDate(v) : null;
  if (!d) throw new InputError(`"${key}" must be a valid date (YYYY-MM-DD)`, key);
  return d;
}

function inRange(d, key) {
  if (d < RANGE.from || d > RANGE.to) {
    throw new InputError(
      `"${key}" must be between ${RANGE.from} and ${RANGE.to} (holiday data range)`,
      key,
    );
  }
}

// 営業日の条件: 土日・祝日・年末年始(任意)・独自の休業日(任意)以外
function options(body) {
  const closed = body?.closedDates ?? [];
  if (!Array.isArray(closed) || closed.length > 400) {
    throw new InputError('"closedDates" must be an array of up to 400 dates', "closedDates");
  }
  const closedSet = new Set(
    closed.map((c) => {
      const d = typeof c === "string" ? parseDate(c) : null;
      if (!d) throw new InputError('"closedDates" must contain dates (YYYY-MM-DD)', "closedDates");
      return d;
    }),
  );
  const yearEnd = body?.yearEndClosure ?? false;
  if (typeof yearEnd !== "boolean")
    throw new InputError('"yearEndClosure" must be boolean', "yearEndClosure");
  const weekend = body?.weekendDays ?? ["sat", "sun"];
  if (!Array.isArray(weekend) || !weekend.every((w) => WEEKDAYS_EN.includes(w))) {
    throw new InputError('"weekendDays" must be an array like ["sat","sun"]', "weekendDays");
  }
  return { closedSet, yearEnd, weekend: new Set(weekend.map((w) => WEEKDAYS_EN.indexOf(w))) };
}

function isBusinessDay(d, o) {
  const dow = new Date(toTime(d)).getUTCDay();
  if (o.weekend.has(dow) || HOLIDAYS[d] || o.closedSet.has(d)) return false;
  if (o.yearEnd) {
    const md = d.slice(5);
    if (md >= "12-29" || md <= "01-03") return false;
  }
  return true;
}

// 西暦 → 和暦
export function toWareki(d) {
  const era = ERAS.find((e) => d >= e.start);
  if (!era) return null;
  const [y, m, day] = d.split("-").map(Number);
  const n = y - (era.firstYear ?? Number(era.start.slice(0, 4))) + 1;
  const yearText = n === 1 ? "元" : String(n);
  return {
    era: era.name,
    eraEn: era.en,
    year: n,
    text: `${era.name}${yearText}年${m}月${day}日`,
    short: `${era.abbr}${n}.${m}.${day}`,
  };
}

// 和暦の文字列 → 西暦。「令和6年4月1日」「R6.4.1」「平成元年1月8日」「H31/4/30」「令和６年４月１日」
export function fromWareki(text) {
  const s = String(text ?? "")
    .normalize("NFKC")
    .replace(/\s+/g, "");
  const m =
    /^(令和|平成|昭和|大正|明治|[RHSTMrhstm])(元|\d{1,2})[年./-](\d{1,2})[月./-](\d{1,2})日?$/.exec(
      s,
    );
  if (!m) return null;
  const key = m[1].toUpperCase();
  const era = ERAS.find((e) => e.name === m[1] || e.abbr === key);
  const n = m[2] === "元" ? 1 : Number(m[2]);
  const y = (era.firstYear ?? Number(era.start.slice(0, 4))) + n - 1;
  const d = parseDate(`${y}-${m[3]}-${m[4]}`);
  if (!d) return null;
  // その元号の期間外(例: 平成31年5月1日 は令和元年)も西暦には直せるが、印を付ける
  const next = ERAS[ERAS.indexOf(era) - 1];
  const outOfRange = d < era.start || (next != null && d >= next.start);
  return { date: d, era: era.name, year: n, outOfEraRange: outOfRange };
}

function describe(d, o) {
  const dow = new Date(toTime(d)).getUTCDay();
  return {
    date: d,
    weekday: WEEKDAYS_EN[dow],
    weekdayJa: WEEKDAYS_JA[dow],
    isHoliday: Boolean(HOLIDAYS[d]),
    holidayName: HOLIDAYS[d] ?? null,
    isBusinessDay: isBusinessDay(d, o),
    wareki: toWareki(d),
  };
}

// POST /v1/calendar/day { date }
export function calendarDay(body) {
  const d = dateField(body, "date");
  inRange(d, "date");
  return describe(d, options(body));
}

// POST /v1/calendar/holidays { year }
export function calendarHolidays(body) {
  const year = body?.year;
  const [from, to] = [Number(RANGE.from.slice(0, 4)), Number(RANGE.to.slice(0, 4))];
  if (!Number.isInteger(year) || year < from || year > to) {
    throw new InputError(`"year" must be an integer between ${from} and ${to}`, "year");
  }
  const holidays = Object.entries(HOLIDAYS)
    .filter(([d]) => d.startsWith(`${year}-`))
    .map(([date, name]) => ({
      date,
      name,
      weekdayJa: WEEKDAYS_JA[new Date(toTime(date)).getUTCDay()],
    }));
  return { year, count: holidays.length, holidays, source: "内閣府「国民の祝日」" };
}

// POST /v1/calendar/add-business-days { date, days }(開始日は数えない。days が負なら前へ)
export function addBusinessDays(body) {
  const d = dateField(body, "date");
  inRange(d, "date");
  const days = body?.days;
  if (!Number.isInteger(days) || Math.abs(days) > MAX_ADD) {
    throw new InputError(`"days" must be an integer between -${MAX_ADD} and ${MAX_ADD}`, "days");
  }
  const o = options(body);
  const step = days < 0 ? -1 : 1;
  let t = toTime(d);
  let left = Math.abs(days);
  while (left > 0) {
    t += step * DAY;
    const cur = iso(t);
    if (cur < RANGE.from || cur > RANGE.to) {
      throw new InputError(
        `Result is outside the holiday data range (${RANGE.from} to ${RANGE.to})`,
        "days",
      );
    }
    if (isBusinessDay(cur, o)) left--;
  }
  return { from: d, days, result: describe(iso(t), o) };
}

// POST /v1/calendar/count-business-days { from, to }(両端を含む)
export function countBusinessDays(body) {
  const from = dateField(body, "from");
  const to = dateField(body, "to");
  inRange(from, "from");
  inRange(to, "to");
  if (to < from) throw new InputError('"to" must be on or after "from"', "to");
  const span = (toTime(to) - toTime(from)) / DAY + 1;
  if (span > MAX_SPAN_DAYS)
    throw new InputError(`Range must be ${MAX_SPAN_DAYS} days or less`, "to");
  const o = options(body);
  let business = 0;
  const holidays = [];
  for (let t = toTime(from); t <= toTime(to); t += DAY) {
    const cur = iso(t);
    if (isBusinessDay(cur, o)) business++;
    if (HOLIDAYS[cur]) holidays.push({ date: cur, name: HOLIDAYS[cur] });
  }
  return { from, to, calendarDays: span, businessDays: business, holidays };
}

// POST /v1/wareki/convert { date } または { wareki }
export function convertWareki(body) {
  if (body?.date != null) {
    const d = dateField(body, "date");
    const w = toWareki(d);
    if (!w) throw new InputError('"date" must be 1873-01-01 or later', "date");
    return { date: d, wareki: w };
  }
  if (body?.wareki != null) {
    if (typeof body.wareki !== "string" || body.wareki.length > 50) {
      throw new InputError('"wareki" must be a short string such as "令和6年4月1日"', "wareki");
    }
    const r = fromWareki(body.wareki);
    if (!r)
      throw new InputError(
        '"wareki" could not be parsed (e.g. "令和6年4月1日", "R6.4.1")',
        "wareki",
      );
    return {
      date: r.date,
      wareki: toWareki(r.date),
      input: { era: r.era, year: r.year, outOfEraRange: r.outOfEraRange },
    };
  }
  throw new InputError('Either "date" or "wareki" is required', "date");
}
