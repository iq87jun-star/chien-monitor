// スプレッドシートのアドオンで使う計算部分。計算API(calc-api)と同じコードを1つのファイルにまとめ、
// Apps Script では グローバルの JPCalc として使う(scripts/build.mjs で dist/lib.js に書き出す)。
import { analyzeRealty, analyzeSalary } from "../../calc-api/src/calc.js";
import { calculateTakeHome } from "../../calc-api/src/takehome.js";
import {
  HOLIDAYS,
  RANGE,
  addBusinessDays,
  calendarDay,
  calendarHolidays,
  countBusinessDays,
  fromWareki,
  parseDate,
  toWareki,
} from "../../calc-api/src/calendar.js";

// 拡張の parser.js はクラシックスクリプトとして globalThis に公開される(上の import の時点で読み込み済み)
export const RealtyParser = globalThis.RealtyParser;
export const JobParser = globalThis.JobParser;
export {
  HOLIDAYS,
  RANGE,
  addBusinessDays,
  analyzeRealty,
  analyzeSalary,
  calculateTakeHome,
  calendarDay,
  calendarHolidays,
  countBusinessDays,
  fromWareki,
  parseDate,
  toWareki,
};
