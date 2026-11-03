import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { addDays, weekday, todayJST, isWorkday, shiftOf, summarize, advice, buildMessage } from "../src/forecast.js";

const config = JSON.parse(readFileSync(new URL("../config.json", import.meta.url)));

// date から 2 日分、毎時同じ値の hourly を作る(overrides で時刻ごとに上書き)
function hourly(date, base = {}, overrides = {}) {
  const h = { time: [], temperature_2m: [], apparent_temperature: [], precipitation_probability: [],
    precipitation: [], snowfall: [], weather_code: [], wind_speed_10m: [], wind_gusts_10m: [] };
  for (const d of [date, addDays(date, 1), addDays(date, 2)]) for (let i = 0; i < 24; i++) {
    const t = `${d}T${String(i).padStart(2, "0")}:00`;
    const v = { temp: 10, feels: 9, pop: 0, precip: 0, snow: 0, code: 1, wind: 1, gust: 2, ...base, ...overrides[t] };
    h.time.push(t); h.temperature_2m.push(v.temp); h.apparent_temperature.push(v.feels);
    h.precipitation_probability.push(v.pop); h.precipitation.push(v.precip); h.snowfall.push(v.snow);
    h.weather_code.push(v.code); h.wind_speed_10m.push(v.wind); h.wind_gusts_10m.push(v.gust);
  }
  return h;
}

test("日付の計算", () => {
  assert.equal(addDays("2026-11-30", 1), "2026-12-01");
  assert.equal(weekday("2026-11-04"), "水");
  assert.equal(todayJST(new Date("2026-11-03T15:30:00Z")), "2026-11-04");
});

test("水曜は休み、早番の週は 19 日から", () => {
  assert.equal(isWorkday(config, "2026-11-04"), false);
  assert.equal(isWorkday(config, "2026-11-05"), true);
  assert.equal(shiftOf(config, "2026-11-18"), "normal");
  assert.equal(shiftOf(config, "2026-11-19"), "early");
  assert.equal(shiftOf(config, "2026-11-24"), "early");
  assert.equal(shiftOf(config, "2026-11-26"), "normal");
});

test("区間の一番悪い天気・最低気温・最大突風をとる", () => {
  const h = hourly("2026-11-05", {}, {
    "2026-11-05T08:00": { code: 61, precip: 2, pop: 90, temp: 8 },
    "2026-11-05T09:00": { gust: 12 },
  });
  const s = summarize(h, "2026-11-05", 8 * 60 + 15, 9 * 60);
  assert.deepEqual(s.rows.map((r) => r.hour), [8, 9]);
  assert.equal(s.code, 61);
  assert.equal(s.tempMin, 8);
  assert.equal(s.gust, 12);
  const tips = advice(s).join();
  assert.match(tips, /レインウェア/);
  assert.match(tips, /突風/);
});

test("帰りが日付をまたぐ時は翌日の時刻を見る", () => {
  const h = hourly("2026-11-05", {}, { "2026-11-06T00:00": { temp: -2 } });
  const s = summarize(h, "2026-11-05", 23 * 60 + 30, 24 * 60 + 15);
  assert.deepEqual(s.rows.map((r) => r.hour), [23, 0]);
  assert.equal(s.tempMin, -2);
});

test("凍結・霧・雪の注意", () => {
  assert.match(advice({ code: 3, tempMin: -1, feelsMin: -4, pop: 0, precip: 0, snow: 0, gust: 2 }).join(), /凍結/);
  assert.match(advice({ code: 45, tempMin: 5, feelsMin: 4, pop: 0, precip: 0, snow: 0, gust: 2 }).join(), /霧/);
  assert.match(advice({ code: 73, tempMin: 0, feelsMin: -3, pop: 80, precip: 1, snow: 1, gust: 2 }).join(), /雪.*凍結|凍結.*雪/s);
});

test("火曜: 今夜の帰りと、明日(水)は休み", () => {
  const msg = buildMessage(config, "2026-11-03", hourly("2026-11-03"), hourly("2026-11-03"));
  assert.match(msg, /今夜の帰り 11\/3\(火\)\*\* 22:30〜23:15/);
  assert.match(msg, /明日 11\/4\(水\)はお休み/);
});

test("水曜: 帰りはなく、明日の通常の行き", () => {
  const msg = buildMessage(config, "2026-11-04", hourly("2026-11-04"), hourly("2026-11-04"));
  assert.doesNotMatch(msg, /今夜の帰り/);
  assert.match(msg, /明日の行き 11\/5\(木\)\*\* 08:15〜09:00/);
});

test("早番の前日は 5 時台の行きを送る", () => {
  const msg = buildMessage(config, "2026-11-18", hourly("2026-11-18"), hourly("2026-11-18"));
  assert.match(msg, /明日の行き 11\/19\(木\) 🌅早番\*\* 05:15〜06:00/);
});
