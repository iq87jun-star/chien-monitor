// 法人番号(13桁)とインボイスの登録番号(T + 13桁)の検査。外部と通信せず、形と検査用数字だけを確かめる。
// 検査用数字(先頭の1桁)= 9 − (Σ Pn × Qn を 9 で割った余り)
//   Pn: 残り12桁の、最下位を1桁目とした n 桁目の数字 / Qn: n が奇数なら1、偶数なら2(法人番号の指定等に関する省令)
// 登録番号は、法人は「T + 法人番号」、個人事業者は法人番号と重ならない13桁。どちらも同じ検査用数字を使う
// (国税庁の公表サイトの差分データ 約2万件で、法人・個人とも全件一致することを確かめた)。
// 正しい形でも、実際に登録されているか(取消・失効を含む)は国税庁のサイトで確かめる必要がある。
import { InputError } from "./calc.js";

const MAX_INPUT = 40;

export function checkDigitOf(base12) {
  let sum = 0;
  for (let n = 1; n <= 12; n++) sum += Number(base12[12 - n]) * (n % 2 === 1 ? 1 : 2);
  return 9 - (sum % 9);
}

// 「Ｔ１２３４-5678…」「登録番号：T1234…(株式会社○○)」→ "T1234…" / "1234…"。空白・ハイフン・前後の文字は読み飛ばす
export function normalizeNumber(input) {
  const s = String(input ?? "")
    .normalize("NFKC")
    .toUpperCase()
    .replace(/[\s\-‐‑‒–—―ー−]/g, "");
  // 数字の並びがいくつかあれば、いちばん長いもの(番号の前後の日付や金額を拾わない)
  let best = null;
  for (const m of s.matchAll(/(T?)(\d+)/g)) if (!best || m[2].length > best[2].length) best = m;
  return best ? best[1] + best[2] : "";
}

const ERRORS = {
  empty: { ja: "番号がありません", en: "No number found" },
  length: { ja: "数字が13桁ではありません", en: "The number must have 13 digits" },
  check_digit: {
    ja: "検査用数字(先頭の1桁)が合いません。打ち間違いの可能性があります",
    en: "Check digit (first digit) does not match; the number is probably mistyped",
  },
};

// POST /v1/invoice/validate-number { number }
export function validateNumber(body) {
  const input = body?.number;
  if (typeof input !== "string" && typeof input !== "number") {
    throw new InputError('"number" is required (e.g. "T1234567890123" or a 13-digit corporate number)', "number");
  }
  if (String(input).length > MAX_INPUT) {
    throw new InputError(`"number" must be ${MAX_INPUT} characters or less`, "number");
  }
  const normalized = normalizeNumber(input);
  const isRegistration = normalized.startsWith("T");
  const digits = normalized.replace(/^T/, "");
  const result = {
    input: String(input),
    type: isRegistration ? "registration_number" : "corporate_number",
    normalized: normalized || null,
    valid: false,
    error: null,
    checkDigit: null,
    expectedCheckDigit: null,
    registrationNumber: null,
    lookupUrl: null,
  };
  const fail = (code) => ({ ...result, error: { code, ...ERRORS[code] } });
  if (!digits) return fail("empty");
  if (digits.length !== 13) return fail("length");
  const expected = checkDigitOf(digits.slice(1));
  Object.assign(result, { checkDigit: Number(digits[0]), expectedCheckDigit: expected });
  if (Number(digits[0]) !== expected) return fail("check_digit");
  return {
    ...result,
    valid: true,
    // 法人番号なら、その法人の登録番号は T + 法人番号(登録しているかは別)
    registrationNumber: `T${digits}`,
    lookupUrl: isRegistration
      ? `https://www.invoice-kohyo.nta.go.jp/regno-search/detail?selRegNo=${digits}`
      : `https://www.houjin-bangou.nta.go.jp/henkorireki-johoto.html?selHouzinNo=${digits}`,
  };
}
