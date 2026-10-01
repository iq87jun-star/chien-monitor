// ゲームトレードの一覧ページを取得して Cloudflare Worker(src/worker.js)に送る。
// Claude の定期実行(1時間ごと)から実行する。判定・通知・状態の保存は Worker が行う。
//
//   GAMETRADE_INGEST_TOKEN=<合言葉> node gametrade-watch/relay.mjs

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { fetchPages } from "./src/core.js";

const here = dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(await readFile(join(here, "config.json"), "utf8"));
const token = process.env.GAMETRADE_INGEST_TOKEN;
if (!token) throw new Error("GAMETRADE_INGEST_TOKEN が未設定です");

const pages = await fetchPages(config);
const res = await fetch(new URL("/ingest", config.worker), {
  method: "POST",
  headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
  body: JSON.stringify({ pages }),
});
const result = await res.text();
console.log(`${res.status} ${result}`);
if (!res.ok) process.exit(1);
