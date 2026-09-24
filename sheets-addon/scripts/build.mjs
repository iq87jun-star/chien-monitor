// Apps Script に送るファイルを dist/ に作る。
//   dist/lib.js        計算部分(calc-api と拡張の parser.js)をまとめたもの。グローバル JPCalc
//   dist/functions.js  スプレッドシートの関数(=JP_TAKEHOME(...) 等)
//   dist/Code.js       メニューと使い方の画面
//   dist/Help.html     使い方の画面
//   dist/appsscript.json
import { build } from "esbuild";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DIST = path.join(ROOT, "dist");
await fs.rm(DIST, { recursive: true, force: true });
await fs.mkdir(DIST, { recursive: true });

await build({
  entryPoints: [path.join(ROOT, "src", "lib-entry.js")],
  outfile: path.join(DIST, "lib.js"),
  bundle: true,
  format: "iife",
  globalName: "JPCalc",
  target: "es2019", // Apps Script(V8)で確実に動く書き方に直す
  charset: "utf8",
  legalComments: "none",
  banner: { js: "// 自動生成(sheets-addon/scripts/build.mjs)。直接編集しない\n" },
});
for (const f of ["functions.js", "Code.js", "Help.html", "appsscript.json"]) {
  await fs.copyFile(path.join(ROOT, "src", f), path.join(DIST, f));
}
const size = (await fs.stat(path.join(DIST, "lib.js"))).size;
console.log(`dist/ ready (lib.js ${Math.round(size / 1024)}KB)`);
