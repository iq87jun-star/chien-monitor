// 通勤の天気を Discord に送る。
//   COMMUTE_DISCORD_WEBHOOK … 送り先(未設定なら標準出力に出すだけ)
//   COMMUTE_DATE … 今日の日付を指定(YYYY-MM-DD。試す時用。未指定なら日本時間の今日)
import { readFileSync } from "node:fs";
import { buildMessage, todayJST } from "./src/forecast.js";

const config = JSON.parse(readFileSync(new URL("./config.json", import.meta.url)));

async function forecast({ lat, lon }) {
  const url = new URL("https://api.open-meteo.com/v1/forecast");
  url.search = new URLSearchParams({
    latitude: lat, longitude: lon, timezone: "Asia/Tokyo", forecast_days: "3", wind_speed_unit: "ms",
    hourly: "temperature_2m,apparent_temperature,precipitation_probability,precipitation,snowfall,weather_code,wind_speed_10m,wind_gusts_10m",
  });
  for (let attempt = 1; ; attempt++) {
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Open-Meteo ${res.status}: ${await res.text()}`);
      return (await res.json()).hourly;
    } catch (e) {
      if (attempt >= 3) throw e;
      await new Promise((r) => setTimeout(r, 5000 * attempt));
    }
  }
}

const today = process.env.COMMUTE_DATE || todayJST();
const [home, work] = await Promise.all([forecast(config.home), forecast(config.work)]);
const message = buildMessage(config, today, home, work);
console.log(message ?? "(送る内容なし)");

const webhook = process.env.COMMUTE_DISCORD_WEBHOOK;
if (message && webhook) {
  const res = await fetch(webhook, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: message, allowed_mentions: { parse: [] } }),
  });
  if (!res.ok) throw new Error(`Discord ${res.status}: ${await res.text()}`);
  console.log("Discord に送りました");
} else if (message) {
  console.log("COMMUTE_DISCORD_WEBHOOK が未設定なので送っていません");
}
