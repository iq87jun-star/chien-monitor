// ステップ1: データ収集
// poe.ninja(経済データ)とSteam News(公式ニュース)から取得し data/raw/ に保存する
import fs from "node:fs/promises";
import path from "node:path";
import {
  RAW_DIR,
  USER_AGENT,
  NINJA_BASE,
  UNIQUE_TYPES,
  STEAM_APPID,
} from "./config.mjs";

async function fetchJson(url, retries = 3) {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, {
        headers: { "User-Agent": USER_AGENT, Accept: "application/json" },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
      return await res.json();
    } catch (err) {
      if (attempt >= retries) throw err;
      const waitMs = 2000 * 2 ** attempt;
      console.warn(`fetch failed (${err.message}), retrying in ${waitMs}ms`);
      await new Promise((r) => setTimeout(r, waitMs));
    }
  }
}

async function writeRaw(name, data) {
  await fs.writeFile(
    path.join(RAW_DIR, `${name}.json`),
    JSON.stringify(data, null, 1),
  );
}

export async function fetchAll() {
  await fs.mkdir(RAW_DIR, { recursive: true });

  // 1. リーグ一覧 → 現行チャレンジリーグを特定(HC・Standard以外の先頭)
  const leagues = await fetchJson(`${NINJA_BASE}/leagues`);
  const league =
    leagues.find(
      (l) =>
        !/^(HC |Hardcore|Ruthless)/.test(l.id) && l.id !== "Standard",
    ) ?? leagues[0];
  console.log(`league: ${league.id}`);
  await writeRaw("leagues", { leagues, current: league });

  const q = encodeURIComponent(league.id);

  // 2. 通貨相場
  const currency = await fetchJson(
    `${NINJA_BASE}/exchange/current/overview?league=${q}&type=Currency`,
  );
  await writeRaw("currency", currency);

  // 3. ユニークアイテム相場(カテゴリごと・連続アクセスを避けて少し間隔を置く)
  for (const type of UNIQUE_TYPES) {
    const data = await fetchJson(
      `${NINJA_BASE}/stash/current/item/overview?league=${q}&type=${type}`,
    );
    await writeRaw(`uniques-${type}`, data);
    await new Promise((r) => setTimeout(r, 500));
  }

  // 4. 公式ニュース(Steam News API)
  const news = await fetchJson(
    `https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid=${STEAM_APPID}&count=10&maxlength=600`,
  );
  await writeRaw("news", news);

  console.log("fetch: done");
  return { league };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  fetchAll().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
