import { test } from "node:test";
import assert from "node:assert/strict";
import { checkDigitOf, normalizeNumber, validateNumber } from "../src/regno.js";

const fails = (fn, field) => assert.throws(fn, (e) => e.field === field);

test("検査用数字: 実在する法人番号で一致する", () => {
  // 国税庁 7000012050002・公表サイトの差分データにある法人
  assert.equal(checkDigitOf("000012050002"), 7);
  assert.equal(checkDigitOf("080005006001"), 1);
  assert.equal(checkDigitOf("380001019513"), 1);
  assert.equal(checkDigitOf("430001074503"), 1);
});

test("書き方の揺れを整える(全角・小文字・ハイフン・ラベル・前後の文字)", () => {
  assert.equal(normalizeNumber("Ｔ７０００　０１２０５０００２"), "T7000012050002");
  assert.equal(normalizeNumber("t7-0000-1205-0002"), "T7000012050002");
  assert.equal(normalizeNumber("登録番号：T7000012050002（国税庁）"), "T7000012050002");
  assert.equal(normalizeNumber("2026年9月 登録番号 T7000012050002"), "T7000012050002");
  assert.equal(normalizeNumber(7000012050002), "7000012050002");
  assert.equal(normalizeNumber("なし"), "");
});

test("登録番号: 正しい番号・国税庁の確認ページ", () => {
  const r = validateNumber({ number: "T1080005006001" });
  assert.equal(r.valid, true);
  assert.equal(r.type, "registration_number");
  assert.equal(r.error, null);
  assert.equal(r.registrationNumber, "T1080005006001");
  assert.equal(r.lookupUrl, "https://www.invoice-kohyo.nta.go.jp/regno-search/detail?selRegNo=1080005006001");
});

test("法人番号: 正しい番号と、その法人の登録番号の形", () => {
  const r = validateNumber({ number: "7000012050002" });
  assert.equal(r.valid, true);
  assert.equal(r.type, "corporate_number");
  assert.equal(r.registrationNumber, "T7000012050002");
  assert.match(r.lookupUrl, /houjin-bangou\.nta\.go\.jp.*selHouzinNo=7000012050002$/);
  assert.equal(validateNumber({ number: 7000012050002 }).valid, true);
});

test("誤り: 検査用数字・桁数・番号なし", () => {
  const typo = validateNumber({ number: "T8000012050002" });
  assert.equal(typo.valid, false);
  assert.equal(typo.error.code, "check_digit");
  assert.equal(typo.checkDigit, 8);
  assert.equal(typo.expectedCheckDigit, 7);
  assert.equal(typo.lookupUrl, null);
  // 隣り合う2桁の入れ替え(よくある打ち間違い)も見つける
  assert.equal(validateNumber({ number: "T7000012500002" }).valid, false);
  assert.equal(validateNumber({ number: "T700001205000" }).error.code, "length");
  assert.equal(validateNumber({ number: "未登録" }).error.code, "empty");
  fails(() => validateNumber({}), "number");
  fails(() => validateNumber({ number: { a: 1 } }), "number");
  fails(() => validateNumber({ number: "T".repeat(41) }), "number");
});
