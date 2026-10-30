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
  // イーシェンは儀玄の読み
  assert.deepEqual(parseRoster("雅両完凸 葉瞬光M2 イシェン", "zzz"), {
    星見雅: { cons: 6, mochi: true },
    葉瞬光: { cons: 2, mochi: false },
    儀玄: { cons: 0, mochi: false },
  });
  // 「花火」と「火花」は別のキャラ
  assert.deepEqual(Object.keys(parseRoster("火花完凸 花火", "houkaistarrail")).sort(), ["火花", "花火"].sort());
  assert.deepEqual(parseRoster("カルテジア完凸餅 ショアキ", "wutheringwaves"), {
    カルテジア: { cons: 6, mochi: true },
    ショアキーパー: { cons: 0, mochi: false },
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
  // 呼び名があれば「〇〇様」はそちらを使う
  assert.match(fillTemplate(posted, { ...c, name: "らもん" }), /【No\.12】らもん様/);
});

test("代理出品: 査定ページからの相談と集計画面の更新を確かめる", async () => {
  const { validLead, validPatch } = await import("../src/consign.js");
  const games = ["genshin-impact", "houkaistarrail"];
  assert.deepEqual(validLead({ game: "genshin-impact", handle: "@Abc_1", wish: 50000, chars: [{ name: "夜蘭", cons: 9 }], low: 1, high: 2, sid: "x" }, games), {
    game: "genshin-impact", handle: "Abc_1", name: null, chars: [{ name: "夜蘭", cons: 6, mochi: false }], low: 1, high: 2, wish: 50000, sid: "x", memo: null,
  });
  // @ID として読めない入力は断らず、呼び名にする
  const named = validLead({ game: "genshin-impact", handle: "じゃるぎ" }, games);
  assert.equal(named.handle, null);
  assert.equal(named.name, "じゃるぎ");
  // 全角の「＠」付きでもユーザー名として読む
  assert.equal(validLead({ game: "genshin-impact", handle: "＠Abc_1" }, games).handle, "Abc_1");
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

test("代理出品: 同じ人がもう一度送った相談は前の番号にまとめる", async () => {
  const { DatabaseSync } = await import("node:sqlite");
  const { readFileSync } = await import("node:fs");
  const { createLead } = await import("../src/consign.js");
  const db = new DatabaseSync(":memory:");
  for (const f of ["0003_consign.sql", "0004_consign_name.sql"]) db.exec(readFileSync(new URL(`../migrations/${f}`, import.meta.url), "utf8"));
  // D1 の prepare().bind().first()/run() だけをまねる
  const env = { DB: { prepare: (q) => ({ bind: (...a) => ({ first: async () => db.prepare(q).get(...a) ?? null, run: async () => db.prepare(q).run(...a) }) }) } };
  const lead = (o) => ({ game: "houkaistarrail", handle: null, chars: [], low: 1, high: 2, wish: null, sid: "s1", ...o });
  assert.deepEqual(await createLead(env, lead({})), { id: 1, merged: false });
  // 同じ画面からもう一度 → No.1 にまとめ、新しく書いたユーザー名・希望額で上書き
  assert.deepEqual(await createLead(env, lead({ handle: "abc", wish: 30000, low: 5 })), { id: 1, merged: true });
  // 別の画面でも同じユーザー名ならまとめる
  assert.deepEqual(await createLead(env, lead({ sid: "s2", handle: "abc" })), { id: 1, merged: true });
  const r = db.prepare("SELECT handle, wish, low FROM consign WHERE id = 1").get();
  assert.deepEqual({ ...r }, { handle: "abc", wish: 30000, low: 1 });
  // 別のゲーム・別の人は新しい番号
  assert.equal((await createLead(env, lead({ game: "zzz" }))).id, 2);
  assert.equal((await createLead(env, lead({ sid: "s3" }))).id, 3);
  // 終わった相談にはまとめない
  db.prepare("UPDATE consign SET status = '見送り' WHERE id = 3").run();
  assert.equal((await createLead(env, lead({ sid: "s3" }))).id, 4);
});

test("分割: 毎月の予定・残り・遅れ・今日やること", async () => {
  const { monthly, splitState, priceDown, todos } = await import("../public/lib/stock.js");
  // 1/31 始まりは月末にそろえる
  assert.deepEqual(monthly("2026-12-31", 3, 7000).map((p) => p.due_on), ["2026-12-31", "2027-01-31", "2027-02-28"]);
  const pays = monthly("2026-09-26", 15, 7000).map((p, i) => ({ ...p, paid_on: i === 0 ? "2026-09-26" : null }));
  const sp = { id: 1, buyer: "りょう", total: 105000, status: "支払い中", pays };
  let st = splitState(sp, pays, "2026-10-25");
  assert.deepEqual([st.paid, st.remaining, st.count, st.next.due_on, st.late, st.mismatch], [7000, 98000, [1, 15], "2026-10-26", null, false]);
  assert.match(todos([], [sp], "2026-10-25")[0].text, /支払日です/);
  st = splitState(sp, pays, "2026-10-29");
  assert.deepEqual(st.late, { n: 1, days: 3, amount: 7000 });
  assert.match(todos([], [sp], "2026-10-29")[0].text, /3日遅れています/);
  // 値下げは7日たってから、千円単位で下限まで
  const s = { id: 1, status: "出品中", price: 200000, floor: 195000, price_at: "2026-10-01" };
  assert.equal(priceDown(s, "2026-10-07"), null);
  assert.deepEqual(priceDown(s, "2026-10-08"), { from: 200000, to: 195000 });
  assert.equal(priceDown({ ...s, price: 195000 }, "2026-10-20"), null);
});

test("在庫・分割の API の入力チェックと保存", async () => {
  const { DatabaseSync } = await import("node:sqlite");
  const { readFileSync } = await import("node:fs");
  const st = await import("../src/stock.js");
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(new URL("../migrations/0005_stock.sql", import.meta.url), "utf8"));
  const stmt = (q, a = []) => ({
    first: async () => db.prepare(q).get(...a) ?? null,
    run: async () => ({ meta: { changes: Number(db.prepare(q).run(...a).changes) } }),
    all: async () => ({ results: db.prepare(q).all(...a) }),
  });
  const env = { DB: { prepare: (q) => ({ ...stmt(q), bind: (...a) => stmt(q, a) }), batch: (list) => Promise.all(list.map((s) => s.all())) } };
  const games = ["genshin-impact"];
  assert.equal(st.validStock({ game: "x" }, games), null);
  assert.equal(st.validStock({ price: -1 }, games), null);
  const id = await st.createStock(env, st.validStock({ game: "genshin-impact", chars: [{ name: "スカーク", cons: 6 }], listings: [{ site: "ゲームトレード", url: "javascript:x" }] }, games));
  const [s] = await st.listStock(env);
  assert.deepEqual([s.id, s.status, s.chars[0].cons, s.listings[0].url], [id, "未出品", 6, ""]);
  assert.equal(await st.updateStock(env, id, st.validStock({ status: "商談中", price: "" }, games)), true);
  assert.equal(st.validSplit({ game: "genshin-impact", buyer: "", total: 1 }, games), null);
  const sid = await st.createSplit(env, st.validSplit({ game: "genshin-impact", buyer: "あお", total: 200000 }, games), [st.validPay({ due_on: "2026-10-20", amount: 10000 })]);
  const payId = await st.addPay(env, sid, st.validPay({ due_on: "2026-11-20", amount: 20000 }));
  await st.updatePay(env, payId, st.validPay({ paid_on: "2026-11-19" }));
  const [sp] = await st.listSplit(env);
  assert.deepEqual([sp.buyer, sp.status, sp.pays.length, sp.pays[1].paid_on], ["あお", "支払い中", 2, "2026-11-19"]);
  assert.equal(await st.deletePay(env, payId), true);
});

test("画像は形と大きさを確かめてから受け取る", async () => {
  const { validImage, MAX_IMAGE_B64 } = await import("../src/stock.js");
  const ok = { owner: "stock", owner_id: 1, mime: "image/jpeg", data: "QUJD", w: 10, h: 20 };
  assert.deepEqual(validImage(ok), ok);
  assert.equal(validImage({ ...ok, owner: "consign" }), null);
  assert.equal(validImage({ ...ok, owner_id: "1" }), null);
  assert.equal(validImage({ ...ok, mime: "text/html" }), null);
  assert.equal(validImage({ ...ok, data: "<script>" }), null);
  assert.equal(validImage({ ...ok, data: "A".repeat(MAX_IMAGE_B64 + 4) }), null);
});

test("購入希望: 欲しいキャラと凸数・予算で在庫を探す", async () => {
  const { matchOf, matchesFor, todos } = await import("../public/lib/stock.js");
  const want = { id: 1, name: "YURI", game: "genshin-impact", status: "希望中", budget: 120000, wants: [{ name: "マーヴィカ", cons: 2 }, { name: "フリーナ", cons: 0 }] };
  const a = { id: 3, game: "genshin-impact", status: "出品中", price: 110000, chars: [{ name: "マーヴィカ", cons: 6 }, { name: "フリーナ", cons: 1 }] };
  const b = { id: 4, game: "genshin-impact", status: "出品中", price: 130000, chars: [{ name: "マーヴィカ", cons: 1 }, { name: "フリーナ", cons: 0 }] };
  const c = { id: 9, game: "houkaistarrail", status: "出品中", price: 1, chars: [{ name: "フリーナ", cons: 6 }] };
  assert.deepEqual([matchOf(want, a.chars, a.price).full, matchOf(want, a.chars, a.price).inBudget], [2, true]);
  // 凸数が足りないキャラは数えない・予算オーバーは印を付ける
  assert.deepEqual([matchOf(want, b.chars, b.price).full, matchOf(want, b.chars, b.price).inBudget], [1, false]);
  assert.deepEqual(matchesFor(want, [b, c, a]).map((m) => m.stock.id), [3, 4]);
  assert.deepEqual(matchesFor({ ...want, status: "成約" }, [a]), []);
  const t = todos([a, b], [], "2026-10-14", undefined, [{ ...want, next_at: "2026-10-14" }]);
  assert.deepEqual(t.map((x) => x.kind), ["want", "want"]);
  assert.match(t[1].text, /在庫 No\.3/);
  // 提案済みの在庫は知らせない
  assert.equal(todos([a], [], "2026-10-14", undefined, [{ ...want, proposed: "在庫3" }]).length, 0);
});

test("購入希望の保存", async () => {
  const { DatabaseSync } = await import("node:sqlite");
  const { readFileSync } = await import("node:fs");
  const st = await import("../src/stock.js");
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(new URL("../migrations/0007_wants.sql", import.meta.url), "utf8"));
  const stmt = (q, a = []) => ({
    first: async () => db.prepare(q).get(...a) ?? null,
    run: async () => ({ meta: { changes: Number(db.prepare(q).run(...a).changes) } }),
    all: async () => ({ results: db.prepare(q).all(...a) }),
  });
  const env = { DB: { prepare: (q) => ({ ...stmt(q), bind: (...a) => stmt(q, a) }) } };
  assert.equal(st.validWant({ name: "x", game: "zzz" }, ["genshin-impact"]), null);
  const id = await st.createWant(env, st.validWant({ name: "YURI", game: "genshin-impact", wants: [{ name: "フリーナ", cons: 2 }], budget: "100000", split: "1" }, ["genshin-impact"]));
  await st.updateWant(env, id, st.validWant({ status: "提案済み", proposed: "在庫3,4" }, ["genshin-impact"]));
  const [w] = await st.listWants(env);
  assert.deepEqual([w.name, w.status, w.wants[0].cons, w.budget, w.split, w.proposed], ["YURI", "提案済み", 2, 100000, true, "在庫3,4"]);
});

test("フォロー候補: 表の読み取りと判定(ボット・業者を外し、○以上を20人まで)", async () => {
  const { parseTable, gradeRow, pickForToday, dueForCheck } = await import("../public/lib/follow.js");
  const text = `#\t@ID\tフォロー\tフォロワー\t作成年月\t投稿内容（一言）
1\t@hoimu_ir\t92\t50\t2025年7月\t別ゲーを引退し、モンストや原神をもっと楽しむ
3\t@zeroo013847361\t1\t27\t2025年4月\t原神石垢・引退垢の販売（業者）
6\t@Kan3Mei1Tetudou\t2,787\t1,596\t2017年8月\t原神とDBDを完全に引退
| 7 | @chomochocomo | 213 | 136 | 2015年1月 | 原神引退するしかない |
12\t@AKA_SB_Razor\t914\t435\t2019年1月\t原神引退しようかしら
x\t@FinleyDaviehnq\t91\t54\t2026年7月\t無言フォローすみません
y\t@m__811_\t13\t12\t2024年1月\tFF20⬇️
z\t@ae__n123\t101\t71\t2023年5月\t仕事と家事が忙しいので原神引退`;
  const rows = parseTable(text);
  assert.equal(rows.length, 8);
  assert.deepEqual(rows[2], { handle: "Kan3Mei1Tetudou", following: 2787, followers: 1596, joined: "2017年8月", note: "原神とDBDを完全に引退" });
  assert.equal(rows[3].handle, "chomochocomo");
  const g = Object.fromEntries(rows.map((r) => [r.handle, gradeRow(r, "2026-10-18").grade]));
  assert.deepEqual(g, { hoimu_ir: "○", zeroo013847361: "×", Kan3Mei1Tetudou: "◎", chomochocomo: "◎", AKA_SB_Razor: "△", FinleyDaviehnq: "×", m__811_: "×", ae__n123: "○" });
  const { take } = pickForToday(rows, "2026-10-18", new Set(["ae__n123"]));
  assert.deepEqual(take.map((x) => x.handle), ["Kan3Mei1Tetudou", "chomochocomo", "hoimu_ir"]);
  const list = [{ status: "フォロー済み", followed_on: "2026-10-04" }, { status: "フォロー済み", followed_on: "2026-10-05" }, { status: "候補" }];
  assert.equal(dueForCheck(list, "2026-10-18").length, 1);
});

test("フォロー候補の保存と状態", async () => {
  const { DatabaseSync } = await import("node:sqlite");
  const { readFileSync } = await import("node:fs");
  const fl = await import("../src/follow.js");
  const db = new DatabaseSync(":memory:");
  db.exec(readFileSync(new URL("../migrations/0008_follow.sql", import.meta.url), "utf8"));
  const stmt = (q, a = []) => ({
    first: async () => db.prepare(q).get(...a) ?? null,
    run: async () => ({ meta: { changes: Number(db.prepare(q).run(...a).changes) } }),
    all: async () => ({ results: db.prepare(q).all(...a) }),
  });
  const env = { DB: { prepare: (q) => ({ ...stmt(q), bind: (...a) => stmt(q, a) }) } };
  const t = "1\t@aaa\t10\t10\t2020年1月\t原神を完全に引退\n2\t@bbb\t10\t10\t2020年1月\t原神引退垢の販売";
  const r1 = await fl.importFollow(env, t);
  assert.deepEqual(r1.added, ["aaa"]);
  assert.equal((await fl.importFollow(env, t)).added.length, 0);
  const [f] = await fl.listFollow(env);
  assert.equal(await fl.setFollowStatus(env, f.id, "フォロー済み"), true);
  assert.equal(await fl.setFollowStatus(env, f.id, "勝手な状態"), false);
  const [g] = await fl.listFollow(env);
  assert.deepEqual([g.status, Boolean(g.followed_on)], ["フォロー済み", true]);
});

test("詐欺対策: 引き渡し前のチェック・見守り・要注意リスト", async () => {
  const { HANDOVER, handoverLeft, watchDue, cautionHit, todos } = await import("../public/lib/stock.js");
  assert.equal(handoverLeft({}).length, Object.keys(HANDOVER).length);
  assert.deepEqual(handoverLeft(Object.fromEntries(Object.keys(HANDOVER).map((k) => [k, true]))), []);
  // 見守りは 1・3・7 日後。確認した回数(watch)より予定が多い時だけ出す
  const s = { id: 3, handed_on: "2026-10-10", watch: 0 };
  assert.equal(watchDue(s, "2026-10-10"), null);
  assert.deepEqual(watchDue(s, "2026-10-11"), { n: 1, day: 1 });
  assert.equal(watchDue({ ...s, watch: 1 }, "2026-10-12"), null);
  assert.deepEqual(watchDue({ ...s, watch: 1 }, "2026-10-13"), { n: 2, day: 3 });
  assert.equal(watchDue({ ...s, watch: 3 }, "2026-11-30"), null);
  // @ID は前後が区切られている時だけ当てる(abc は abcd に当てない)
  const cs = [{ handle: "bad_guy", reason: "引き戻し" }];
  assert.equal(cautionHit(cs, "X: @Bad_Guy")?.reason, "引き戻し");
  assert.equal(cautionHit(cs, "bad_guy2"), null);
  assert.equal(cautionHit(cs, null), null);
  const t = todos([{ ...s, status: "売却済み", listings: [] }], [], "2026-10-11", undefined, [{ id: 1, name: "a", contact: "@bad_guy", status: "希望中", wants: [] }], [{ id: 9, handle: "bad_guy", status: "新規" }], cs);
  assert.ok(t.some((x) => x.kind === "stock" && x.watch === 1 && /引き渡しから1日/.test(x.text)));
  assert.ok(t.some((x) => x.kind === "want" && x.level === 3 && /要注意/.test(x.text)));
  assert.ok(t.some((x) => x.kind === "consign" && /No\.9 は要注意/.test(x.text)));
});

test("詐欺対策: チェックが残っていると引き渡し完了にできない", async () => {
  const { DatabaseSync } = await import("node:sqlite");
  const { handoverMissing, validStock } = await import("../src/stock.js");
  const { HANDOVER } = await import("../public/lib/stock.js");
  const db = new DatabaseSync(":memory:");
  for (const f of ["0003_consign.sql", "0004_consign_name.sql", "0005_stock.sql", "0009_safety.sql"]) db.exec(readFileSync(new URL(`../migrations/${f}`, import.meta.url), "utf8"));
  const env = { DB: { prepare: (q) => ({ bind: (...a) => ({ first: async () => db.prepare(q).get(...a) ?? null }) }) } };
  db.prepare("INSERT INTO stock (created_at, updated_at, game, status, handover) VALUES ('', '', 'granblue', '商談中', ?)").run(JSON.stringify({ proof: true }));
  // 引き渡し以外の変更は止めない
  assert.deepEqual(await handoverMissing(env, "stock", 1, { price: 1000 }), []);
  // チェックを送らない時は保存済みのチェックで、送った時はそのチェック(画面の全部の状態)で確かめる
  assert.equal((await handoverMissing(env, "stock", 1, { handed_on: "2026-10-19" })).length, Object.keys(HANDOVER).length - 1);
  const patch = validStock({ handed_on: "2026-10-19", handover: { proof: true, pay: true, link: true, mail: true } }, ["granblue"]);
  assert.deepEqual(await handoverMissing(env, "stock", 1, patch), [HANDOVER.pass, HANDOVER.receipt]);
  const all = validStock({ handed_on: "2026-10-19", handover: Object.fromEntries(Object.keys(HANDOVER).map((k) => [k, true])) }, ["granblue"]);
  assert.deepEqual(await handoverMissing(env, "stock", 1, all), []);
  // 分割は「引き渡し済み」にする時も確かめる
  db.prepare("INSERT INTO split (created_at, updated_at, game, buyer, total, status) VALUES ('', '', 'granblue', 'a', 1, '完済')").run();
  assert.equal((await handoverMissing(env, "split", 1, { status: "引き渡し済み" })).length, Object.keys(HANDOVER).length);
});

test("チェック式査定(グラブル・ウマ娘・第五人格): 学習モデルの目安額と取引しやすさ", async () => {
  const { CHECK, checkEstimate, checkDetail, checkFeatureNames } = await import("../public/lib/check.js");
  const { fillTemplate } = await import("../public/lib/dm.js");
  const model = JSON.parse(readFileSync(new URL("../public/check-model.json", import.meta.url), "utf8"));
  const safe = { login: "id", mail: "yes", origin: "self", receipt: "yes" };
  for (const game of Object.keys(CHECK)) {
    const m = model.games[game];
    assert.deepEqual(m.features, checkFeatureNames(game, m.terms));
    // 「持っているもの」の候補は学習した語の中から。選ぶと金額が上がる
    assert.ok(m.pick.length > 0 && m.pick.every((t) => m.terms.includes(t)));
    const base = checkEstimate(model, game, {}, safe);
    const withPick = checkEstimate(model, game, {}, safe, [m.pick[0]]);
    assert.deepEqual(withPick.has, [m.pick[0]]);
    assert.ok(withPick.market.high > base.market.high, `${game} ${m.pick[0]}`);
    // 自由に書いた文も語に切って使う
    assert.deepEqual(checkEstimate(model, game, {}, safe, [`${m.pick[0]}・${m.pick[1]}`]).has.sort(), [m.pick[0], m.pick[1]].sort());
    // 項目の重みは 0 以上(数が多いほど安くなる査定にしない)
    m.features.forEach((f, i) => f.startsWith("log:") && assert.ok(m.weights[i] >= 0, `${game} ${f}`));
    const r = checkEstimate(model, game, {}, safe);
    assert.ok(r.low > 0 && r.low < r.high && r.low % 1000 === 0);
    // 買取額は相場より低い
    assert.ok(r.high < r.market.high);
  }
  const r = checkEstimate(model, "granblue", { rank: "250", ssr: "400", crystal: "30,000", eternals: "10", evokers: "6", hihi: "3", kongo: "2" }, safe);
  assert.equal(r.safety.level, "ok");
  assert.ok(r.high >= checkEstimate(model, "granblue", { rank: "100" }, safe).high);
  assert.equal(checkEstimate(model, "granblue", { eternals: 99 }, safe).values.eternals, 10);
  // SNS 連携だけ・買ったアカウントは金額を出さない
  const ng = checkEstimate(model, "umamusume", { ssr_lb: 15 }, { ...safe, login: "sns" });
  assert.equal(ng.safety.level, "ng");
  assert.equal(ng.low, null);
  assert.equal(checkEstimate(model, "umamusume", {}, { ...safe, origin: "bought" }).low, null);
  // 未回答・レシートなしは「確認が要る」
  assert.equal(checkEstimate(model, "umamusume", {}, { ...safe, receipt: "no" }).safety.level, "check");
  assert.equal(checkEstimate(model, "umamusume", {}, {}).safety.level, "check");
  assert.throws(() => checkEstimate(model, "x", {}, {}));
  assert.match(checkDetail("granblue", r, safe), /十天衆の最終上限解放\(人\) 10[\s\S]*相場[\s\S]*◎ 安心[\s\S]*引き継ぎ: ゲーム会社のID/);
  assert.match(checkDetail("identityv", checkEstimate(model, "identityv", { survivor: 8 }, safe), safe), /サバイバーの段位 最高峰7段/);
  // 定型文の {X} は、ゲームごとの窓口の X
  assert.equal(fillTemplate("{X}", { id: 1, game: "granblue" }), "@meruru_prop");
  assert.equal(fillTemplate("{X}", { id: 1, game: "identityv" }), "@meruru_prop");
  assert.equal(fillTemplate("{X}", { id: 1, game: "genshin-impact" }), "@Meruru_Genshin");
  // {スクショ} はゲームごとにお願いする内容が変わる
  assert.match(fillTemplate("{スクショ}", { id: 1, game: "granblue" }), /十天衆・十賢者[\s\S]*ユーザーID/);
  assert.match(fillTemplate("{スクショ}", { id: 1, game: "houkaistarrail" }), /光円錐/);
  assert.match(fillTemplate("{スクショ}", { id: 1, game: "identityv" }), /衣装一覧/);
  assert.match(fillTemplate("{スクショ}", { id: 1, game: "unknown" }), /アカウントの内容が分かるスクショ/);
});

test("チェック式査定: 売れた出品から項目の数を読む(学習用)", async () => {
  const { listingValues, NOT_ACCOUNT } = await import("../public/lib/check.js");
  const g = listingValues("granblue", { name: "初期垢 宝晶石換算74万↑SSR計580↑ 十天輝 ヒヒ80↑ 終賢10", info: ["ランク：1", "SSRキャラクターの数：0体", "宝晶石の数：0個"] });
  assert.deepEqual(g.values, { rank: 0, ssr: 580, crystal: 740000, eternals: 10, evokers: 10, hihi: 80, kongo: 0 });
  assert.equal(g.extra.starter, true);
  // 項目欄に数があればそちらを使う
  assert.equal(listingValues("granblue", { name: "x", info: ["ランク：201", "SSRキャラクターの数：316体"] }).values.ssr, 316);
  const u = listingValues("umamusume", { name: "【画像の所持5体完凸】+120000石", info: ["チームランク：SS", "SSRサポートカードの数：60枚", "ジュエルの数：0個"] });
  assert.deepEqual(u.values, { teamss: 1, ssr: 60, ssr_lb: 5, star3: 0, jewel: 0 });
  const i = listingValues("identityv", { name: "フリーレンコラボコンプ垢 UR3", info: ["サバイバーランク：最高峰7段", "ハンターランク：3段"] });
  assert.deepEqual(i.values, { survivor: 8, hunter: 3, ur: 3, ssr: 0, collab: 5 });
  assert.ok(NOT_ACCOUNT.test("グラブルフェス2024 来場者特典 金剛晶"));
  assert.ok(!NOT_ACCOUNT.test("引退垢 十天最終"));
});

test("チェック式査定: スクショ読み取りの依頼文と結果の扱い", async () => {
  const { CHECK, checkSchema, checkPrompt, checkValues, textTerms } = await import("../public/lib/check.js");
  assert.deepEqual([...textTerms("UR衣装:フリーレン・ヒンメル【限定】JOKER 2点")], ["ur衣装", "フリーレン", "ヒンメル", "限定", "joker"]);
  // 候補の名前は、写っているものだけを選んでもらう(enum)
  const s = checkSchema("identityv", ["剪燭", "joker"]);
  assert.deepEqual(s.properties.has.items.enum, ["剪燭", "joker"]);
  assert.ok(s.required.includes("has"));
  assert.match(checkPrompt("identityv", ["剪燭", "joker"]), /has: [\s\S]*剪燭、joker/);
  assert.equal(checkSchema("identityv").properties.has, undefined);
  for (const game of Object.keys(CHECK)) {
    const schema = checkSchema(game);
    assert.deepEqual(schema.required, [...CHECK[game].fields.map((f) => f.k), "id_visible"]);
    assert.doesNotMatch(JSON.stringify(schema), /"(minimum|maximum|multipleOf|minLength|maxLength)"/);
    for (const f of CHECK[game].fields) assert.ok(f.read && checkPrompt(game).includes(`- ${f.k}: ${f.read}`), `${game}.${f.k}`);
  }
  // -1(読めない)・小数・範囲外は null か上限にそろえる
  assert.deepEqual(checkValues("granblue", { rank: 250, ssr: -1, eternals: 12, evokers: 1.5, hihi: 0 }), { rank: 250, ssr: null, crystal: null, eternals: 10, evokers: null, hihi: 0, kongo: null });
});
