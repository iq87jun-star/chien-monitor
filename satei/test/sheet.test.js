import { test } from "node:test";
import assert from "node:assert/strict";
import { validAnswers, SHEET_FIELDS } from "../public/lib/sheet.js";
import { validSheet, validSubmit } from "../src/sheet.js";

test("引き継ぎ情報: 同意が無ければ受け付けない・選択肢以外は断る", () => {
  assert.equal(validAnswers({ uid: "1" }), null);
  assert.equal(validAnswers({ agree: true, phone: "たぶん" }), null);
  const a = validAnswers({ agree: true, uid: " 812345678(アジア) ", phone: "なし", extra: "x" });
  assert.equal(a.uid, "812345678(アジア)");
  assert.equal(a.phone, "なし");
  assert.equal(a.first_mail, "");
  assert.deepEqual(Object.keys(a), SHEET_FIELDS.map((f) => f.key));
});

test("引き継ぎ情報: レシートは4枚まで・画像の形式を確かめる", () => {
  const answers = { agree: true };
  const im = { mime: "image/jpeg", data: "AAAA", w: 10, h: 10 };
  assert.equal(validSubmit({ answers, receipts: [im, im, im, im] }).receipts.length, 4);
  assert.equal(validSubmit({ answers, receipts: [im, im, im, im, im] }), null);
  assert.equal(validSubmit({ answers, receipts: [{ ...im, mime: "text/html" }] }), null);
  assert.equal(validSubmit({ answers, receipts: [{ ...im, data: "<script>" }] }), null);
  assert.deepEqual(validSubmit({ answers }).receipts, []);
});

test("引き継ぎ情報: リンク作成の入力", () => {
  assert.deepEqual(validSheet({ consign_id: "44", game: "identityv", label: " No.44 " }, ["identityv"]), { consign_id: 44, game: "identityv", label: "No.44" });
  assert.deepEqual(validSheet({}, ["identityv"]), { consign_id: null, game: null, label: null });
  assert.equal(validSheet({ game: "ff14" }, ["identityv"]), null);
  assert.equal(validSheet({ consign_id: "-1" }, ["identityv"]), null);
});
