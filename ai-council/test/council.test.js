import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { pickEvents, calendarText, formatJST, todayJST, isGotobi, legWindows, legOverlaps, overlapText, mergeEvents } from "../src/context.js";
import { runCouncil, transcript, splitMessage } from "../src/council.js";

const config = JSON.parse(readFileSync(new URL("../config.json", import.meta.url)));
const leg = (name) => config.legs.find((l) => l.name.startsWith(name));

test("日本時間の表示", () => {
  assert.equal(formatJST(new Date("2026-11-05T13:30:00Z")), "11/5(木) 22:30");
  assert.equal(todayJST(new Date("2026-11-04T15:30:00Z")), "2026-11-05");
});

test("ゴトー日: 土日は前の金曜、月末も含む", () => {
  assert.equal(isGotobi(2026, 11, 5), true); // 木
  assert.equal(isGotobi(2026, 11, 10), true); // 火
  assert.equal(isGotobi(2026, 11, 13), true); // 15 日が日曜 → 13 日(金)
  assert.equal(isGotobi(2026, 11, 15), false); // 日曜
  assert.equal(isGotobi(2026, 11, 30), true); // 月末(月)
  assert.equal(isGotobi(2026, 11, 6), false);
  assert.equal(isGotobi(2026, 10, 30), true); // 31 日が土曜 → 30 日(金)
});

test("手法の保有時間: 金曜の朝から 4 日先に月曜の Mon4 が入る", () => {
  const now = new Date("2026-11-05T22:47:00Z"); // 11/6(金) 07:47 JST
  const w = legWindows(config.legs, now, 96);
  const mon4 = w.find((x) => x.leg.name.startsWith("Mon4"));
  assert.equal(formatJST(mon4.from), "11/9(月) 13:00");
  assert.equal(formatJST(mon4.to), "11/10(火) 19:00");
  // 実口座の EURGBP は金曜 23 時から
  assert.ok(w.some((x) => x.leg.name.includes("EURGBP") && formatJST(x.from) === "11/6(金) 23:00"));
  // 終わった窓は入らない(木曜の Roll5 は 11/5 09:00 JST に終了)
  assert.ok(!w.some((x) => x.leg.name.startsWith("Roll5") && x.to <= now));
});

test("保有時間に重なる指標・祝日を通貨で選ぶ", () => {
  const now = new Date("2026-11-05T22:47:00Z");
  const events = [
    { title: "Non-Farm Employment Change", country: "USD", date: "2026-11-06T08:30:00-05:00", impact: "High" },
    { title: "Bank Holiday", country: "JPY", date: "2026-11-09T00:00:00+09:00", impact: "Holiday" },
    { title: "CPI", country: "CHF", date: "2026-11-06T08:30:00+01:00", impact: "High" },
    { title: "Low one", country: "EUR", date: "2026-11-06T23:30:00+09:00", impact: "Low" },
  ];
  const o = legOverlaps(legWindows(config.legs, now, 96), events, config.calendar);
  const names = o.map((x) => x.leg.name);
  // 雇用統計(11/6 22:30 JST)は USD を含む手法にだけ重なる。EURGBP 23 時は USD を見ないので入らない
  assert.ok(!names.some((n) => n.includes("EURGBP")));
  // 祝日(11/9 JPY)は月曜 7 時の theoption と Mon4 に重なる
  const jpyHol = o.filter((x) => x.hits.some((e) => e.title === "Bank Holiday")).map((x) => x.leg.name);
  assert.ok(jpyHol.some((n) => n.startsWith("theoption 月曜")));
  assert.match(overlapText(o), /(祝日)/);
  assert.equal(overlapText([]), "(この先の保有時間に重なる重要指標・祝日はなし)");
  assert.ok(leg("Mon4"));
});

test("経済指標は通貨・重要度・時間で選んで時刻順、2 週分は重複なしでまとめる", () => {
  const now = new Date("2026-11-05T03:00:00Z");
  const nfp = { title: "NFP", country: "USD", date: "2026-11-06T08:30:00-05:00", impact: "High", forecast: "120K", previous: "95K" };
  const boj = { title: "BoJ", country: "JPY", date: "2026-11-05T12:00:00+09:00", impact: "High", forecast: "", previous: "" };
  const events = mergeEvents([[nfp, boj], [nfp, { title: "Too far", country: "USD", date: "2026-11-07T08:30:00-05:00", impact: "High" }]]);
  assert.equal(events.length, 3);
  const picked = pickEvents(events, config.calendar, now);
  assert.deepEqual(picked.map((e) => e.title), ["BoJ", "NFP"]);
  assert.equal(calendarText(picked), "- 11/5(木) 12:00 [JPY] BoJ\n- 11/6(金) 22:30 [USD] NFP(予想 120K / 前回 95K)");
});

test("会議: 前提と前の役の答えが次の役に渡り、1 人失敗しても続く", async () => {
  const seen = {};
  const chat = async (role, system, user) => {
    seen[role] = { system, user };
    if (role === "ideaB") throw new Error("429 混雑");
    return { text: `${role} の答え`, cost: 0.01 };
  };
  const r = await runCouncil({ config, chat, mode: "ask", question: "Mon5 を足すべきか", portfolio: "前提P", calendar: "指標Y", overlaps: "重なりZ", today: "2026-11-05" });
  assert.deepEqual(r.steps.map((s) => s.role), ["research", "ideaA", "ideaB", "critic", "chair"]);
  assert.match(seen.research.user, /Mon5 を足すべきか/);
  for (const role of ["research", "ideaA", "critic", "chair"]) {
    assert.match(seen[role].user, /前提P/);
    assert.match(seen[role].user, /重なりZ/);
    assert.match(seen[role].system, /後付けのフィルタ/);
  }
  assert.match(seen.ideaA.user, /research の答え/);
  assert.match(seen.critic.user, /ideaA の答え/);
  assert.match(seen.critic.user, /点検役B は失敗: 429 混雑/);
  assert.match(seen.chair.user, /critic の答え/);
  assert.equal(r.final, "chair の答え");
  assert.ok(Math.abs(r.cost - 0.04) < 1e-9);
  assert.match(transcript({ title: "t", ...r }), /⚠️ 失敗: 429 混雑/);
});

test("毎朝の点検では、すぐ対応・注意・やることの形で頼む", async () => {
  const seen = {};
  const chat = async (role, system, user) => ((seen[role] = user), { text: "ok" });
  await runCouncil({ config, chat, mode: "brief", question: "", portfolio: "", calendar: "", overlaps: "", today: "2026-11-05" });
  assert.match(seen.ideaA, /失格ライン/);
  assert.match(seen.chair, /すぐ対応/);
});

test("まとめ役が失敗したら final は null", async () => {
  const chat = async (role) => (role === "chair" ? { text: "  " } : { text: "ok" });
  const r = await runCouncil({ config, chat, mode: "brief", question: "", portfolio: "", calendar: "", overlaps: "", today: "2026-11-05" });
  assert.equal(r.final, null);
  assert.equal(r.steps.at(-1).error, "空の返事");
});

test("Discord 用に 2,000 字以内に分ける", () => {
  const text = ["a".repeat(1000), "b".repeat(1000), "c".repeat(4000)].join("\n");
  const parts = splitMessage(text, 1900);
  assert.ok(parts.every((p) => p.length <= 1900));
  assert.equal(parts.join("").replace(/\n/g, ""), text.replace(/\n/g, ""));
  assert.deepEqual(splitMessage("短い"), ["短い"]);
});

test("portfolio.md がある", () => {
  const p = readFileSync(new URL(`../${config.portfolio}`, import.meta.url), "utf8");
  assert.match(p, /棄却済み/);
  assert.doesNotMatch(p, /\d{7,}/); // 口座番号を書かない
});

import { decryptStatus, encryptStatus, statusText } from "../src/status.js";

test("口座データ: 暗号化して戻せる、鍵が違えば失敗", () => {
  const key = Buffer.alloc(32, 7).toString("base64");
  const obj = { updatedAt: "2026-11-06T07:30:00+09:00", prop: [] };
  assert.deepEqual(decryptStatus(encryptStatus(obj, key), key), obj);
  assert.throws(() => decryptStatus(encryptStatus(obj, key), Buffer.alloc(32, 8).toString("base64")));
  assert.throws(() => decryptStatus("AAAA", "short"), /32 バイト/);
});

test("口座データ: 失格・日次上限までの距離、重複建玉、古さを書く", () => {
  const s = {
    updatedAt: "2026-11-06T07:30:00+09:00",
    prop: [{ name: "FN-100ギャンブル", currency: "USD", balance: 92873, equity: 92500, floor: 90000, dailyLimit: 87873,
      positions: [{ symbol: "XAUUSD", side: "BUY", lots: 0.4, profit: -200 }, { symbol: "XAUUSD", side: "BUY", lots: 0.4, profit: -173 }] }],
    theoption: { balance: 395560, recent: [{ date: "11/5", leg: "EURGBP 23時 LOW", result: "勝ち", pnl: 9500 }], errors: ["213 AUDJPY 再試行で約定"] },
    warnings: ["Fin-ルビー の端末が応答なし"],
  };
  const t = statusText(s, new Date("2026-11-05T22:47:00Z"));
  assert.match(t, /0\.3 時間前/);
  assert.match(t, /失格まで 2,500/);
  assert.match(t, /日次上限まで 4,627/);
  assert.match(t, /同じ銘柄・同じ向きが複数: XAUUSD BUY ×2/);
  assert.match(t, /395,560 円/);
  assert.match(t, /\+9500 円/);
  assert.match(t, /端末が応答なし/);
  assert.doesNotMatch(t, /18 時間以上前/);
  assert.match(statusText(s, new Date("2026-11-07T07:00:00Z")), /18 時間以上前/);
});

import { extractCandidates, systemFor } from "../src/prompts.js";

test("新規開拓会議: ①②③と過去の候補を渡し、発案役の名前で呼ぶ", async () => {
  const seen = {};
  const chat = async (role, system, user) => ((seen[role] = { system, user }), { text: `${role} の答え` });
  const r = await runCouncil({ config, chat, mode: "explore", question: "", portfolio: "前提P", live: "口座L",
    calendar: "指標Y", overlaps: "重なりZ", explored: "- 2026-11-07 ① 金曜の指数", today: "2026-11-07" });
  assert.match(seen.research.user, /プロップファーム/);
  assert.match(seen.ideaA.system, /月曜の偏りを減らす/);
  assert.match(seen.ideaA.system, /theoption の新しい脚/);
  assert.match(seen.critic.system, /蒸し返し/);
  for (const role of ["research", "ideaA", "critic", "chair"]) {
    assert.match(seen[role].user, /前提P/);
    assert.match(seen[role].user, /金曜の指数/); // 過去の候補
    assert.doesNotMatch(seen[role].user, /重なりZ/); // 新規開拓では指標の重なりは渡さない
  }
  assert.match(seen.chair.user, /## 候補一覧/);
  assert.equal(r.steps[1].label, "💡 発案役A");
});

test("点検と相談では点検役のまま", () => {
  assert.match(systemFor("brief", "ideaA"), /点検役/);
  assert.match(systemFor("ask", "critic"), /点検役 2 人/);
  assert.match(systemFor("explore", "research"), /調査役/);
});

test("まとめ役の候補一覧から候補を取り出す", () => {
  const text = "本文\n- 候補として面白い\n## 候補一覧\n- 候補: ① 月末の指数 LONG\n- 候補:② FundedNext 以外の EA 可の会社\n- 候補: なし\n";
  assert.deepEqual(extractCandidates(text), ["① 月末の指数 LONG", "② FundedNext 以外の EA 可の会社"]);
  assert.deepEqual(extractCandidates("- 候補: なし"), []);
  assert.deepEqual(extractCandidates(null), []);
});
