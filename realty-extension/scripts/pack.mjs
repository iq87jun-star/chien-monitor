// ストア提出用zipを dist/ に作る(manifest・src・icons のみ。テストや開発用ファイルは含めない)
//   dist/realty-price-checker-<version>.zip                 … Chrome ウェブストア・Edge アドオン用(同じzip)
//   dist/firefox/realty-price-checker-<version>-firefox.zip … Firefox アドオン(AMO)用
// Firefox 用は manifest だけを変える: アドオンID・データ収集の申告(AMO で新規登録に必須)を加え、
// Firefox が未対応の background.service_worker を background.scripts に置き換える。
// 中身を確かめる時は dist/firefox-src を `npx web-ext lint -s dist/firefox-src` で検査する。
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const NAME = "realty-price-checker";
const GECKO_ID = "realty-price-checker@pokeca-kaigai.com";
const FILES = ["manifest.json", "src", "icons"];

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DIST = path.join(ROOT, "dist");
const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, "manifest.json"), "utf8"));

function zip(cwd, out) {
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.rmSync(out, { force: true });
  execFileSync("zip", ["-r", "-X", "-q", out, ...FILES], { cwd });
  console.log(out);
}

// Chrome・Edge 用
zip(ROOT, path.join(DIST, `${NAME}-${manifest.version}.zip`));

// Firefox 用(manifest を書き換えた作業フォルダを zip にする)
const ffDir = path.join(DIST, "firefox-src");
fs.rmSync(ffDir, { recursive: true, force: true });
for (const f of FILES) fs.cpSync(path.join(ROOT, f), path.join(ffDir, f), { recursive: true });
const ff = structuredClone(manifest);
ff.browser_specific_settings = {
  gecko: {
    id: GECKO_ID,
    // 128 以降は MV3 のホスト権限がインストール時に許可される
    strict_min_version: "128.0",
    // 個人データを一切収集しない(AMO の組み込みのデータ同意画面に表示される)
    data_collection_permissions: { required: ["none"] },
  },
};
if (ff.background?.service_worker) ff.background = { scripts: [ff.background.service_worker] };
fs.writeFileSync(path.join(ffDir, "manifest.json"), JSON.stringify(ff, null, 2) + "\n");
zip(ffDir, path.join(DIST, "firefox", `${NAME}-${manifest.version}-firefox.zip`));
