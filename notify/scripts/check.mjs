// 値下がりチェック(GitHub Actions の notify ワークフローから実行)。
// 必要な環境変数: CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID
//   node scripts/check.mjs           … 相場データが更新されていればチェック
//   node scripts/check.mjs --force   … 更新がなくてもチェック
import { findDatabase, fromRest } from "../src/db.js";
import { runCheck } from "../src/check.js";

const token = process.env.CLOUDFLARE_API_TOKEN;
const accountId = process.env.CLOUDFLARE_ACCOUNT_ID;
if (!token || !accountId) {
  console.log("CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID が未設定のためスキップ");
  process.exit(0);
}
const databaseId = await findDatabase({ accountId, token, name: "toreca-notify" });
const stats = await runCheck({
  db: fromRest({ accountId, databaseId, token }),
  force: process.argv.includes("--force"),
  log: (msg) => console.log(msg),
});
console.log(JSON.stringify(stats));
