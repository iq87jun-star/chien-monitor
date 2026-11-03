// 通勤時間帯の天気をまとめる(外部と通信しない部分。テストしやすいようにここに置く)

export const WEEKDAYS = ["日", "月", "火", "水", "木", "金", "土"];

// Open-Meteo の天気コード(WMO)→ 日本語
const CODES = {
  0: "快晴", 1: "晴れ", 2: "晴れ時々曇り", 3: "曇り",
  45: "霧", 48: "霧(着氷)",
  51: "弱い霧雨", 53: "霧雨", 55: "強い霧雨", 56: "着氷性の霧雨", 57: "着氷性の霧雨",
  61: "小雨", 63: "雨", 65: "強い雨", 66: "着氷性の雨", 67: "着氷性の雨",
  71: "小雪", 73: "雪", 75: "大雪", 77: "霧雪",
  80: "にわか雨", 81: "にわか雨", 82: "激しいにわか雨",
  85: "にわか雪", 86: "強いにわか雪",
  95: "雷雨", 96: "雷雨(ひょう)", 99: "雷雨(ひょう)",
};
const ICONS = (c) =>
  c === 0 || c === 1 ? "☀️" : c === 2 ? "🌤️" : c === 3 ? "☁️" : c === 45 || c === 48 ? "🌫️"
  : c >= 95 ? "⛈️" : (c >= 71 && c <= 77) || c === 85 || c === 86 ? "❄️" : "☔";
export const describe = (code) => `${ICONS(code)}${CODES[code] ?? `不明(${code})`}`;

// "YYYY-MM-DD" に日数を足す(日本時間の日付として扱う)
export function addDays(date, n) {
  const d = new Date(`${date}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}
export const weekday = (date) => WEEKDAYS[new Date(`${date}T00:00:00Z`).getUTCDay()];
export function todayJST(now = new Date()) {
  return new Date(now.getTime() + 9 * 3600e3).toISOString().slice(0, 10);
}

const toMin = (hhmm) => { const [h, m] = hhmm.split(":").map(Number); return h * 60 + m; };
const fmt = (min) => `${String(Math.floor(min / 60) % 24).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;

export function isWorkday(config, date) {
  if (config.holidays.includes(weekday(date))) return false;
  return !(config.daysOff ?? []).includes(date);
}
const daysBetween = (a, b) => Math.round((new Date(`${b}T00:00:00Z`) - new Date(`${a}T00:00:00Z`)) / 864e5);

// 早番か: notEarly(交代などで外れた日)> earlyShift(臨時の早番の期間)> earlyShiftRotation(3 人で回す周期)
export function shiftOf(config, date) {
  if ((config.notEarly ?? []).includes(date)) return "normal";
  if ((config.earlyShift ?? []).some((p) => p.from <= date && date <= p.to)) return "early";
  const r = config.earlyShiftRotation;
  if (r) {
    const d = daysBetween(r.start, date);
    const k = ((d % r.everyDays) + r.everyDays) % r.everyDays;
    if (k < r.lengthDays) return "early";
  }
  return "normal";
}

// 区間 [from, to](分)にかかる 1 時間ごとの予報の時刻(毎正時)を返す
function hoursCovering(from, to) {
  const hours = [];
  for (let h = Math.floor(from / 60); h * 60 <= to; h++) hours.push(h);
  return hours;
}

// 時間ごとの予報(Open-Meteo の hourly)から、その日のある区間の様子をまとめる
export function summarize(hourly, date, fromMin, toMin_) {
  const rows = [];
  for (const h of hoursCovering(fromMin, toMin_)) {
    // 24 時以降は翌日の時刻
    const d = h >= 24 ? addDays(date, 1) : date;
    const i = hourly.time.indexOf(`${d}T${String(h % 24).padStart(2, "0")}:00`);
    if (i < 0) continue;
    rows.push({
      hour: h % 24,
      code: hourly.weather_code[i],
      temp: hourly.temperature_2m[i],
      feels: hourly.apparent_temperature[i],
      pop: hourly.precipitation_probability[i] ?? 0,
      precip: hourly.precipitation[i] ?? 0,
      snow: hourly.snowfall[i] ?? 0,
      wind: hourly.wind_speed_10m[i],
      gust: hourly.wind_gusts_10m[i],
    });
  }
  if (!rows.length) return null;
  // 一番悪い天気(コードが大きいほど悪い)を代表にする
  const worst = rows.reduce((a, b) => (b.code > a.code ? b : a));
  return {
    rows,
    code: worst.code,
    tempMin: Math.min(...rows.map((r) => r.temp)),
    tempMax: Math.max(...rows.map((r) => r.temp)),
    feelsMin: Math.min(...rows.map((r) => r.feels)),
    pop: Math.max(...rows.map((r) => r.pop)),
    precip: Math.max(...rows.map((r) => r.precip)),
    snow: rows.reduce((s, r) => s + r.snow, 0),
    gust: Math.max(...rows.map((r) => r.gust)),
    wind: Math.max(...rows.map((r) => r.wind)),
  };
}

// ランニング・自転車向けのひとこと
export function advice(s) {
  const tips = [];
  const isSnow = s.snow > 0 || (s.code >= 71 && s.code <= 77) || s.code === 85 || s.code === 86;
  if (s.code >= 95) tips.push("⚡ 雷の予報。外を走るのは避けた方が安全");
  if (isSnow) tips.push("❄️ 雪。自転車は滑りやすいので無理をしない");
  else if (s.precip >= 1 || s.pop >= 70) tips.push("☔ 雨の可能性大。レインウェアを");
  else if (s.precip > 0 || s.pop >= 40) tips.push("🌂 降るかも。薄手の雨具があると安心");
  if (s.code === 66 || s.code === 67 || s.code === 56 || s.code === 57 || s.code === 48 ||
      (s.tempMin <= 1 && (s.precip > 0 || isSnow)))
    tips.push("🧊 路面凍結に注意");
  else if (s.tempMin <= 0) tips.push("🧊 0℃以下。橋の上や日陰の凍結に注意");
  if (s.gust >= 10) tips.push("💨 突風が強い(自転車は横風にあおられやすい)");
  else if (s.gust >= 7) tips.push("💨 風がやや強め");
  if (s.code === 45 || s.code === 48) tips.push("🔦 霧で見通しが悪い。ライトと反射材を");
  if (s.feelsMin <= 3) tips.push("🧤 体感が低い。手袋・ネックウォーマーを");
  else if (s.feelsMin <= 8) tips.push("🧥 肌寒い。長袖や薄手の上着を");
  return tips;
}

const md = (date) => `${Number(date.slice(5, 7))}/${Number(date.slice(8))}`;
const r1 = (x) => Math.round(x * 10) / 10;
function line(label, window, s) {
  if (!s) return `**${label}** ${window} … 予報なし`;
  const temp = r1(s.tempMin) === r1(s.tempMax) ? `${r1(s.tempMin)}℃` : `${r1(s.tempMin)}〜${r1(s.tempMax)}℃`;
  const parts = [
    `**${label}** ${window}`,
    `${describe(s.code)} ${temp}(体感${r1(s.feelsMin)}℃)`,
    `降水確率${s.pop}%${s.precip > 0 ? `・${r1(s.precip)}mm/h` : ""}${s.snow > 0 ? `・雪${r1(s.snow)}cm` : ""}`,
    `風${r1(s.wind)}m/s(突風${r1(s.gust)})`,
  ];
  const tips = advice(s);
  return parts.join(" / ") + (tips.length ? `\n　${tips.join("\n　")}` : "");
}

// 通知の本文を作る。today の帰り(today が勤務日なら)と、翌日の行き(翌日が勤務日なら)
// home: 自宅の hourly(行きに使う)、work: 職場の hourly(帰りに使う)
export function buildMessage(config, today, home, work) {
  const tomorrow = addDays(today, 1);
  const m = config.commuteMinutes;
  const out = [];
  if (isWorkday(config, today)) {
    const end = toMin(config.shift[shiftOf(config, today)].end);
    out.push(line(`今夜の帰り ${md(today)}(${weekday(today)})`,
      `${fmt(end)}〜${fmt(end + m)}`, summarize(work, today, end, end + m)));
  }
  if (isWorkday(config, tomorrow)) {
    const shift = shiftOf(config, tomorrow);
    const start = toMin(config.shift[shift].start);
    const label = `明日の行き ${md(tomorrow)}(${weekday(tomorrow)})${shift === "early" ? " 🌅早番" : ""}`;
    out.push(line(label, `${fmt(start - m)}〜${fmt(start)}`, summarize(home, tomorrow, start - m, start)));
  } else {
    out.push(`明日 ${md(tomorrow)}(${weekday(tomorrow)})はお休み 🎉`);
  }
  return out.length ? `🏃🚲 **通勤の天気**\n${out.join("\n\n")}` : null;
}
