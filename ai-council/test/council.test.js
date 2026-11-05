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
