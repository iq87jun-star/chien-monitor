// デプロイ前の準備(GitHub Actions の notify ワークフローから実行)。
// D1 データベース「toreca-notify」を探し(無ければ作り)、wrangler.toml の database_id を書き換える。
// 必要な環境変数: CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { findDatabase } from "../src/db.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const id = await findDatabase({
  accountId: process.env.CLOUDFLARE_ACCOUNT_ID,
  token: process.env.CLOUDFLARE_API_TOKEN,
  name: "toreca-notify",
  create: true,
});
const file = path.join(ROOT, "wrangler.toml");
const toml = await fs.readFile(file, "utf8");
const next = toml.replace(/^database_id = ".*"$/m, `database_id = "${id}"`);
if (next === toml && !toml.includes(id))
  throw new Error("wrangler.toml に database_id の行がありません");
await fs.writeFile(file, next);
console.log(`D1 toreca-notify: ${id}`);
