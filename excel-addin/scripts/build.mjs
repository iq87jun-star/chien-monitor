// Excel のアドインとして公開するファイルを dist/ に作る(このフォルダをそのまま HTTPS で配信する)。
//   dist/functions.js    関数の本体(計算API と同じコード + Excel への登録)
//   dist/functions.json  関数の説明(Excel に出る説明・引数)。src/functions.js の FUNCTIONS から作る
//   dist/functions.html  関数を動かすページ(Excel が裏で開く)
//   dist/help.html       使い方の画面(関数の一覧)
//   dist/manifest.xml    アドインの定義(AppSource に提出する・手動で読み込む時に使う)
//   dist/assets/         アイコン
// 配信先は EXCEL_ADDIN_BASE_URL(末尾は /)。省略時は本番(pokeca-kaigai.com/excel-addin/)
import { build } from "esbuild";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { CATEGORIES, FUNCTIONS } from "../src/functions.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DIST = path.join(ROOT, "dist");
const BASE_URL = process.env.EXCEL_ADDIN_BASE_URL || "https://pokeca-kaigai.com/excel-addin/";
const PROVIDER = "JP Calc Tools"; // AppSource の発行者名と合わせる
if (!/^https:\/\/.+\/$/.test(BASE_URL)) throw new Error(`EXCEL_ADDIN_BASE_URL must be https and end with /: ${BASE_URL}`);

const pkg = JSON.parse(await fs.readFile(path.join(ROOT, "package.json"), "utf8"));
await fs.rm(DIST, { recursive: true, force: true });
await fs.mkdir(path.join(DIST, "assets"), { recursive: true });

// 1. 関数の本体
await build({
  entryPoints: [path.join(ROOT, "src", "entry.js")],
  outfile: path.join(DIST, "functions.js"),
  bundle: true,
  format: "iife",
  target: "es2017", // Excel の古めの実行環境(Windows の Excel 2021 等)でも動く書き方にする
  charset: "utf8",
  legalComments: "none",
  banner: { js: "// 自動生成(excel-addin/scripts/build.mjs)。直接編集しない" },
});

// 2. 関数の説明(Excel のカスタム関数のメタデータ)
const metadata = {
  functions: FUNCTIONS.map((f) => ({
    id: f.name, // 公開後に変えると、関数を使っているブックが壊れる
    name: f.name,
    description: f.description,
    helpUrl: `${BASE_URL}help.html#${f.name}`,
    parameters: f.params.map((p) => ({
      name: p.name,
      description: p.description,
      type: "any",
      dimensionality: p.range ? "matrix" : "scalar",
      ...(p.optional ? { optional: true } : {}),
    })),
    result: { type: "any", dimensionality: f.result },
  })),
};
await fs.writeFile(path.join(DIST, "functions.json"), `${JSON.stringify(metadata, null, 2)}\n`);

// 3. ページ・定義・アイコン
await fs.copyFile(path.join(ROOT, "src", "functions.html"), path.join(DIST, "functions.html"));
await fs.writeFile(path.join(DIST, "help.html"), helpPage());
const manifest = (await fs.readFile(path.join(ROOT, "src", "manifest.template.xml"), "utf8"))
  .replaceAll("{{BASE_URL}}", BASE_URL)
  .replaceAll("{{VERSION}}", `${pkg.version}.0`)
  .replaceAll("{{PROVIDER}}", PROVIDER);
await fs.writeFile(path.join(DIST, "manifest.xml"), manifest);
for (const size of [16, 32, 64, 80]) {
  await fs.copyFile(path.join(ROOT, "listing", `icon-${size}.png`), path.join(DIST, "assets", `icon-${size}.png`));
}

const size = (await fs.stat(path.join(DIST, "functions.js"))).size;
console.log(`dist/ ready for ${BASE_URL} (${FUNCTIONS.length} functions, functions.js ${Math.round(size / 1024)}KB)`);

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

function helpPage() {
  const sections = CATEGORIES.map((c) => {
    const items = FUNCTIONS.filter((f) => f.category === c.key)
      .map((f) => {
        const sig = f.params.map((p) => (p.optional ? `[${p.name}]` : p.name)).join(", ");
        const args = f.params.map((p) => `<li><code>${esc(p.name)}</code> … ${esc(p.description)}</li>`).join("");
        return `<dt id="${f.name}"><code>=JP.${f.name}(${esc(sig)})</code></dt>
      <dd>${esc(f.description)}<ul>${args}</ul><div class="ex">例: <code>${esc(f.example)}</code></div></dd>`;
      })
      .join("\n      ");
    return `<h2>${esc(c.title)}</h2>\n    <dl>\n      ${items}\n    </dl>`;
  }).join("\n    ");
  return `<!doctype html>
<html lang="ja">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>日本の計算関数(Excel)の使い方</title>
    <style>
      :root { color-scheme: light dark; --fg: #1f2937; --sub: #4b5563; --bg: #fff; --code: #f1f5f9; --accent: #1d7a3e; }
      @media (prefers-color-scheme: dark) { :root { --fg: #e5e7eb; --sub: #9ca3af; --bg: #111827; --code: #1f2937; --accent: #4ade80; } }
      body { margin: 0; background: var(--bg); color: var(--fg); font: 14px/1.7 "Yu Gothic UI", "Hiragino Sans", "Noto Sans JP", system-ui, sans-serif; }
      .wrap { max-width: 760px; margin: 0 auto; padding: 16px; }
      h1 { font-size: 18px; margin: 4px 0 8px; }
      h2 { font-size: 15px; color: var(--accent); margin: 24px 0 4px; border-bottom: 1px solid color-mix(in srgb, var(--sub) 30%, transparent); padding-bottom: 4px; }
      code { background: var(--code); padding: 1px 4px; border-radius: 3px; font-size: 12.5px; overflow-wrap: anywhere; }
      dt { margin-top: 14px; font-weight: 600; }
      dd { margin: 2px 0 0; color: var(--sub); }
      dd ul { margin: 4px 0; padding-left: 18px; }
      .ex { margin-top: 2px; }
      .note { color: var(--sub); font-size: 13px; }
      a { color: var(--accent); }
    </style>
  </head>
  <body>
    <div class="wrap">
    <h1>日本の計算関数(Excel)</h1>
    <p>セルに <code>=JP.</code> と入力すると関数の一覧が出ます。「範囲も可」の引数に範囲(<code>A2:A100</code>)を渡すと、行ごとにまとめて計算します。</p>
    <p class="note">日付を返す関数(WORKDAY・FROM_WAREKI・HOLIDAYS)はシリアル値を返します。セルの表示形式を「日付」にしてください(Excel 標準の WORKDAY と同じです)。
    計算はすべて Excel の中で行い、入力した値を外部に送りません。</p>
    ${sections}
    <p class="note">手取りは協会けんぽ・2026年度の率による概算です。税務・法律の助言ではありません。
    <a href="https://pokeca-kaigai.com/excel-addin-privacy.html">プライバシーポリシー</a> ・
    <a href="https://pokeca-kaigai.com/excel-addin-terms.html">利用規約</a></p>
    </div>
  </body>
</html>
`;
}
