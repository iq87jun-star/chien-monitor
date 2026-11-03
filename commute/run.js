// 通勤の天気を Discord に送る。
//   COMMUTE_DISCORD_WEBHOOK … 送り先(未設定なら標準出力に出すだけ)
//   COMMUTE_DATE … 今日の日付を指定(YYYY-MM-DD。試す時用。未指定なら日本時間の今日)
// お出かけ(休みの日の自転車)は次を渡す:
//   TRIP_PLACE … 行き先(住所・施設名・「緯度,経度」) TRIP_DATE … 日付(明日、11/8 など。空なら今日)
//   TRIP_ARRIVE … 到着時刻(10:00 など) TRIP_END … 終了時刻(15:00 など)
import { readFileSync } from "node:fs";
import { buildMessage, todayJST } from "./src/forecast.js";
import { buildTripMessage, parseDate, parseTime } from "./src/trip.js";

const config = JSON.parse(readFileSync(new URL("./config.json", import.meta.url)));
const UA = "chien-monitor-commute/0.1 (+https://github.com/iq87jun-star/chien-monitor)";

async function getJSON(url, opts = {}) {
  for (let attempt = 1; ; attempt++) {
    try {
      const res = await fetch(url, { headers: { "User-Agent": UA }, ...opts });
      if (!res.ok) throw new Error(`${url.host ?? url} ${res.status}: ${(await res.text()).slice(0, 200)}`);
      return await res.json();
    } catch (e) {
      if (attempt >= 3) throw e;
      await new Promise((r) => setTimeout(r, 5000 * attempt));
    }
  }
}

async function forecast({ lat, lon }, days = 3) {
  const url = new URL("https://api.open-meteo.com/v1/forecast");
  url.search = new URLSearchParams({
    latitude: lat, longitude: lon, timezone: "Asia/Tokyo", forecast_days: String(days), wind_speed_unit: "ms",
    hourly: "temperature_2m,apparent_temperature,precipitation_probability,precipitation,snowfall,weather_code,wind_speed_10m,wind_gusts_10m",
  });
  return (await getJSON(url)).hourly;
}

// 行き先の位置: 「緯度,経度」→ OpenStreetMap(施設名に強い)→ 国土地理院(住所に強い)
async function geocode(place) {
  const ll = place.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/);
  if (ll) return { name: place, lat: Number(ll[1]), lon: Number(ll[2]) };
  const isAddress = /[都道府県市区町村]/.test(place) || /\d+-\d+/.test(place);
  const osm = async () => {
    const url = new URL("https://nominatim.openstreetmap.org/search");
    // 自宅の周り(長野県中部)を優先して探す
    url.search = new URLSearchParams({ q: place, format: "jsonv2", limit: "1", countrycodes: "jp", "accept-language": "ja",
      viewbox: `${config.home.lon - 0.6},${config.home.lat + 0.5},${config.home.lon + 0.6},${config.home.lat - 0.5}` });
    const [r] = await getJSON(url);
    return r && { name: [r.name, ...r.display_name.split(",").slice(1, 3)].filter(Boolean).map((x) => x.trim()).join(" "), lat: Number(r.lat), lon: Number(r.lon) };
  };
  const gsi = async () => {
    const url = new URL("https://msearch.gsi.go.jp/address-search/AddressSearch");
    url.search = new URLSearchParams({ q: place });
    const [r] = await getJSON(url);
    return r && { name: r.properties.title, lat: r.geometry.coordinates[1], lon: r.geometry.coordinates[0] };
  };
  for (const find of isAddress ? [gsi, osm] : [osm, gsi]) {
    const hit = await find().catch((e) => (console.error(e.message), null));
    if (hit) return hit;
  }
  throw new Error(`行き先が見つかりません: ${place}(住所や「緯度,経度」でも指定できます)`);
}

async function main() {
  const today = process.env.COMMUTE_DATE || todayJST();
  if (process.env.TRIP_PLACE) {
    const place = process.env.TRIP_PLACE.trim();
    const date = parseDate(process.env.TRIP_DATE, today);
    const arrive = parseTime(process.env.TRIP_ARRIVE);
    const end = parseTime(process.env.TRIP_END);
    const dest = await geocode(place);
    const [home, there] = await Promise.all([forecast(config.home, 16), forecast(dest, 16)]);
    return buildTripMessage(config, { date, place, dest, arrive, end }, home, there);
  }
  const [home, work] = await Promise.all([forecast(config.home), forecast(config.work)]);
  return buildMessage(config, today, home, work);
}

const message = await main();
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
