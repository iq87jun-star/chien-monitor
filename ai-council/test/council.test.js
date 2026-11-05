import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { breakEvenWinRate, propLimits, profileText, pickEvents, calendarText, formatJST, todayJST } from "../src/context.js";
import { runCouncil, transcript, splitMessage } from "../src/council.js";

const config = JSON.parse(readFileSync(new URL("../config.json", import.meta.url)));

test("バイナリーの損益分岐の勝率", () => {
  assert.ok(Math.abs(breakEvenWinRate(1.8) - 0.5556) < 1e-4);
  assert.equal(breakEvenWinRate(2), 0.5);
  assert.throws(() => breakEvenWinRate(1));
});

test("プロップの連敗の余裕", () => {
  const l = propLimits({ accountSize: 100000, dailyLossPct: 5, maxLossPct: 10, riskPerTradePct: 0.5 });
  assert.deepEqual(l, { risk: 500, daily: 5000, max: 10000, lossesToDaily: 10, lossesToMax: 20 });
});

test("前提の文章に計算結果が入る", () => {
  const t = profileText(config.profile);
  assert.match(t, /10 連敗で日次上限/);
  assert.match(t, /損益分岐の勝率 55\.6%/);
});

test("日本時間の表示", () => {
  assert.equal(formatJST(new Date("2026-11-05T13:30:00Z")), "11/5(木) 22:30");
  assert.equal(todayJST(new Date("2026-11-04T15:30:00Z")), "2026-11-05");
});

test("経済指標は通貨・重要度・時間で選んで時刻順", () => {
  const now = new Date("2026-11-05T03:00:00Z"); // 日本時間 12:00。36 時間後は 11/7(土) 00:00
  const events = [
    { title: "NFP", country: "USD", date: "2026-11-06T08:30:00-05:00", impact: "High", forecast: "120K", previous: "95K" },
    { title: "BoJ", country: "JPY", date: "2026-11-05T12:00:00+09:00", impact: "High", forecast: "", previous: "" },
    { title: "Low one", country: "USD", date: "2026-11-05T10:00:00-05:00", impact: "Low" },
    { title: "CHF", country: "CHF", date: "2026-11-05T10:00:00-05:00", impact: "High" },
    { title: "Old", country: "USD", date: "2026-11-04T08:30:00-05:00", impact: "High" },
    { title: "Too far", country: "USD", date: "2026-11-07T08:30:00-05:00", impact: "High" },
  ];
  const picked = pickEvents(events, config.calendar, now);
  assert.deepEqual(picked.map((e) => e.title), ["BoJ", "NFP"]);
  assert.equal(
    calendarText(picked),
    "- 11/5(木) 12:00 [JPY] BoJ\n- 11/6(金) 22:30 [USD] NFP(予想 120K / 前回 95K)",
  );
  assert.equal(calendarText([]), "(この先の重要指標はなし)");
});

test("会議: 前の役の答えが次の役に渡り、1 人失敗しても続く", async () => {
  const seen = {};
  const chat = async (role, system, user) => {
    seen[role] = user;
    if (role === "ideaB") throw new Error("429 混雑");
    return { text: `${role} の答え`, cost: 0.01 };
  };
  const r = await runCouncil({ config, chat, mode: "ask", question: "ロンドン時間のブレイク", context: "前提X", calendar: "指標Y", today: "2026-11-05" });
  assert.deepEqual(r.steps.map((s) => s.role), ["research", "ideaA", "ideaB", "critic", "chair"]);
  assert.match(seen.research, /ロンドン時間のブレイク/);
  assert.match(seen.ideaA, /research の答え/);
  assert.match(seen.critic, /ideaA の答え/);
  assert.match(seen.critic, /発案役B は失敗: 429 混雑/);
  assert.match(seen.chair, /critic の答え/);
  assert.match(seen.chair, /指標Y/);
  assert.equal(r.final, "chair の答え");
  assert.ok(Math.abs(r.cost - 0.04) < 1e-9);
  const md = transcript({ title: "t", ...r });
  assert.match(md, /⚠️ 失敗: 429 混雑/);
});

test("まとめ役が失敗したら final は null", async () => {
  const chat = async (role) => (role === "chair" ? { text: "  " } : { text: "ok" });
  const r = await runCouncil({ config, chat, mode: "brief", question: "", context: "", calendar: "", today: "2026-11-05" });
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
