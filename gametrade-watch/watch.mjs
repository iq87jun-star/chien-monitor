// 手元で試す用(本番は Cloudflare Worker の src/worker.js が10分ごとに実行する)。
//
//   node watch.mjs            … 通知し、状態を state.json に保存
//   node watch.mjs --dry-run  … 通知も保存もせず、通知対象を表示するだけ
//
// 環境変数:
//   GAMETRADE_DISCORD_WEBHOOK … 通知先の Discord ウェブフックURL(未設定なら表示のみ)
//   GAMETRADE_STATE           … 状態ファイルのパス(既定: このフォルダの state.json)

import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { runCheck, priceText } from "./src/core.js";

const here = dirname(fileURLToPath(import.meta.url));
const config = JSON.parse(await readFile(join(here, "config.json"), "utf8"));
const statePath = process.env.GAMETRADE_STATE || join(here, "state.json");
const dryRun = process.argv.includes("--dry-run");
const state = await readFile(statePath, "utf8").then(JSON.parse, () => null);

const r = await runCheck({ config, state, webhook: process.env.GAMETRADE_DISCORD_WEBHOOK, dryRun });
console.log(`取得 ${r.total}件 / 通知対象 ${r.hits.length}件${r.first ? "(初回: 記録のみ)" : ""}`);
for (const it of r.hits) console.log(`  [${it.kind === "drop" ? "値下げ" : "新規"}] ${priceText(it)}  ${it.name}  ${it.url}`);
if (!dryRun) await writeFile(statePath, JSON.stringify(r.state) + "\n");
