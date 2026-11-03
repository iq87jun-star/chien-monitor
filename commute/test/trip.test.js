import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseDate, parseTime, rideMinutes, buildTripMessage } from "../src/trip.js";
import { addDays } from "../src/forecast.js";

const config = JSON.parse(readFileSync(new URL("../config.json", import.meta.url)));

function hourly(date, overrides = {}) {
  const h = { time: [], temperature_2m: [], apparent_temperature: [], precipitation_probability: [],
    precipitation: [], snowfall: [], weather_code: [], wind_speed_10m: [], wind_gusts_10m: [] };
  for (const d of [addDays(date, -1), date, addDays(date, 1)]) for (let i = 0; i < 24; i++) {
    const t = `${d}T${String(i).padStart(2, "0")}:00`;
    const v = { temp: 10, feels: 9, pop: 0, precip: 0, snow: 0, code: 1, wind: 1, gust: 2, ...overrides[t] };
    h.time.push(t); h.temperature_2m.push(v.temp); h.apparent_temperature.push(v.feels);
    h.precipitation_probability.push(v.pop); h.precipitation.push(v.precip); h.snowfall.push(v.snow);
    h.weather_code.push(v.code); h.wind_speed_10m.push(v.wind); h.wind_gusts_10m.push(v.gust);
  }
  return h;
}

test("日付の書き方", () => {
  const today = "2026-11-03";
  assert.equal(parseDate("", today), "2026-11-03");
  assert.equal(parseDate("明日", today), "2026-11-04");
  assert.equal(parseDate("あさって", today), "2026-11-05");
  assert.equal(parseDate("11/8", today), "2026-11-08");
  assert.equal(parseDate("１１／８", today), "2026-11-08");
  assert.equal(parseDate("11月8日", today), "2026-11-08");
  assert.equal(parseDate("8日", today), "2026-11-08");
  assert.equal(parseDate("1日", today), "2026-12-01");
  assert.equal(parseDate("1/5", today), "2027-01-05");
  assert.equal(parseDate("2026-11-08", today), "2026-11-08");
  assert.throws(() => parseDate("来週", today), /日付が読めません/);
});

test("時刻の書き方", () => {
  assert.equal(parseTime("10:00"), 600);
  assert.equal(parseTime("10時"), 600);
  assert.equal(parseTime("10時30分"), 630);
  assert.equal(parseTime("9"), 540);
  assert.equal(parseTime("1630"), 990);
  assert.equal(parseTime("１６：３０"), 990);
  assert.throws(() => parseTime("昼"), /時刻が読めません/);
  assert.throws(() => parseTime("25:00"), /時刻が読めません/);
});

test("自転車の所要時間: 職場までは約 7km・25 分", () => {
  const r = rideMinutes(config, config.home, config.work);
  assert.ok(r.km > 6 && r.km < 8, `${r.km}`);
  assert.equal(r.minutes, 25);
});

test("行き・現地・帰りの天気をまとめる", () => {
  const date = "2026-11-08";
  const dest = { name: "どこか", lat: config.work.lat, lon: config.work.lon }; // 25 分
  const home = hourly(date, { [`${date}T09:00`]: { code: 61, precip: 1.5, pop: 80 } });
  const there = hourly(date, { [`${date}T15:00`]: { gust: 11 } });
  const msg = buildTripMessage(config, { date, place: "テスト", dest, arrive: 600, end: 900 }, home, there);
  assert.match(msg, /お出かけの天気 11\/8\(日\)\*\* テスト/);
  assert.match(msg, /\*\*行き\*\* 09:35出発 → 10:00着 \/ ☔小雨/);
  assert.match(msg, /レインウェア/);
  assert.match(msg, /\*\*現地\*\* 10:00〜15:00/);
  assert.match(msg, /\*\*帰り\*\* 15:00出発 → 15:25ごろ着 .*\n.*突風が強い/);
});

test("終了が深夜 0 時をまたぐ時は翌日の予報を見る", () => {
  const date = "2026-11-08";
  const dest = { name: "どこか", lat: config.work.lat, lon: config.work.lon };
  const there = hourly(date, { [`${addDays(date, 1)}T00:00`]: { temp: -3, feels: -6 } });
  const msg = buildTripMessage(config, { date, place: "夜", dest, arrive: 20 * 60, end: 30 }, hourly(date), there);
  assert.match(msg, /\*\*帰り\*\* 00:30出発 → 00:55ごろ着 .*-3℃/);
});
