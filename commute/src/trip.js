// お休みの日の自転車のお出かけ: 行き先・到着時刻・終了時刻から、行きと帰りの天気をまとめる(通信しない部分)
import { addDays, weekday, summarize, advice, describe } from "./forecast.js";

const r1 = (x) => Math.round(x * 10) / 10;
const md = (date) => `${Number(date.slice(5, 7))}/${Number(date.slice(8))}`;
const fmt = (min) => `${String(Math.floor(min / 60) % 24).padStart(2, "0")}:${String(min % 60).padStart(2, "0")}`;
const z2 = (s) => s.replace(/[０-９：／]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xfee0));

// "今日" "明日" "あさって" "11/8" "2026-11-08" "8日" → YYYY-MM-DD(今日より前の月日は来年)
export function parseDate(text, today) {
  const t = z2((text ?? "").trim());
  if (!t || t === "今日" || t === "きょう") return today;
  if (t === "明日" || t === "あした") return addDays(today, 1);
  if (t === "明後日" || t === "あさって") return addDays(today, 2);
  let m = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (m) return `${m[1]}-${m[2].padStart(2, "0")}-${m[3].padStart(2, "0")}`;
  m = t.match(/^(\d{1,2})[\/月](\d{1,2})日?$/);
  let y = Number(today.slice(0, 4)), mo, d;
  if (m) [mo, d] = [m[1], m[2]];
  else if ((m = t.match(/^(\d{1,2})日?$/))) {
    [mo, d] = [today.slice(5, 7), m[1]];
    if (`${y}-${String(mo).padStart(2, "0")}-${d.padStart(2, "0")}` < today) {
      const next = addDays(`${today.slice(0, 8)}01`, 32);
      [y, mo] = [Number(next.slice(0, 4)), next.slice(5, 7)];
    }
  } else throw new Error(`日付が読めません: ${text}(例: 明日、11/8、2026-11-08)`);
  let date = `${y}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  if (date < today) date = `${y + 1}${date.slice(4)}`;
  return date;
}

// "10:00" "10時" "10時30分" "10" "1030" → 分
export function parseTime(text) {
  const t = z2((text ?? "").trim());
  const m = t.match(/^(\d{1,2})(?:[:時](\d{1,2})?分?)?$/) ?? t.match(/^(\d{1,2})(\d{2})$/);
  if (!m) throw new Error(`時刻が読めません: ${text}(例: 10:00、10時半は 10:30)`);
  const min = Number(m[1]) * 60 + Number(m[2] ?? 0);
  if (Number(m[1]) > 23 || Number(m[2] ?? 0) > 59) throw new Error(`時刻が読めません: ${text}`);
  return min;
}

// 直線距離(km)
export function distanceKm(a, b) {
  const rad = (x) => (x * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat), dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.sqrt(h));
}

// 自転車の所要時間(分、5 分単位に切り上げ)。道のりは直線の roadFactor 倍とみる
export function rideMinutes(config, from, to) {
  const km = distanceKm(from, to) * (config.bike?.roadFactor ?? 1.3);
  const min = (km / (config.bike?.kmh ?? 18)) * 60;
  return { km: r1(km), minutes: Math.max(5, Math.ceil(min / 5) * 5) };
}

function leg(label, window, s) {
  if (!s) return `**${label}** ${window} … 予報なし(16 日先まで)`;
  const temp = r1(s.tempMin) === r1(s.tempMax) ? `${r1(s.tempMin)}℃` : `${r1(s.tempMin)}〜${r1(s.tempMax)}℃`;
  const tips = advice(s);
  return `**${label}** ${window} / ${describe(s.code)} ${temp}(体感${r1(s.feelsMin)}℃) / 降水確率${s.pop}%` +
    `${s.precip > 0 ? `・${r1(s.precip)}mm/h` : ""} / 風${r1(s.wind)}m/s(突風${r1(s.gust)})` +
    (tips.length ? `\n　${tips.join("\n　")}` : "");
}

// trip: { date, place, dest: {name, lat, lon}, arrive, end }(arrive・end は分)
// home: 自宅の hourly、dest: 行き先の hourly
export function buildTripMessage(config, trip, home, dest) {
  const { km, minutes } = rideMinutes(config, config.home, trip.dest);
  const depart = trip.arrive - minutes;
  let end = trip.end;
  if (end <= trip.arrive) end += 24 * 60; // 終了が日付をまたぐ時
  const back = end + minutes;
  const startDay = depart < 0 ? addDays(trip.date, -1) : trip.date;
  const dep = depart < 0 ? depart + 24 * 60 : depart;
  const stay = summarize(dest, trip.date, trip.arrive, end);
  return [
    `🚲 **お出かけの天気 ${md(trip.date)}(${weekday(trip.date)})** ${trip.place}`,
    `📍 ${trip.dest.name}(道のり約${km}km・自転車で約${minutes}分として計算)`,
    "",
    leg("行き", `${fmt(dep)}出発 → ${fmt(trip.arrive)}着`, summarize(home, startDay, dep, dep + minutes)),
    "",
    stay ? `**現地** ${fmt(trip.arrive)}〜${fmt(end)} / ${describe(stay.code)} ${r1(stay.tempMin)}〜${r1(stay.tempMax)}℃ / 降水確率${stay.pop}%` : "",
    "",
    leg("帰り", `${fmt(end)}出発 → ${fmt(back)}ごろ着`, summarize(dest, trip.date, end, back)),
  ].filter((l, i, a) => !(l === "" && a[i - 1] === "")).join("\n");
}
