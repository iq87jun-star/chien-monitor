// 価格差リストを作る: 海外相場の高いカードを楽天で1枚ずつ検索し、手残りを計算して
// data/latest.json と report.md に書き出す。ARBITRAGE_DISCORD_WEBHOOK があれば上位を Discord に送る。
// 楽天アプリIDが無い・海外相場が無いときは、既存の結果を壊さずに警告だけで終わる。
import fs from "node:fs/promises";
import path from "node:path";
import {
  ROOT,
  DATA_DIR,
  OVERSEAS_CARDS,
  OVERSEAS_FX,
  USER_AGENT,
  RAKUTEN_API,
  HITS_PER_CARD,
  REQUEST_INTERVAL_MS,
  MIN_OVERSEAS_JPY,
  MAX_CARDS,
  SETTINGS,
  MAX_ROWS,
} from "./config.mjs";
import {
  pickCandidates,
  searchKeyword,
  domesticQuote,
  buildList,
  renderReport,
  discordMessages,
} from "./src/core.mjs";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function readJson(file) {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return null;
  }
}

async function fetchJson(url, retries = 2) {
  for (let attempt = 0; ; attempt++) {
    try {
      const res = await fetch(url, { headers: { Accept: "application/json", "User-Agent": USER_AGENT } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    } catch (err) {
      if (attempt >= retries) throw err;
      await sleep(3000 * 2 ** attempt);
    }
  }
}

const jstNow = () =>
  new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 16).replace("T", " ");

async function main() {
  const appId = process.env.RAKUTEN_APP_ID;
  const affiliateId = process.env.RAKUTEN_AFFILIATE_ID || "";
  if (!appId) {
    console.warn(
      "arbitrage: RAKUTEN_APP_ID が未設定のため終了します(楽天ウェブサービスでアプリIDを無料発行し、Secrets に登録してください)",
    );
    return;
  }

  const overseas = await readJson(OVERSEAS_CARDS);
  const fx = await readJson(OVERSEAS_FX);
  const eurJpy = fx?.rates?.JPY;
  if (!overseas?.cards?.length || !eurJpy) {
    console.warn("arbitrage: 海外相場(toreca/data/raw)が読めないため終了します");
    return;
  }

  const candidates = pickCandidates(overseas.cards, eurJpy, { minJpy: MIN_OVERSEAS_JPY, max: MAX_CARDS });
  console.log(`arbitrage: ${candidates.length} 枚を楽天で検索します(1€=${eurJpy}円)`);

  const rows = [];
  let failures = 0;
  for (const card of candidates) {
    const params = new URLSearchParams({
      applicationId: appId,
      keyword: searchKeyword(card),
      hits: String(HITS_PER_CARD),
      sort: "+itemPrice",
      formatVersion: "2",
    });
    if (affiliateId) params.set("affiliateId", affiliateId);
    try {
      const body = await fetchJson(`${RAKUTEN_API}?${params}`);
      rows.push({ card, quote: domesticQuote(card, body?.Items, SETTINGS) });
    } catch (err) {
      failures++;
      console.warn(`arbitrage: ${card.id} の検索に失敗(${err.message})`);
    }
    await sleep(REQUEST_INTERVAL_MS);
  }
  // 全件失敗(アプリIDの誤り・API障害)なら前回の結果を残す
  if (rows.length === 0) {
    console.warn("arbitrage: 楽天の検索がすべて失敗したため、前回の結果を残して終了します");
    process.exitCode = 1;
    return;
  }

  const settings = { ...SETTINGS, eurJpy };
  const result = buildList(rows, settings);
  const meta = {
    ...settings,
    generatedAt: jstNow(),
    overseasFetchedAt: String(overseas.fetchedAt ?? "").slice(0, 10),
    searched: rows.length,
    maxRows: MAX_ROWS,
  };

  await fs.mkdir(DATA_DIR, { recursive: true });
  await fs.writeFile(
    path.join(DATA_DIR, "latest.json"),
    JSON.stringify({ ...meta, failures, ...result }, null, 1),
  );
  await fs.writeFile(path.join(ROOT, "report.md"), renderReport(result, meta));
  console.log(
    `arbitrage: 一致 ${result.matched} 枚 / 海外で売ると得 ${result.exportList.length} 枚 / ` +
      `国内が高い ${result.domesticHigh.length} 枚(検索失敗 ${failures})`,
  );

  const webhook = process.env.ARBITRAGE_DISCORD_WEBHOOK;
  if (webhook) {
    for (const content of discordMessages(result, meta)) {
      const res = await fetch(webhook, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: "価格差リスト", content }),
      });
      if (!res.ok) console.warn(`arbitrage: Discord への送信に失敗(HTTP ${res.status})`);
      await sleep(1000);
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
