import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseRoster, featureNames } from "../public/lib/features.js";
import { fitRidge, dot } from "../public/lib/model.js";
import { estimate } from "../public/lib/estimate.js";
import { prompt, SCHEMA } from "../src/worker.js";

test("タイトルからキャラごとの凸数と餅を読む(次のキャラ名の手前まで)", () => {
  assert.deepEqual(parseRoster("サンドローネ オデット マーヴィカ1凸+餅 ナヒーダ3凸", "genshin-impact"), {
    サンドローネ: { cons: 0, mochi: false },
    オデット: { cons: 0, mochi: false },
    マーヴィカ: { cons: 1, mochi: true },
    ナヒーダ: { cons: 3, mochi: false },
  });
  assert.deepEqual(parseRoster("召使完凸、ヌヴィ C2", "genshin-impact"), {
    アルレッキーノ: { cons: 6, mochi: false },
    ヌヴィレット: { cons: 2, mochi: false },
  });
  assert.deepEqual(parseRoster("黄泉両完凸 キャスE2 丹恒・騰荒", "houkaistarrail"), {
    黄泉: { cons: 6, mochi: true },
    キャストリス: { cons: 2, mochi: false },
    丹恒騰荒: { cons: 0, mochi: false },
  });
});

test("リッジ回帰は一次式を当てる", () => {
  const X = [], y = [];
  for (let i = 0; i < 50; i++) {
    const a = i % 7, b = i % 3;
    X.push([1, a, b]);
    y.push(2 + 0.5 * a - 0.25 * b);
  }
  const w = fitRidge(X, y, 1e-6);
  assert.ok(Math.abs(dot(w, [1, 4, 2]) - 3.5) < 1e-3);
});

test("査定額は上位 topK 人だけで出し、幅と買取の割合をかける", () => {
  const game = "genshin-impact";
  const features = featureNames(game);
  const weights = features.map((f) => (f === "bias" ? Math.log(100000) : f.startsWith("has:") ? 0.1 : 0));
  const model = { buyRate: 0.5, games: { [game]: { features, weights, topK: 2, band: [Math.log(0.8), Math.log(1.2)] } } };
  const r = estimate(model, game, [
    { name: "フリーナ", cons: 0, mochi: false },
    { name: "ナヒーダ", cons: 0, mochi: false },
    { name: "夜蘭", cons: 0, mochi: false },
    { name: "辞書にないキャラ", cons: 6, mochi: true },
  ]);
  assert.equal(r.keys.length, 2);
  // 相場 = 10万 × e^0.2(2人分)× 星5の数の重み 0 → 約12.2万。× 0.8〜1.2 × 0.5
  const market = 100000 * Math.exp(0.2);
  assert.equal(r.low, Math.floor((market * 0.8 * 0.5) / 1000) * 1000);
  assert.equal(r.high, Math.ceil((market * 1.2 * 0.5) / 1000) * 1000);
});

test("公開しているモデルはキャラ辞書と合っている", () => {
  const model = JSON.parse(readFileSync(new URL("../public/model.json", import.meta.url)));
  assert.equal(model.buyRate, 0.55);
  for (const [game, m] of Object.entries(model.games)) {
    assert.deepEqual(m.features, featureNames(game));
    assert.ok(m.band[0] < 0 && m.band[1] > 0);
  }
});

test("読み取りの指示にキャラ名の一覧が入る", () => {
  assert.match(prompt("houkaistarrail"), /キャストリス/);
  assert.match(prompt("genshin-impact"), /命ノ星座/);
});

test("読み取り結果の形は構造化出力で使えない制約(minimum など)を含まない", () => {
  assert.doesNotMatch(JSON.stringify(SCHEMA), /"(minimum|maximum|multipleOf|minLength|maxLength)"/);
});

test("利用記録は形を確かめ、個人を特定できるものは受け取らない", async () => {
  const { validEvent } = await import("../src/events.js");
  const games = ["genshin-impact", "houkaistarrail"];
  const ev = validEvent(
    { kind: "estimate", game: "houkaistarrail", sid: "abcdEFGH1234", chars: [{ name: " 黄泉 ", cons: 9, mochi: 1, uid: "123" }], low: 50000, high: 90000, ip: "1.2.3.4" },
    games,
  );
  assert.deepEqual(ev, { kind: "estimate", game: "houkaistarrail", sid: "abcdEFGH1234", chars: [{ name: "黄泉", cons: 6, mochi: true }], low: 50000, high: 90000, ok: 1 });
  assert.equal(validEvent({ kind: "hack", game: "houkaistarrail", sid: "abcdEFGH1234" }, games), null);
  assert.equal(validEvent({ kind: "dm", game: "x", sid: "abcdEFGH1234" }, games), null);
  assert.equal(validEvent({ kind: "dm", game: "houkaistarrail", sid: "<script>" }, games), null);
  assert.equal(validEvent({ kind: "dm", game: "houkaistarrail", sid: "abcdEFGH1234", low: -1, high: 1.5 }, games).low, null);
});

test("代理出品: 定型文に管理番号・ユーザー名・金額・投稿URLを差し込む", async () => {
  const { fillTemplate, DEFAULT_TEMPLATES } = await import("../src/consign.js");
  const c = { id: 12, handle: "meru_fan", game: "houkaistarrail", chars: [{ name: "黄泉", cons: 6 }, { name: "花火", cons: 0 }], low: 51000, high: 96000, wish: 80000, post_url: "https://x.com/Meruru_Genshin/status/1", next_at: "2026-10-09" };
  assert.equal(fillTemplate("{番号}|{名前}|{ゲーム}|{キャラ}|{査定額}|{希望額}|{投稿URL}|{期限}", c), "12|@meru_fan|スタレ|黄泉完凸・花火|5.1万円〜9.6万円|8万円|https://x.com/Meruru_Genshin/status/1|10月9日");
  const posted = DEFAULT_TEMPLATES.find((t) => t.key === "posted").body;
  assert.match(fillTemplate(posted, c), /【No\.12】@meru_fan様[\s\S]*status\/1[\s\S]*いいね[\s\S]*リアクション/);
});

test("代理出品: 査定ページからの相談と集計画面の更新を確かめる", async () => {
  const { validLead, validPatch } = await import("../src/consign.js");
  const games = ["genshin-impact", "houkaistarrail"];
  assert.deepEqual(validLead({ game: "genshin-impact", handle: "@Abc_1", wish: 50000, chars: [{ name: "夜蘭", cons: 9 }], low: 1, high: 2, sid: "x" }, games), {
    game: "genshin-impact", handle: "Abc_1", chars: [{ name: "夜蘭", cons: 6, mochi: false }], low: 1, high: 2, wish: 50000, sid: "x",
  });
  assert.equal(validLead({ game: "genshin-impact", handle: "bad handle!" }, games), null);
  assert.equal(validLead({ game: "x" }, games), null);
  assert.equal(validLead({ game: "houkaistarrail" }, games).handle, null);
  assert.deepEqual(validPatch({ status: "出品中", wish: "70000", next_at: "2026-10-10", post_url: "https://evil.example/", handle: "", memo: " m " }), {
    status: "出品中", wish: 70000, next_at: "2026-10-10", post_url: null, handle: null, memo: "m",
  });
  assert.deepEqual(validPatch({ status: "不明", next_at: "10/10" }), { next_at: null });
});

test("成約データの上限を超える高額アカウントは、金額を断言せず個別査定にする", () => {
  const game = "genshin-impact";
  const features = featureNames(game);
  const weights = features.map((f) => (f === "bias" ? Math.log(100000) : f.startsWith("has:") ? 0.3 : 0));
  const model = { buyRate: 0.5, games: { [game]: { features, weights, topK: 30, band: [Math.log(0.8), Math.log(1.2)], cap: 200000 } } };
  const many = ["フリーナ", "ナヒーダ", "夜蘭", "千織", "閑雲", "雷電将軍"].map((name) => ({ name, cons: 6, mochi: true }));
  const r = estimate(model, game, many); // 相場 10万 × e^1.8 ≒ 60万 > 上限 20万
  assert.equal(r.capped, true);
  assert.equal(r.high, null);
  assert.equal(r.low, 100000); // 上限 20万 × 0.5
  assert.equal(estimate(model, game, many.slice(0, 1)).capped, undefined);
});
