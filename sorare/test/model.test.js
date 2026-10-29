import { test } from "node:test";
import assert from "node:assert/strict";
import { teamForm, startRate, project, bestLineup, sellCandidates } from "../src/model.js";
import { totp, usd } from "../src/api.js";

test("teamForm はホーム・アウェイを見分けて未消化の試合を飛ばす", () => {
  const g = [
    { homeGoals: 2, awayGoals: 1, homeTeam: { name: "A" }, awayTeam: { name: "B" } },
    { homeGoals: 0, awayGoals: 3, homeTeam: { name: "C" }, awayTeam: { name: "A" } },
    { homeGoals: null, awayGoals: null, homeTeam: { name: "A" }, awayTeam: { name: "D" } },
  ];
  assert.deepEqual(teamForm("A", g), { gf: 2.5, ga: 0.5, n: 2 });
});

test("startRate は 60 分以上の割合", () => {
  assert.equal(startRate([{ playerGameStats: { minsPlayed: 90 } }, { playerGameStats: { minsPlayed: 30 } }, { playerGameStats: null }, { playerGameStats: { minsPlayed: 60 } }]), 0.5);
  assert.equal(startRate([]), 0);
});

test("project は守備側に相手の得点の少なさ、攻撃側に相手の失点の多さを効かせる", () => {
  const ctx = { avgGf: 1.5, form: { A: { gf: 1.5, ga: 1.5 }, B: { gf: 0.5, ga: 2.5 } }, next: { A: { opp: "B", home: true } } };
  const df = project({ club: "A", pos: "Defender", l15: 60, start: 1 }, ctx);
  const fw = project({ club: "A", pos: "Forward", l15: 60, start: 1 }, ctx);
  assert.ok(df.factor > 1.1 && fw.factor > 1.1);
  assert.ok(df.factor <= 1.15 * 1.03 + 1e-9);
  assert.equal(project({ club: "Z", pos: "Forward", l15: 60, start: 1 }, ctx).proj, 0);
});

const P = (id, pos, proj, club, price = 1) => ({ id, pos, proj, club, price });

test("bestLineup は GK・DF・MF・FW・EX の順でクラブ上限と予算を守る", () => {
  const c = [P("g", "Goalkeeper", 60, "X"), P("d1", "Defender", 70, "X"), P("d2", "Defender", 65, "X"), P("d3", "Defender", 50, "Y"),
    P("m", "Midfielder", 55, "Y"), P("f", "Forward", 68, "Z"), P("f2", "Forward", 66, "Z", 100)];
  const r = bestLineup(c, { maxPerClub: 2, budget: 10 });
  assert.deepEqual(r.lineup.map((x) => x.id), ["g", "d1", "m", "f", "d3"]);   // d2 は X が 3 人になる、f2 は予算超え
  assert.equal(r.captain, "d1");
  assert.equal(bestLineup(c.filter((x) => x.pos !== "Goalkeeper")), null);
});

test("sellCandidates は年齢とスタメン率で拾う", () => {
  const r = sellCandidates([{ age: 33, start: 0.9 }, { age: 25, start: 0.3 }, { age: 25, start: 0.9 }], { maxAge: 31, minStartRate: 0.5 });
  assert.deepEqual(r.map((x) => x.reasons), [["33歳"], ["スタメン率30%"]]);
});

test("totp は RFC 6238 のテストベクタと一致", () => {
  // 秘密鍵 "12345678901234567890" の base32、T=59 秒 → 94287082(8 桁)
  assert.equal(totp("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", 59000, 30, 8), "94287082");
});

test("totp は otpauth URL・小文字・空白とハイフン入りの秘密鍵も受け付ける", () => {
  const want = totp("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", 59000);
  assert.equal(totp("otpauth://totp/Sorare:me?secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ&issuer=Sorare", 59000), want);
  assert.equal(totp("gezd gnbv-gy3t qojq gezd gnbv gy3t qojq", 59000), want);
});

test("秘密鍵でない値はわかる理由で止める", () => {
  assert.throws(() => totp("123456"), /6桁のコードではなく/);
  assert.throws(() => totp("ABCD-1890-EFGH"), /数字の0・1・8・9/);
  assert.throws(() => totp("otpauth://totp/x?issuer=Sorare"), /secret= が無い/);
});

test("usd はドル・ユーロ建てを換算し ETH 建ては null", () => {
  assert.equal(usd({ usdCents: 46 }), 0.46);
  assert.equal(usd({ eurCents: 200 }, 1.1), 2.2);
  assert.equal(usd({ usdCents: null, eurCents: null }), null);
});
