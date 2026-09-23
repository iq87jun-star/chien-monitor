// ストア提出用zipを dist/ に作る(manifest・src・icons のみ。テストや開発用ファイルは含めない)
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { version } = JSON.parse(fs.readFileSync(path.join(ROOT, "manifest.json"), "utf8"));
const out = path.join(ROOT, "dist", `job-salary-checker-${version}.zip`);

fs.mkdirSync(path.dirname(out), { recursive: true });
fs.rmSync(out, { force: true });
execFileSync("zip", ["-r", "-X", "-q", out, "manifest.json", "src", "icons"], { cwd: ROOT });
console.log(out);
