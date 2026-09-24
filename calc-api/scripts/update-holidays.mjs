// 内閣府の「国民の祝日」CSV(1955年〜翌年分。Shift_JIS)を取得して src/holidays.json に書き出す。
// 内閣府は例年2月頃に翌年分を追加する。calc-api ワークフローが毎月確認し、更新があれば知らせる。
//   node scripts/update-holidays.mjs          … 取得して書き出す
//   node scripts/update-holidays.mjs --check  … 書き出さずに、取り込み済みと違えば終了コード1
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const URL = "https://www8.cao.go.jp/chosei/shukujitsu/syukujitsu.csv";
const OUT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "src", "holidays.json");

const res = await fetch(URL);
if (!res.ok) throw new Error(`HTTP ${res.status}`);
const text = new TextDecoder("shift_jis").decode(await res.arrayBuffer());
const holidays = {};
for (const line of text.split(/\r?\n/).slice(1)) {
  const [d, name] = line.split(",");
  const m = /^(\d{4})\/(\d{1,2})\/(\d{1,2})$/.exec(d?.trim() ?? "");
  if (!m || !name) continue;
  holidays[`${m[1]}-${m[2].padStart(2, "0")}-${m[3].padStart(2, "0")}`] = name.trim();
}
const days = Object.keys(holidays).sort();
if (days.length < 900) throw new Error(`too few holidays (${days.length})`);
const out = {
  source: URL,
  from: `${days[0].slice(0, 4)}-01-01`,
  to: `${days.at(-1).slice(0, 4)}-12-31`,
  holidays: Object.fromEntries(days.map((d) => [d, holidays[d]])),
};
const json = JSON.stringify(out, null, 0) + "\n";
if (process.argv.includes("--check")) {
  const current = await fs.readFile(OUT, "utf8").catch(() => "");
  if (current !== json) {
    console.error(
      `祝日データに更新があります(${out.from}〜${out.to})。npm run holidays で取り込んでください`,
    );
    process.exit(1);
  }
  console.log("祝日データは最新です");
} else {
  await fs.writeFile(OUT, json);
  console.log(`${days.length} holidays, ${out.from} .. ${out.to} → ${OUT}`);
}
